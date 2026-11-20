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
import math
import os
import random
import sqlite3
from pathlib import Path

import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

from chemlib import add_defects, library

RDLogger.DisableLog("rdApp.*")  # bad molecules are reported in a table, not as log messages
Path("work").mkdir(exist_ok=True)

# ---- 2. Settings checked before a run starts ----
from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunSettings(BaseSettings):
    """Everything a run needs to know, checked before it starts.

    Each setting can be overridden by an environment variable: CHEMRUN_BATCH_SIZE, and so on.
    """

    model_config = SettingsConfigDict(env_prefix="CHEMRUN_")

    n_molecules: int = Field(12_000, gt=0)
    batch_size: int = Field(1_000, gt=0)
    work_dir: Path = Path("work")
    max_attempts: int = Field(5, ge=1, le=10)
    first_delay_s: float = Field(0.5, gt=0)
    max_delay_s: float = Field(30.0, gt=0)

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
    print(f"refused to start: {err.error_count()} bad settings")
    for problem in err.errors():
        print(f"  {problem['loc'][0]}: {problem['msg']} (got {problem['input']!r})")
finally:
    del os.environ["CHEMRUN_BATCH_SIZE"], os.environ["CHEMRUN_WORK_DIR"]

# ---- 3. One molecule at a time: quarantine, don't crash ----
ALLOWED_ELEMENTS = {"C", "N", "O", "S", "F", "Cl", "Br"}


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
source = add_defects(library(settings.n_molecules, seed=10), rate=0.03, seed=11)
source = source.sort_values("id").reset_index(drop=True)
n_batches = math.ceil(len(source) / settings.batch_size)
print(f"{len(source):,} records in {n_batches} batches of up to {settings.batch_size:,}")
print(source["defect"].replace("", "(none)").value_counts().to_string())
good, bad = prepare_batch(source.iloc[: settings.batch_size])
print(f"prepared {len(good)}, quarantined {len(bad)}")
print(bad["reason"].value_counts().to_string())

# ---- 4. Retries with back-off and jitter ----
class TransientError(Exception):
    """A failure that may go away if we wait and try again: a timeout, a busy server."""


class FlakyService:
    """A stand-in for a remote service that fails its first `failures` calls, then works."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    def __call__(self, smiles: str) -> dict:
        """Prepare a molecule, unless this is one of the calls that fail."""
        self.calls += 1
        if self.calls <= self.failures:
            raise TransientError(f"call {self.calls}: service busy")
        return prepare(smiles)
def with_retries(func, *args, max_attempts=5, first_delay=0.5, max_delay=30.0,
                 rng=random.Random(), sleep=None):
    """Call func(*args), retrying transient failures with exponential back-off and full jitter.

    Args:
        func: What to call.
        *args: Its arguments.
        max_attempts: How many calls in all before giving up.
        first_delay: The ceiling of the first wait, in seconds; it doubles after each failure.
        max_delay: The largest ceiling, in seconds.
        rng: The random number generator for the jitter.
        sleep: How to wait (time.sleep in real use).

    Returns:
        What func returns.

    Raises:
        TransientError: If every attempt failed. Any other error is raised at once, unretried.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args)
        except TransientError as err:
            if attempt == max_attempts:
                raise
            ceiling = min(max_delay, first_delay * 2 ** (attempt - 1))
            delay = rng.uniform(0, ceiling)
            print(f"  attempt {attempt} failed ({err}); waiting {delay:.2f} s of up to {ceiling} s")
            sleep(delay)


waits = []
service = FlakyService(failures=3)
result = with_retries(service, "CC(=O)Oc1ccccc1C(=O)O", rng=random.Random(1), sleep=waits.append)
print(f"succeeded on call {service.calls}: aspirin, MW {result['mol_wt']}")
print(f"waited {sum(waits):.2f} s in all")
try:
    with_retries(FlakyService(failures=10), "CCO", rng=random.Random(1), sleep=waits.append)
except TransientError as err:
    print(f"gave up: {err}")

broken = FlakyService(failures=0)
try:
    with_retries(broken, "C1CC", rng=random.Random(1), sleep=waits.append)
except BadMolecule as err:
    print(f"not retried ({broken.calls} call): {err}")

# ---- The same with tenacity ----
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

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


random.seed(1)  # tenacity draws its jitter from Python's random module
print(prepare_remotely("CN1C=NC2=C1C(=O)N(C(=O)N2C)C"))
print(f"{service.calls} calls; waits of {[round(w, 2) for w in waits]} s")

# ---- 5. Idempotent batches ----
naive = sqlite3.connect(Path("work") / "naive.sqlite")
naive.execute("DROP TABLE IF EXISTS molecules")
for attempt in (1, 2):
    good.to_sql("molecules", naive, if_exists="append", index=False)
    count = naive.execute("SELECT COUNT(*), COUNT(DISTINCT id) FROM molecules").fetchone()
    print(f"after writing batch 0 {attempt}x: {count[0]} rows, {count[1]} different molecules")
naive.close()
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


demo_path = Path("work") / "demo.sqlite"
demo_path.unlink(missing_ok=True)
con = connect(demo_path)
for attempt in (1, 2):
    save_batch(con, good, bad)
    print(f"after writing batch 0 {attempt}x: {count_rows(con)}")
con.close()

# ---- 6. Checkpoints, crashes and resuming ----
class SimulatedCrash(Exception):
    """Stands in for the process dying: power cut, out of memory, a server restart."""


def run_pipeline(source: pd.DataFrame, db_path: Path, batch_size: int,
                 prepare_fn=prepare_batch, crash_at: int | None = None) -> list[int]:
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
    con = connect(db_path)
    done = {row[0] for row in con.execute("SELECT batch FROM checkpoints")}
    ran = []
    try:
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
    finally:
        con.close()
    return ran
reference_path = settings.work_dir / "reference.sqlite"
reference_path.unlink(missing_ok=True)
ran = run_pipeline(source, reference_path, settings.batch_size)
print(f"ran batches {ran[0]} to {ran[-1]}")
with sqlite3.connect(reference_path) as con:
    print(count_rows(con))
run_path = settings.work_dir / "run.sqlite"
run_path.unlink(missing_ok=True)
try:
    run_pipeline(source, run_path, settings.batch_size, crash_at=7)
except SimulatedCrash as err:
    print(f"crashed: {err}")
with sqlite3.connect(run_path) as con:
    print(count_rows(con))
    finished = [row[0] for row in con.execute("SELECT batch FROM checkpoints ORDER BY batch")]
print(f"checkpointed batches: {finished}")
ran = run_pipeline(source, run_path, settings.batch_size)
print(f"resumed: skipped {len(finished)} finished batches, ran batches {ran}")
with sqlite3.connect(run_path) as con:
    print(count_rows(con))
def read_tables(db_path: Path) -> dict[str, pd.DataFrame]:
    """Every table of a run's database, sorted by its key, for comparison."""
    keys = {"molecules": "id", "quarantine": "id", "checkpoints": "batch"}
    with sqlite3.connect(db_path) as con:
        return {t: pd.read_sql(f"SELECT * FROM {t} ORDER BY {k}", con) for t, k in keys.items()}


reference, resumed = read_tables(reference_path), read_tables(run_path)
for table in reference:
    pd.testing.assert_frame_equal(reference[table], resumed[table])  # raises if they differ
    print(f"{table}: identical ({len(reference[table]):,} rows)")
caught = source.merge(reference["quarantine"][["id", "reason"]], on="id", how="left")
caught["reason"] = caught["reason"].fillna("(prepared)")
print(pd.crosstab(caught["defect"].replace("", "(none)"), caught["reason"]).to_string())

# ---- 7. Atomic writes ----
import csv

molecules = reference["molecules"]
export_path = settings.work_dir / "molecules.csv"


def write_rows(handle, table: pd.DataFrame, crash_after: int | None = None) -> None:
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
        write_rows(handle, molecules, crash_after=4_000)
except SimulatedCrash as err:
    print(f"crashed: {err}")
print(f"the file exists: {export_path.exists()}, rows a reader sees: {len(pd.read_csv(export_path)):,}")
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
    write_csv_atomic(molecules, export_path, crash_after=4_000)
except SimulatedCrash as err:
    print(f"crashed: {err}")
print(f"after the crash: {len(pd.read_csv(export_path)):,} rows, "
      f"temporary file left behind: {export_path.with_name('molecules.csv.tmp').exists()}")

# ---- 8. Cached results with joblib.Memory ----
from joblib import Memory

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
