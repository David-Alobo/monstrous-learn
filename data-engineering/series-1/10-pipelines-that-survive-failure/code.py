"""Pipelines that survive failure: the code of the lesson, in order.

Idempotent batches, checkpoints, retries with back-off, quarantine, atomic writes, cached results and settings checked up front, so a run that fails halfway can be resumed and gives the same answer.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/10-pipelines-that-survive-failure/
Run it from anywhere, e.g. from the series folder: uv run python 10-pipelines-that-survive-failure/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]

# ---- Setup ----
import csv
import logging
import math
import os
import random
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any, TextIO

import pandas as pd
from joblib import Memory
from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from chemlib import add_defects, library

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# defaults of the run settings (section 2); environment variables CHEMRUN_* override them
WORK = Path("work")  # every file the lesson writes goes here
N_MOLECULES = 12_000  # molecules drawn from chemlib
BATCH_SIZE = 1_000  # records per batch: smaller batches lose less in a crash
MAX_ATTEMPTS = 5  # calls in all before a transient failure is given up
FIRST_DELAY_S = 0.5  # ceiling of the first retry wait, in seconds; it doubles after each failure
MAX_DELAY_S = 30.0  # the largest retry ceiling, in seconds

# the faulty library
LIBRARY_SEED = 10  # chemlib's seed for the molecules
DEFECT_RATE = 0.03  # fraction of records given a fault
DEFECT_SEED = 11  # chemlib's seed for which records get which fault
ALLOWED_ELEMENTS = {"C", "N", "O", "S", "F", "Cl", "Br"}  # anything else is quarantined

# the lesson's demonstrations
JITTER_SEED = 1  # seed for the random retry waits, so they are the same on every run
CRASH_AT_BATCH = 7  # the batch at which the pipeline is made to crash
CRASH_AFTER_ROWS = 4_000  # the row at which the CSV export is made to crash

RDLogger.DisableLog("rdApp.*")  # bad molecules are reported in a table, not as RDKit messages
WORK.mkdir(exist_ok=True)

# ---- 2. Settings checked before a run starts ----
class RunSettings(BaseSettings):
    """Everything a run needs to know, checked before it starts.

    Each setting can be overridden by an environment variable: CHEMRUN_BATCH_SIZE, and so on.
    """

    model_config = SettingsConfigDict(env_prefix="CHEMRUN_")

    n_molecules: int = Field(N_MOLECULES, gt=0)
    batch_size: int = Field(BATCH_SIZE, gt=0)
    work_dir: Path = WORK
    max_attempts: int = Field(MAX_ATTEMPTS, ge=1, le=10)
    first_delay_s: float = Field(FIRST_DELAY_S, gt=0)
    max_delay_s: float = Field(MAX_DELAY_S, gt=0)

    @field_validator("work_dir")
    @classmethod
    def folder_exists(cls, folder: Path) -> Path:
        """The output folder must exist before the run, so a typing mistake fails now."""
        if not folder.is_dir():
            raise ValueError(f"no folder called '{folder}'")
        return folder

    @model_validator(mode="after")
    def delays_in_order(self) -> "RunSettings":
        """The first retry delay cannot be longer than the longest delay allowed."""
        if self.first_delay_s > self.max_delay_s:
            raise ValueError("first_delay_s is longer than max_delay_s")
        return self


settings = RunSettings()
for name, value in settings.model_dump().items():
    print(f"{name:14} {value}")
os.environ["CHEMRUN_BATCH_SIZE"] = "0"
os.environ["CHEMRUN_WORK_DIR"] = "wrok"
try:
    RunSettings()
except ValidationError as err:
    log.error("refused to start: %d bad settings", err.error_count())
    for problem in err.errors():
        log.error("  %s: %s (got %r)", problem["loc"][0], problem["msg"], problem["input"])
finally:
    del os.environ["CHEMRUN_BATCH_SIZE"], os.environ["CHEMRUN_WORK_DIR"]

# ---- 3. One molecule at a time: quarantine, don't crash ----
class BadMolecule(Exception):
    """A permanent problem with a record: trying again will not fix it."""


def prepare(smiles: str) -> dict:
    """Check a SMILES lightly, canonicalise it and compute three descriptors.

    Args:
        smiles: The record's SMILES.

    Returns:
        The canonical SMILES, molecular weight, logP and TPSA.

    Raises:
        BadMolecule: If the record cannot be used, with the reason.
    """
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        raise BadMolecule("cannot be parsed")
    try:
        Chem.SanitizeMol(mol)
    except Chem.MolSanitizeException as err:
        raise BadMolecule(f"fails sanitisation ({type(err).__name__})") from err
    if len(Chem.GetMolFrags(mol)) > 1:
        raise BadMolecule("more than one component")
    unexpected = sorted({atom.GetSymbol() for atom in mol.GetAtoms()} - ALLOWED_ELEMENTS)
    if unexpected:
        raise BadMolecule(f"unexpected element {', '.join(unexpected)}")
    return {
        "canonical": Chem.MolToSmiles(mol),
        "mol_wt": round(Descriptors.MolWt(mol), 3),
        "logp": round(Descriptors.MolLogP(mol), 3),
        "tpsa": round(Descriptors.TPSA(mol), 2),
    }


def prepare_batch(batch: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prepare every record of a batch; bad records go to quarantine and the batch carries on.

    Args:
        batch: Records with id and smiles.

    Returns:
        The prepared molecules, and the quarantined records with the reason for each.
    """
    good, bad = [], []
    for record in batch.itertuples(index=False):
        try:
            good.append({"id": record.id, "smiles": record.smiles, **prepare(record.smiles)})
        except BadMolecule as err:
            bad.append({"id": record.id, "smiles": record.smiles, "reason": str(err)})
    good_columns = ["id", "smiles", "canonical", "mol_wt", "logp", "tpsa"]
    return (pd.DataFrame(good, columns=good_columns),
            pd.DataFrame(bad, columns=["id", "smiles", "reason"]))
source = add_defects(library(settings.n_molecules, seed=LIBRARY_SEED), rate=DEFECT_RATE,
                     seed=DEFECT_SEED)
source = source.sort_values("id").reset_index(drop=True)
n_batches = math.ceil(len(source) / settings.batch_size)
log.info("%s records in %d batches of up to %s", f"{len(source):,}", n_batches,
         f"{settings.batch_size:,}")
print(source["defect"].replace("", "(none)").value_counts().to_string())
good, bad = prepare_batch(source.iloc[: settings.batch_size])
log.info("prepared %d, quarantined %d", len(good), len(bad))
print(bad["reason"].value_counts().to_string())

# ---- 4. Retries with back-off and jitter ----
class TransientError(Exception):
    """A failure that may go away if we wait and try again: a timeout, a busy server."""


class FlakyService:
    """A stand-in for a remote service that fails its first `failures` calls, then works."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def __call__(self, smiles: str) -> dict:
        """Prepare a molecule, unless this is one of the calls that fail."""
        self.calls += 1
        if self.calls <= self.failures:
            raise TransientError(f"call {self.calls}: service busy")
        return prepare(smiles)
def with_retries(func: Callable, *args, max_attempts: int = MAX_ATTEMPTS,
                 first_delay: float = FIRST_DELAY_S, max_delay: float = MAX_DELAY_S,
                 rng: random.Random | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> Any:
    """Call func(*args), retrying transient failures with exponential back-off and full jitter.

    Args:
        func: What to call.
        *args: Its arguments.
        max_attempts: How many calls in all before giving up.
        first_delay: The ceiling of the first wait, in seconds; it doubles after each failure.
        max_delay: The largest ceiling, in seconds.
        rng: The random number generator for the jitter (a fresh, unseeded one if not given).
        sleep: How to wait (time.sleep unless told otherwise).

    Returns:
        What func returns.

    Raises:
        TransientError: If every attempt failed. Any other error is raised at once, unretried.
    """
    rng = rng or random.Random()
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args)
        except TransientError as err:
            if attempt == max_attempts:
                raise
            ceiling = min(max_delay, first_delay * 2 ** (attempt - 1))
            delay = rng.uniform(0, ceiling)
            log.warning("attempt %d failed (%s); waiting %.2f s of up to %s s",
                        attempt, err, delay, ceiling)
            sleep(delay)


waits = []
service = FlakyService(failures=3)
result = with_retries(service, "CC(=O)Oc1ccccc1C(=O)O", rng=random.Random(JITTER_SEED),
                      sleep=waits.append)
print(f"succeeded on call {service.calls}: aspirin, MW {result['mol_wt']}")
print(f"waited {sum(waits):.2f} s in all")
try:
    with_retries(FlakyService(failures=10), "CCO", rng=random.Random(JITTER_SEED),
                 sleep=waits.append)
except TransientError as err:
    log.error("gave up: %s", err)

broken = FlakyService(failures=0)
try:
    with_retries(broken, "C1CC", rng=random.Random(JITTER_SEED), sleep=waits.append)
except BadMolecule as err:
    log.warning("not retried (%d call), quarantined: %s", broken.calls, err)

# ---- The same with tenacity ----
service = FlakyService(failures=2)
waits = []


@retry(
    retry=retry_if_exception_type(TransientError),  # BadMolecule is not retried
    stop=stop_after_attempt(settings.max_attempts),
    wait=wait_random_exponential(multiplier=settings.first_delay_s, max=settings.max_delay_s),
    sleep=waits.append,  # leave this out in real use: tenacity then waits with time.sleep
    reraise=True,  # after the last attempt, raise the original error, not a wrapper
)
def prepare_remotely(smiles: str) -> dict:
    """Prepare a molecule on the (flaky) remote service, retrying transient failures."""
    return service(smiles)


random.seed(JITTER_SEED)  # tenacity draws its jitter from Python's random module
print(prepare_remotely("CN1C=NC2=C1C(=O)N(C(=O)N2C)C"))
print(f"{service.calls} calls; waits of {[round(w, 2) for w in waits]} s")

# ---- 5. Idempotent batches ----
with closing(sqlite3.connect(WORK / "naive.sqlite")) as naive:
    naive.execute("DROP TABLE IF EXISTS molecules")
    for attempt in (1, 2):
        good.to_sql("molecules", naive, if_exists="append", index=False)
        count = naive.execute("SELECT COUNT(*), COUNT(DISTINCT id) FROM molecules").fetchone()
        print(f"after writing batch 0 {attempt}x: {count[0]} rows, {count[1]} different molecules")
SCHEMA = """
CREATE TABLE IF NOT EXISTS molecules (
    id TEXT PRIMARY KEY, smiles TEXT, canonical TEXT, mol_wt REAL, logp REAL, tpsa REAL);
CREATE TABLE IF NOT EXISTS quarantine (id TEXT PRIMARY KEY, smiles TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS checkpoints (batch INTEGER PRIMARY KEY, n_good INTEGER, n_bad INTEGER);
"""
UPSERT_MOLECULE = """
INSERT INTO molecules VALUES (:id, :smiles, :canonical, :mol_wt, :logp, :tpsa)
ON CONFLICT (id) DO UPDATE SET smiles = excluded.smiles, canonical = excluded.canonical,
    mol_wt = excluded.mol_wt, logp = excluded.logp, tpsa = excluded.tpsa
"""
UPSERT_QUARANTINE = """
INSERT INTO quarantine VALUES (:id, :smiles, :reason)
ON CONFLICT (id) DO UPDATE SET smiles = excluded.smiles, reason = excluded.reason
"""


def connect(path: Path) -> sqlite3.Connection:
    """Open the run's database, creating its tables if they are not there yet."""
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def save_batch(con: sqlite3.Connection, good: pd.DataFrame, bad: pd.DataFrame) -> None:
    """Write a batch's results idempotently: all its rows in one transaction, upserted by id."""
    with con:  # commits at the end, or rolls everything back if anything fails
        con.executemany(UPSERT_MOLECULE, good.to_dict("records"))
        con.executemany(UPSERT_QUARANTINE, bad.to_dict("records"))


def count_rows(con: sqlite3.Connection) -> str:
    """How many rows each table holds, as one line."""
    tables = ["molecules", "quarantine", "checkpoints"]
    counts = [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables]
    return ", ".join(f"{t} {n:,}" for t, n in zip(tables, counts, strict=True))


demo_path = WORK / "demo.sqlite"
demo_path.unlink(missing_ok=True)
with closing(connect(demo_path)) as con:
    for attempt in (1, 2):
        save_batch(con, good, bad)
        print(f"after writing batch 0 {attempt}x: {count_rows(con)}")

# ---- 6. Checkpoints, crashes and resuming ----
class SimulatedCrash(Exception):
    """Stands in for the process dying: power cut, out of memory, a server restart."""


BatchPreparer = Callable[[pd.DataFrame], tuple[pd.DataFrame, pd.DataFrame]]


def run_pipeline(source: pd.DataFrame, db_path: Path, batch_size: int,
                 prepare_fn: BatchPreparer = prepare_batch,
                 crash_at: int | None = None) -> list[int]:
    """Prepare every batch not yet checkpointed, saving each idempotently.

    Args:
        source: The records, in a fixed order (it decides which records are in which batch).
        db_path: The run's SQLite database.
        batch_size: Records per batch.
        prepare_fn: The function that prepares one batch.
        crash_at: The batch at which to simulate a crash, after saving it and before its checkpoint.

    Returns:
        The batches this call ran.
    """
    ran = []
    with closing(connect(db_path)) as con:
        done = {row[0] for row in con.execute("SELECT batch FROM checkpoints")}
        for k in range(math.ceil(len(source) / batch_size)):
            if k in done:
                continue
            good, bad = prepare_fn(source.iloc[k * batch_size : (k + 1) * batch_size])
            save_batch(con, good, bad)
            if k == crash_at:
                raise SimulatedCrash(f"died after saving batch {k}, before its checkpoint")
            with con:
                con.execute("INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?)",
                            (k, len(good), len(bad)))
            ran.append(k)
    return ran
reference_path = settings.work_dir / "reference.sqlite"
reference_path.unlink(missing_ok=True)
ran = run_pipeline(source, reference_path, settings.batch_size)
log.info("ran batches %d to %d", ran[0], ran[-1])
with closing(sqlite3.connect(reference_path)) as con:
    print(count_rows(con))
run_path = settings.work_dir / "run.sqlite"
run_path.unlink(missing_ok=True)
try:
    run_pipeline(source, run_path, settings.batch_size, crash_at=CRASH_AT_BATCH)
except SimulatedCrash as err:
    log.error("crashed: %s", err)
with closing(sqlite3.connect(run_path)) as con:
    print(count_rows(con))
    finished = [row[0] for row in con.execute("SELECT batch FROM checkpoints ORDER BY batch")]
print(f"checkpointed batches: {finished}")
ran = run_pipeline(source, run_path, settings.batch_size)
log.info("resumed: skipped %d finished batches, ran batches %s", len(finished), ran)
with closing(sqlite3.connect(run_path)) as con:
    print(count_rows(con))
def read_tables(db_path: Path) -> dict[str, pd.DataFrame]:
    """Every table of a run's database, sorted by its key, for comparison."""
    keys = {"molecules": "id", "quarantine": "id", "checkpoints": "batch"}
    with closing(sqlite3.connect(db_path)) as con:
        return {t: pd.read_sql(f"SELECT * FROM {t} ORDER BY {k}", con) for t, k in keys.items()}


reference, resumed = read_tables(reference_path), read_tables(run_path)
for table in reference:
    pd.testing.assert_frame_equal(reference[table], resumed[table])  # raises if they differ
    print(f"{table}: identical ({len(reference[table]):,} rows)")
caught = source.merge(reference["quarantine"][["id", "reason"]], on="id", how="left")
caught["reason"] = caught["reason"].fillna("(prepared)")
print(pd.crosstab(caught["defect"].replace("", "(none)"), caught["reason"]).to_string())

# ---- 7. Atomic writes ----
molecules = reference["molecules"]
export_path = settings.work_dir / "molecules.csv"


def write_rows(handle: TextIO, table: pd.DataFrame, crash_after: int | None = None) -> None:
    """Write a table as CSV to an open file, one row at a time, optionally crashing partway."""
    writer = csv.writer(handle)
    writer.writerow(table.columns)
    for i, row in enumerate(table.itertuples(index=False)):
        if i == crash_after:
            raise SimulatedCrash(f"died after writing {i:,} rows")
        writer.writerow(row)


export_path.unlink(missing_ok=True)
try:
    with open(export_path, "w", newline="", encoding="utf-8") as handle:
        write_rows(handle, molecules, crash_after=CRASH_AFTER_ROWS)
except SimulatedCrash as err:
    log.error("crashed: %s", err)
rows_seen = len(pd.read_csv(export_path))
print(f"the file exists: {export_path.exists()}, rows a reader sees: {rows_seen:,}")
def write_csv_atomic(table: pd.DataFrame, path: Path, crash_after: int | None = None) -> None:
    """Write a table as CSV so that readers only ever see the old file or the complete new one.

    Args:
        table: What to write.
        path: The file to write.
        crash_after: Simulate a crash after this many rows (for the lesson).
    """
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as handle:
            write_rows(handle, table, crash_after)
            handle.flush()
            os.fsync(handle.fileno())  # the bytes are on the disk, not only in memory
        os.replace(tmp, path)  # atomic: the old file or the new one, never half of one
    finally:
        tmp.unlink(missing_ok=True)


write_csv_atomic(molecules, export_path)
print(f"complete export: {len(pd.read_csv(export_path)):,} rows")
try:
    write_csv_atomic(molecules, export_path, crash_after=CRASH_AFTER_ROWS)
except SimulatedCrash as err:
    log.error("crashed: %s", err)
print(f"after the crash: {len(pd.read_csv(export_path)):,} rows, "
      f"temporary file left behind: {export_path.with_name('molecules.csv.tmp').exists()}")

# ---- 8. Cached results with joblib.Memory ----
memory = Memory(settings.work_dir / "cache", verbose=0)
memory.clear(warn=False)  # start the lesson with an empty cache
computed = []


def prepare_batch_cached(batch: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """prepare_batch, with its results kept on disk: each different batch is computed once."""
    computed.append(batch["id"].iloc[0])
    return prepare_batch(batch)


# joblib names the cache folder after where the function is defined: for a script, its full path,
# which can pass Windows' 260-character path limit. A short module name keeps the folder short.
prepare_batch_cached.__module__ = "module10"
prepare_batch_cached = memory.cache(prepare_batch_cached)


for name in ("first", "second"):
    path = settings.work_dir / f"cached-{name}.sqlite"
    path.unlink(missing_ok=True)
    before = len(computed)
    run_pipeline(source, path, settings.batch_size, prepare_fn=prepare_batch_cached)
    print(f"{name} full run: {len(computed) - before} batches computed")
same = read_tables(settings.work_dir / "cached-second.sqlite")["molecules"]
print("cached results equal the reference:", same.equals(reference["molecules"]))
