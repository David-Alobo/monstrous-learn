"""The capstone pipeline: a resumable, monitored pipeline over a chemlib library.

Stages, for every batch of the input:

    ingest (with retries) -> validate -> standardise -> deduplicate by InChIKey
    -> filter (PAINS, property limits) -> fingerprints and descriptors
    -> partitioned Parquet + a checkpoint in DuckDB

and once every batch is done: reconcile the counts, register the tables in DuckDB and write a
provenance manifest.

The per-molecule work of a batch (validate, standardise, flags, features) is a pure function of the
batch, so several batches run at once in worker processes. Everything that depends on earlier
batches (deduplication against molecules already seen, the checkpoint) happens in the main process,
one batch at a time and in order, so the output is the same however many workers run and however
often the run is stopped and resumed.

Usage, from this folder (settings come from CAPSTONE_* environment variables):

    python pipeline.py                                    # 10,000 molecules into work/capstone
    CAPSTONE_N_MOLECULES=1733400 CAPSTONE_BATCH_SIZE=20000 CAPSTONE_WORKERS=8 python pipeline.py

Run the same command again after a crash and it resumes from the last finished batch.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import rdkit
from joblib import Parallel, delayed
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, rdFingerprintGenerator
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
from rdkit.Chem.MolStandardize import rdMolStandardize
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the series folder, for chemlib
import chemlib  # noqa: E402

RDLogger.DisableLog("rdApp.*")  # every failure is recorded as a reason code instead
log = logging.getLogger(__name__)  # the run's structured log; see open_log()

# ---- settings ----------------------------------------------------------------------------------


class Settings(BaseSettings):
    """Everything a run needs, checked before it starts; each can be set as CAPSTONE_<NAME>."""

    model_config = SettingsConfigDict(env_prefix="CAPSTONE_")

    n_molecules: int = Field(10_000, gt=0, le=chemlib.size())
    seed: int = Field(15, ge=0)
    defect_rate: float = Field(0.02, ge=0, le=0.5)
    batch_size: int = Field(500, gt=0)
    workers: int = Field(4, ge=1, le=256)
    out_dir: Path = Path("work/capstone")
    max_mw: float = Field(500.0, gt=0)
    max_logp: float = 5.0
    max_attempts: int = Field(4, ge=1, le=10)
    retry_wait_s: float = Field(0.5, ge=0)


# ---- the rules: what decides the output, versioned and hashed -----------------------------------

ALLOWED_ELEMENTS = ("Br", "C", "Cl", "F", "H", "N", "O", "S")
MORGAN_RADIUS = 2
MORGAN_BITS = 2048  # stored packed, eight bits to a byte
RULES = {
    "version": "1.0.0",  # change it whenever a rule below changes
    "standardise": ["FragmentParent (largest organic fragment)", "Uncharger"],
    "allowed_elements": list(ALLOWED_ELEMENTS),
    "filters": ["RDKit FilterCatalog PAINS (A, B, C)", "max_mw", "max_logp"],
    "fingerprint": f"Morgan radius {MORGAN_RADIUS}, {MORGAN_BITS} bits",
    "rdkit": rdkit.__version__,
}


def rules_hash() -> str:
    """A short hash of the rules (and the RDKit version), stored with every output row.

    Returns:
        The first 12 hexadecimal digits of the rules' SHA-256.
    """
    text = json.dumps(RULES, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# ---- output tables: fixed schemas, so every partition has the same columns and types -----------

SCHEMAS = {
    "compounds": pa.schema(
        [
            ("id", pa.string()),
            ("inchikey", pa.string()),
            ("smiles", pa.string()),
            ("input_smiles", pa.string()),
            ("mw", pa.float64()),
            ("logp", pa.float64()),
            ("tpsa", pa.float64()),
            ("hbd", pa.int32()),
            ("hba", pa.int32()),
            ("heavy_atoms", pa.int32()),
            ("morgan2", pa.binary(MORGAN_BITS // 8)),
            ("rules_hash", pa.string()),
            ("defect", pa.string()),
        ]
    ),
    "quarantine": pa.schema(
        [
            ("id", pa.string()),
            ("input_smiles", pa.string()),
            ("stage", pa.string()),
            ("reason", pa.string()),
            ("defect", pa.string()),
        ]
    ),
    "removed": pa.schema(
        [
            ("id", pa.string()),
            ("inchikey", pa.string()),
            ("smiles", pa.string()),
            ("reason", pa.string()),
            ("detail", pa.string()),
            ("defect", pa.string()),
        ]
    ),
}


# ---- ingest ------------------------------------------------------------------------------------


def n_batches(settings: Settings) -> int:
    """How many batches the input has.

    Args:
        settings: The run's settings.

    Returns:
        The number of batches.
    """
    return -(-settings.n_molecules // settings.batch_size)  # rounded up


@lru_cache(maxsize=2)
def _sample(n: int, seed: int) -> pd.DataFrame:
    """A chemlib sample, made once per process and reused by every batch.

    Args:
        n: How many molecules.
        seed: Which sample.

    Returns:
        The sample, sorted by molecule number.
    """
    return chemlib.library(n, seed=seed)


def read_batch(settings: Settings, number: int) -> pd.DataFrame:
    """Batch `number` of the input, with recorded faults; the same rows every time it is read.

    The whole library (n_molecules = chemlib.size()) is streamed, never held in memory; a smaller
    run reads a random sample of the library.

    Args:
        settings: The run's settings.
        number: The batch, from 0.

    Returns:
        The batch: id, smiles, vendor, price_usd, stock_mg and chemlib's `defect` label.
    """
    start = number * settings.batch_size
    size = min(settings.batch_size, settings.n_molecules - start)
    if settings.n_molecules >= chemlib.size():
        rows = next(chemlib.stream(size, batch=size, start=start))
    else:
        sample = _sample(settings.n_molecules, settings.seed)
        rows = sample.iloc[start : start + size].reset_index(drop=True)
    seed = settings.seed * 100_000 + number
    batch = chemlib.add_defects(rows, rate=settings.defect_rate, seed=seed)
    # chemlib writes each duplicate as a random SMILES from RDKit's unseeded random generator, so
    # the same batch read twice in one process can differ. A resumable run needs every read of a
    # batch to give the same rows, so the duplicates are rewritten with a seeded random SMILES
    # (made from the canonical SMILES, so the atom order it starts from is always the same).
    is_dup = batch["defect"] == "duplicate"
    canonical = [Chem.CanonSmiles(smiles) for smiles in batch.loc[is_dup, "smiles"]]
    batch.loc[is_dup, "smiles"] = [
        Chem.MolToRandomSmilesVect(Chem.MolFromSmiles(smiles), 1, randomSeed=seed)[0]
        for smiles in canonical
    ]
    return batch


class Faults(NamedTuple):
    """Faults to inject, for testing resumability and retries (never set in production).

    flaky_reads: batch number -> how many reads of it fail before one succeeds.
    crash_in_batch: crash after writing this batch's files, before its checkpoint.
    """

    flaky_reads: dict[int, int] = {}  # never changed, so one shared default is safe
    crash_in_batch: int | None = None


class SimulatedCrash(RuntimeError):
    """Raised by an injected fault, as if the process had been killed."""


MAX_RETRY_WAIT_S = 30  # the longest wait between two reads, however many have failed


def read_with_retries(settings: Settings, number: int, faults: Faults) -> tuple[pd.DataFrame, int]:
    """Read a batch, retrying connection errors with exponential back-off (tenacity).

    Args:
        settings: The run's settings (max_attempts, retry_wait_s).
        number: The batch.
        faults: Injected faults; flaky_reads makes the first reads of a batch fail.

    Each retry is logged as a warning on this module's logger.

    Returns:
        The batch and how many attempts it took.
    """
    attempts = 0

    def log_retry(state: RetryCallState) -> None:
        """Log one failed read, before tenacity waits and tries again."""
        log.warning("read failed; retrying", extra={"fields": {
            "batch": number, "attempt": state.attempt_number,
            "error": str(state.outcome.exception())}})  # fmt: skip

    retrying = Retrying(
        stop=stop_after_attempt(settings.max_attempts),
        wait=wait_exponential(multiplier=settings.retry_wait_s, max=MAX_RETRY_WAIT_S),
        retry=retry_if_exception_type(ConnectionError),
        before_sleep=log_retry,
        reraise=True,
    )
    for attempt in retrying:
        with attempt:
            attempts += 1
            if attempts <= faults.flaky_reads.get(number, 0):
                raise ConnectionError(f"supplier connection reset reading batch {number}")
            batch = read_batch(settings, number)
    return batch, attempts


# ---- validate, standardise, flag and describe: one pure function per batch ---------------------

MORGAN = rdFingerprintGenerator.GetMorganGenerator(radius=MORGAN_RADIUS, fpSize=MORGAN_BITS)
UNCHARGER = rdMolStandardize.Uncharger()


@lru_cache(maxsize=1)
def pains_catalog() -> FilterCatalog:
    """RDKit's PAINS filters (families A, B and C), built once per process.

    Returns:
        The filter catalogue.
    """
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    return FilterCatalog(params)


def validate(smiles: str) -> tuple[Chem.Mol | None, str]:
    """Read and sanitise one record (as in Module 6).

    Args:
        smiles: The record's SMILES.

    Returns:
        The molecule, or None and the reason code ("PARSE" or "VALENCE").
    """
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        return None, "PARSE"
    try:
        Chem.SanitizeMol(mol)
    except Chem.MolSanitizeException:
        return None, "VALENCE"
    return mol, ""


def standardise(mol: Chem.Mol) -> tuple[Chem.Mol | None, str]:
    """The parent molecule, neutralised (as in Module 7), checked for allowed elements.

    Salts and solvents are removed here (their action in Module 6 is "fix"), so a sodium salt is
    standardised, not rejected; an element outside the allowed set is rejected after that.

    Args:
        mol: A sanitised molecule.

    Returns:
        The standardised molecule, or None and the reason code ("ELEMENT").
    """
    parent = rdMolStandardize.FragmentParent(mol, skipStandardize=True)
    parent = UNCHARGER.uncharge(parent)
    Chem.SanitizeMol(parent)
    if {atom.GetSymbol() for atom in parent.GetAtoms()} - set(ALLOWED_ELEMENTS):
        return None, "ELEMENT"
    return parent, ""


def features(mol: Chem.Mol) -> dict:
    """Descriptors, a packed Morgan fingerprint and the first PAINS match of a molecule.

    Args:
        mol: A standardised molecule.

    Returns:
        mw, logp, tpsa, hbd, hba, heavy_atoms, morgan2 (packed bits) and pains ("" if none).
    """
    match = pains_catalog().GetFirstMatch(mol)
    return {
        "mw": round(Descriptors.MolWt(mol), 3),
        "logp": round(Descriptors.MolLogP(mol), 3),
        "tpsa": round(Descriptors.TPSA(mol), 2),
        "hbd": Descriptors.NumHDonors(mol),
        "hba": Descriptors.NumHAcceptors(mol),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
        "morgan2": np.packbits(MORGAN.GetFingerprintAsNumPy(mol)).tobytes(),
        "pains": "" if match is None else match.GetDescription(),
    }


ROW_COLUMNS = ["id", "inchikey", "smiles", "input_smiles", "mw", "logp", "tpsa", "hbd", "hba",
               "heavy_atoms", "morgan2", "pains", "defect"]  # fmt: skip


def process_batch(batch: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate, standardise and describe every record of a batch. Pure: no files, no database.

    Args:
        batch: Records with id, smiles and defect.

    Returns:
        The standardised molecules with their InChIKey, features and PAINS match, and the
        quarantined records with their stage and reason.
    """
    rows, quarantined = [], []
    for record in batch.itertuples(index=False):
        mol, reason = validate(record.smiles)
        stage = "validate"
        if mol is not None:
            mol, reason = standardise(mol)
            stage = "standardise"
        inchikey = Chem.MolToInchiKey(mol) if mol is not None else ""
        if mol is not None and not inchikey:
            mol, reason = None, "INCHIKEY"
        if mol is None:
            quarantined.append({"id": record.id, "input_smiles": record.smiles, "stage": stage,
                                "reason": reason, "defect": record.defect})  # fmt: skip
            continue
        rows.append({"id": record.id, "inchikey": inchikey, "smiles": Chem.MolToSmiles(mol),
                     "input_smiles": record.smiles, **features(mol),
                     "defect": record.defect})  # fmt: skip
    return (pd.DataFrame(rows, columns=ROW_COLUMNS),
            pd.DataFrame(quarantined, columns=SCHEMAS["quarantine"].names))  # fmt: skip


# ---- deduplicate and filter: in order, against everything already seen -------------------------


def deduplicate(rows: pd.DataFrame, seen: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep the first record of each InChIKey, in this batch and across every earlier batch.

    Args:
        rows: Standardised molecules, in file order.
        seen: InChIKey -> id of the record kept for it, from earlier batches.

    Returns:
        The first records, and the duplicates (reason DUPLICATE, detail = the id kept instead).
    """
    first_id = dict(seen)
    keep, duplicate_of = [], []
    for key, record_id in zip(rows["inchikey"], rows["id"], strict=True):
        if key in first_id:
            keep.append(False)
            duplicate_of.append(first_id[key])
        else:
            first_id[key] = record_id
            keep.append(True)
            duplicate_of.append("")
    keep = np.array(keep, dtype=bool)
    duplicates = rows[~keep].assign(reason="DUPLICATE", detail=np.array(duplicate_of)[~keep])
    return rows[keep], duplicates


def apply_filters(rows: pd.DataFrame, settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove PAINS matches and molecules outside the property limits, recording why.

    Args:
        rows: Unique standardised molecules.
        settings: The limits (max_mw, max_logp).

    Returns:
        The molecules that pass, and those removed (reason PAINS, MW or LOGP, with a detail).
    """
    reason = np.select(
        [rows["pains"] != "", rows["mw"] > settings.max_mw, rows["logp"] > settings.max_logp],
        ["PAINS", "MW", "LOGP"],
        "",
    )
    detail = np.select(
        [reason == "PAINS", reason == "MW", reason == "LOGP"],
        [rows["pains"], rows["mw"].astype(str), rows["logp"].astype(str)],
        "",
    )
    removed = rows.assign(reason=reason, detail=detail)[reason != ""]
    return rows[reason == ""], removed


# ---- writing, checkpoints and the run record ---------------------------------------------------


def write_atomic(df: pd.DataFrame, table: str, path: Path) -> None:
    """Write a table as Parquet to a temporary file, then rename it into place in one step.

    Args:
        df: The rows (extra columns are dropped; the schema decides the columns).
        table: Which schema: "compounds", "quarantine" or "removed".
        path: The final file.
    """
    schema = SCHEMAS[table]
    data = pa.Table.from_pandas(df[schema.names], schema=schema, preserve_index=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    pq.write_table(data, tmp)
    os.replace(tmp, path)  # atomic: readers see the old file or the new one, never half of one


DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY, started TIMESTAMP, finished TIMESTAMP, status VARCHAR,
    batches INTEGER, message VARCHAR);
CREATE TABLE IF NOT EXISTS batches (
    batch INTEGER PRIMARY KEY, run_id VARCHAR, committed TIMESTAMP, attempts INTEGER,
    rows_in INTEGER, quarantined_validate INTEGER, quarantined_standardise INTEGER,
    duplicates INTEGER, filtered INTEGER, rows_out INTEGER);
CREATE TABLE IF NOT EXISTS seen (inchikey VARCHAR PRIMARY KEY, id VARCHAR);
"""


def connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    """Open the run's DuckDB database (checkpoints, run record, seen InChIKeys), creating it.

    Args:
        settings: The run's settings (out_dir).

    Returns:
        The connection.
    """
    settings.out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.out_dir / "pipeline.duckdb"))
    for statement in DDL.split(";"):
        if statement.strip():
            con.execute(statement)
    return con


def partition(settings: Settings, table: str, number: int) -> Path:
    """The Parquet file of one batch of one table (a Hive-style partition, batch=NNNNN).

    Args:
        settings: The run's settings (out_dir).
        table: "compounds", "quarantine" or "removed".
        number: The batch.

    Returns:
        The file's path.
    """
    return settings.out_dir / table / f"batch={number:05d}" / "part-0.parquet"


def commit_batch(
    con: duckdb.DuckDBPyConnection,
    settings: Settings,
    number: int,
    batch: pd.DataFrame,
    result: tuple[pd.DataFrame, pd.DataFrame],
    attempts: int,
    run_id: str,
    clock: Callable[[], datetime],
    faults: Faults,
) -> None:
    """Deduplicate and filter one processed batch, write its files, then checkpoint it.

    The files are written first and the checkpoint last, in one transaction with the batch's
    InChIKeys. A crash in between leaves files but no checkpoint, so the batch is simply done again
    (and its files overwritten with the same content) when the run resumes.

    Args:
        con: The run's database.
        settings: The run's settings.
        number: The batch.
        batch: The batch as read (for its row count).
        result: What process_batch returned for it.
        attempts: How many reads it took.
        run_id: The run committing it.
        clock: Returns the current time.
        faults: Injected faults (crash_in_batch).
    """
    rows, quarantined = result
    keys = rows[["inchikey"]]  # noqa: F841 (read by DuckDB below)
    seen = dict(con.execute(
        "SELECT s.inchikey, s.id FROM seen s JOIN keys k USING (inchikey)").fetchall())  # fmt: skip
    unique, duplicates = deduplicate(rows, seen)
    kept, filtered = apply_filters(unique, settings)
    kept = kept.assign(rules_hash=rules_hash())
    write_atomic(kept, "compounds", partition(settings, "compounds", number))
    write_atomic(quarantined, "quarantine", partition(settings, "quarantine", number))
    removed = pd.concat([duplicates, filtered], ignore_index=True)
    removed = removed.reindex(columns=SCHEMAS["removed"].names)
    write_atomic(removed, "removed", partition(settings, "removed", number))
    if faults.crash_in_batch == number:
        raise SimulatedCrash(f"killed after writing batch {number}, before its checkpoint")
    counts = {
        "rows_in": len(batch),
        "quarantined_validate": int((quarantined["stage"] == "validate").sum()),
        "quarantined_standardise": int((quarantined["stage"] == "standardise").sum()),
        "duplicates": len(duplicates),
        "filtered": len(filtered),
        "rows_out": len(kept),
    }
    new_keys = unique[["inchikey", "id"]]  # noqa: F841 (read by DuckDB below)
    con.execute("BEGIN TRANSACTION")
    con.execute("INSERT INTO seen SELECT inchikey, id FROM new_keys")
    con.execute(
        "INSERT INTO batches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [number, run_id, clock(), attempts, *counts.values()],
    )
    con.execute("COMMIT")
    log.info("batch committed", extra={"fields": {"run_id": run_id, "batch": number, **counts}})


class ReconciliationError(RuntimeError):
    """The counts of a run do not add up, or the files disagree with the run record."""


def reconcile(con: duckdb.DuckDBPyConnection, settings: Settings) -> dict:
    """Check that every row is accounted for, every batch is done, and the files agree.

    Args:
        con: The run's database (with the views registered).
        settings: The run's settings.

    Returns:
        The totals, by stage.

    Raises:
        ReconciliationError: listing every check that failed.
    """
    totals = (
        con.execute("""
        SELECT count(*) AS batches, sum(rows_in) AS rows_in,
               sum(quarantined_validate) AS quarantined_validate,
               sum(quarantined_standardise) AS quarantined_standardise,
               sum(duplicates) AS duplicates, sum(filtered) AS filtered, sum(rows_out) AS rows_out
        FROM batches
    """)
        .df()
        .iloc[0]
        .astype(int)
        .to_dict()
    )
    files = {table: con.execute(f"SELECT count(*) FROM {table}").fetchall()[0][0]
             for table in SCHEMAS}  # fmt: skip
    problems = []
    unbalanced = con.execute("""
        SELECT batch FROM batches WHERE rows_in <> quarantined_validate + quarantined_standardise
            + duplicates + filtered + rows_out ORDER BY batch
    """).fetchall()
    if unbalanced:
        problems.append(f"batches whose counts do not add up: {[b for (b,) in unbalanced]}")
    if totals["batches"] != n_batches(settings):
        problems.append(f"{totals['batches']} of {n_batches(settings)} batches done")
    if files["compounds"] != totals["rows_out"]:
        problems.append(f"compounds files hold {files['compounds']} rows, record says "
                        f"{totals['rows_out']}")  # fmt: skip
    quarantined = totals["quarantined_validate"] + totals["quarantined_standardise"]
    if files["quarantine"] != quarantined:
        problems.append(f"quarantine files hold {files['quarantine']} rows, record says "
                        f"{quarantined}")  # fmt: skip
    if files["removed"] != totals["duplicates"] + totals["filtered"]:
        problems.append(f"removed files hold {files['removed']} rows, record says "
                        f"{totals['duplicates'] + totals['filtered']}")  # fmt: skip
    if problems:
        raise ReconciliationError("; ".join(problems))
    return totals


def register_views(con: duckdb.DuckDBPyConnection, settings: Settings) -> None:
    """Register the Parquet tables as DuckDB views, so the database is the way in to the data.

    Args:
        con: The run's database.
        settings: The run's settings (out_dir).
    """
    for table in SCHEMAS:
        files = (settings.out_dir.resolve() / table / "*" / "*.parquet").as_posix()
        con.execute(f"CREATE OR REPLACE VIEW {table} AS "
                    f"SELECT * FROM read_parquet('{files}', hive_partitioning = true)")  # fmt: skip


CHUNK_BYTES = 1 << 20  # files are hashed 1 MiB at a time


def sha256_file(path: Path) -> str:
    """The SHA-256 of a file's bytes.

    Args:
        path: The file.

    Returns:
        Its hexadecimal digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(
    con: duckdb.DuckDBPyConnection,
    settings: Settings,
    totals: dict,
    clock: Callable[[], datetime],
) -> dict:
    """Write manifest.json: the input, rules, versions, counts and every output's hash.

    Args:
        con: The run's database.
        settings: The run's settings.
        totals: The reconciled totals.
        clock: Returns the current time.

    Returns:
        The manifest.
    """
    outputs = {}
    for path in sorted(settings.out_dir.glob("*/batch=*/*.parquet")):
        outputs[path.relative_to(settings.out_dir).as_posix()] = sha256_file(path)
    chemlib_file = Path(chemlib.__file__)
    manifest = {
        "created": clock().isoformat(timespec="seconds"),
        "runs": [r for (r,) in con.execute("SELECT run_id FROM runs ORDER BY run_id").fetchall()],
        "input": {
            "source": "chemlib",
            "chemlib_sha256": sha256_file(chemlib_file),
            "n_molecules": settings.n_molecules,
            "seed": settings.seed,
            "defect_rate": settings.defect_rate,
            "batch_size": settings.batch_size,
        },
        "settings": settings.model_dump(mode="json", exclude={"out_dir", "workers"}),
        "rules": RULES,
        "rules_hash": rules_hash(),
        "versions": {
            "python": platform.python_version(),
            "rdkit": rdkit.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
            "duckdb": duckdb.__version__,
        },
        "counts": totals,
        "outputs": outputs,
        "data_sha256": hashlib.sha256(json.dumps(outputs, sort_keys=True).encode()).hexdigest(),
    }
    path = settings.out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


# ---- logging -----------------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """One JSON object per line (as in Module 14), with the time from the run's clock."""

    def __init__(self, clock: Callable[[], datetime]):
        super().__init__()
        self.clock = clock

    def format(self, record: logging.LogRecord) -> str:
        """The record as a JSON line.

        Args:
            record: The log record.

        Returns:
            The line.
        """
        event = {"time": self.clock().isoformat(timespec="seconds"), "level": record.levelname,
                 "event": record.getMessage(), **getattr(record, "fields", {})}  # fmt: skip
        if record.exc_info:  # logged with log.exception: say what failed, with the full traceback
            event["error"] = f"{record.exc_info[0].__name__}: {record.exc_info[1]}"
            event["traceback"] = self.formatException(record.exc_info)
        return json.dumps(event)


def close_log() -> None:
    """Close and remove every handler of this module's logger (the log file, and any other)."""
    for handler in list(log.handlers):
        handler.close()
        log.removeHandler(handler)


def open_log(settings: Settings, clock: Callable[[], datetime]) -> None:
    """Point this module's logger at the run's pipeline.log, one JSON line per event.

    Handlers left from an earlier run, or added by a caller, are removed first, so no line is
    written twice. The logger does not pass its lines on to the root logger: they are JSON, and a
    plain handler there would show a second copy of every one.

    Args:
        settings: The run's settings (out_dir).
        clock: Where the times come from.
    """
    close_log()
    log.setLevel(logging.INFO)
    log.propagate = False
    handler = logging.FileHandler(settings.out_dir / "pipeline.log", encoding="utf-8")
    handler.setFormatter(JsonFormatter(clock))
    log.addHandler(handler)


# ---- the run -----------------------------------------------------------------------------------


def utc_now() -> datetime:
    """The real time, in UTC (the default clock).

    Returns:
        The current time, without a timezone (all times in the run record are UTC).
    """
    return datetime.now(UTC).replace(tzinfo=None)


NO_FAULTS = Faults()


def run(
    settings: Settings, clock: Callable[[], datetime] = utc_now, faults: Faults = NO_FAULTS
) -> dict:
    """Run the pipeline, or resume it: batches already checkpointed are skipped.

    Args:
        settings: The run's settings.
        clock: Returns the current time (inject a fixed clock for repeatable records).
        faults: Injected faults, for testing only.

    Returns:
        The manifest of the finished output.
    """
    con = connect(settings)
    open_log(settings, clock)
    try:
        return _run(con, settings, clock, faults)
    except Exception:
        log.exception("run failed")  # the reason and the full traceback, before the log closes
        raise
    finally:  # a crash still releases the database and the log file
        con.close()
        close_log()


def _run(
    con: duckdb.DuckDBPyConnection,
    settings: Settings,
    clock: Callable[[], datetime],
    faults: Faults,
) -> dict:
    """The body of run(), with the database and the logger open.

    Args:
        con: The run's database.
        settings: The run's settings.
        clock: Returns the current time.
        faults: Injected faults.

    Returns:
        The manifest of the finished output.
    """
    # a run still marked "running" was killed: it can never finish, so say so
    con.execute("UPDATE runs SET status = 'abandoned' WHERE status = 'running'")
    run_number = con.execute("SELECT count(*) FROM runs").fetchall()[0][0] + 1
    run_id = f"run-{run_number:03d}"
    con.execute("INSERT INTO runs VALUES (?, ?, NULL, 'running', 0, '')", [run_id, clock()])
    done = {b for (b,) in con.execute("SELECT batch FROM batches").fetchall()}
    todo = [b for b in range(n_batches(settings)) if b not in done]
    log.info("run started", extra={"fields": {"run_id": run_id, "rules_hash": rules_hash(),
                                              "done": len(done), "todo": len(todo)}})  # fmt: skip
    with Parallel(n_jobs=settings.workers) as parallel:
        for first in range(0, len(todo), settings.workers):
            wave = todo[first : first + settings.workers]
            read = [read_with_retries(settings, number, faults) for number in wave]
            results = parallel(delayed(process_batch)(batch) for batch, _ in read)
            for number, (batch, attempts), result in zip(wave, read, results, strict=True):
                commit_batch(con, settings, number, batch, result, attempts, run_id, clock,
                             faults)  # fmt: skip
    register_views(con, settings)
    totals = reconcile(con, settings)
    con.execute("UPDATE runs SET finished = ?, status = 'succeeded', batches = ? WHERE run_id = ?",
                [clock(), len(todo), run_id])  # fmt: skip
    manifest = write_manifest(con, settings, totals, clock)
    log.info("run finished", extra={"fields": {"run_id": run_id, **totals}})
    return manifest


def main() -> int:
    """Run (or resume) the pipeline with settings from the environment, and print the totals.

    The run itself reports to pipeline.log; the totals are printed for the person who ran it. A
    failed run is logged there with its full traceback, and the program ends with exit code 1, so
    whatever started it (a person, tmux, a scheduler, CI) can tell that it failed.

    Returns:
        The exit code: 0 if the run finished, 1 if it failed.
    """
    try:
        settings = Settings()
        manifest = run(settings)
    except Exception as error:  # the top of the program: the one place a broad catch belongs
        print(f"The run failed: {type(error).__name__}: {error}", file=sys.stderr)
        print("The full traceback is in pipeline.log (if the run got that far).", file=sys.stderr)
        return 1
    for stage, count in manifest["counts"].items():
        print(f"{stage:24} {count:>10,}")
    print("data sha256:", manifest["data_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
