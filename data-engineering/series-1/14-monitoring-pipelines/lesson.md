---
title: Monitoring pipelines
summary: Structured logs, a run history, counts that must reconcile, freshness, drift in molecular properties and alerts, so a pipeline tells you when it goes wrong.
requires: rdkit, numpy, pandas, pyarrow, duckdb, matplotlib
---

A pipeline that loads a supplier's compounds every night can fail in two ways. It can crash, which
is annoying but obvious. Or it can run, finish, report success and still be wrong: a join that
drops a third of the rows, a supplier file that holds only one corner of the catalogue, a job that
quietly stopped running last Tuesday. The chemistry in each step can be perfect and the data still
untrustworthy. Monitoring is the part of data engineering that answers three plain questions after
every run: **did it run, did it do the right thing, and is the data still what we expect?**

By the end of this module you will be able to:

- write structured logs (one JSON event per line) with Python's `logging`, and keep secrets out of them;
- keep a run history in DuckDB, one row per run and per step, with an injected clock;
- reconcile counts (in = out + quarantined + duplicates) and catch a silent data-loss bug with it;
- compute throughput, quarantine rate, error rate and freshness for each run;
- measure drift in molecular properties with the population stability index and the
  Kolmogorov–Smirnov statistic;
- turn thresholds into alerts that fire once, resolve once, and do not drown you.

Everything here runs on any laptop: you need Python, RDKit, NumPy, pandas, pyarrow, DuckDB and
matplotlib. The molecules come from the course's teaching library, `chemlib`.

## Setup

Everything this lesson needs is imported and set here, so the settings can be changed in one place.
Pipeline steps report with `log`; `print` is kept for showing you results; Module 1 explains why,
and Section 2 below takes logging further.

```python
import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import duckdb
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

import chemlib

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files
WORK = Path("work")
LOG_FILE = WORK / "pipeline.log"  # the pipeline's structured log
HISTORY_DB = WORK / "monitoring.duckdb"  # the run history
PUBLISHED = WORK / "published"  # one Parquet file per successful run
DASHBOARD = WORK / "run-dashboard.svg"

# each night's supplier file: how many molecules, and the share given a recorded fault
NIGHTLY_MOLECULES = 1500
DEFECT_RATE = 0.04
LIBRARY_SEED = 100  # night n's file is chemlib.library(..., seed=LIBRARY_SEED + n)
ONE_PAGE_START = 1_666_800  # where the "one page of a sorted export" starts in the library
TIMING_SEED = 1  # seeds the simulated step durations (Section 3)
FORTNIGHT_SEED = 14  # seeds the step durations of the fortnight of runs (Section 8)

# the validation rule: elements a record may contain
ALLOWED_ELEMENTS = {"C", "H", "N", "O", "S", "F", "Cl", "Br"}

# the simulated clock: milliseconds each step takes per row, and the fortnight's timetable
MS_PER_ROW = {"validate": 0.4, "deduplicate": 0.5, "enrich": 0.05, "describe": 0.3}
FIRST_NIGHT = datetime(2027, 1, 4, 2, 0)  # 02:00 UTC on the first night
NIGHTS = 14
BUG_NIGHT = 8  # the night the inner-join bug is deployed (Section 8)
ONE_PAGE_NIGHT = 11  # the night the supplier sends one page of a sorted export
MORNING_CHECK = timedelta(hours=7)  # the freshness check runs at 09:00, 7 hours after the load

# thresholds for the checks and alerts
FRESHNESS_LIMIT = timedelta(hours=26)  # a nightly job: one day plus some slack
QUARANTINE_LIMIT = 0.10  # alert above this share of rows quarantined
PSI_BINS = 10  # bins (reference deciles) for the population stability index
PSI_LOOK, PSI_ALERT = 0.1, 0.25  # PSI: worth a look above 0.1, an alert above 0.25

# the dashboard's colours (the course's colour-blind-safe palette)
COLOURS = {"ink": "#1d2130", "violet": "#7c5cf0", "cyan": "#0e9fb5", "muted": "#8b91a1"}

RDLogger.DisableLog("rdApp.*")  # we record RDKit's failures ourselves, as quarantine reasons
matplotlib.use("Agg")  # draw figures to files, without a window
WORK.mkdir(exist_ok=True)
```

## 1. What monitoring is for

Our example is a nightly load from a compound supplier: read the file, validate each record, remove
duplicates, add the vendor's details, calculate two descriptors and publish the result as Parquet.
Tonight's file holds 1,500 molecules, with faults added at a known rate of 4% (as in Module 6);
the duplicates arrive as extra rows, so the file has 1,510 records. First, the validation rule
every record goes through. `Counter`, imported in the Setup block, tallies the reasons: it counts
and sorts in one step.

```python
def check(smiles):
    """Read one record and say why it cannot be used.

    Args:
        smiles: The record's SMILES.

    Returns:
        The molecule (None if rejected) and the quarantine reason ("" if accepted).
    """
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        return None, "unreadable"
    try:
        Chem.SanitizeMol(mol)
    except Chem.MolSanitizeException:
        return None, "impossible valence"
    if len(Chem.GetMolFrags(mol)) > 1:
        return None, "more than one component"
    if {atom.GetSymbol() for atom in mol.GetAtoms()} - ALLOWED_ELEMENTS:
        return None, "element not allowed"
    return mol, ""


tonight = chemlib.add_defects(
    chemlib.library(NIGHTLY_MOLECULES, seed=LIBRARY_SEED + 1), rate=DEFECT_RATE, seed=1
)
reasons = [check(smiles)[1] for smiles in tonight["smiles"]]
print(len(tonight), "records tonight")
for reason, count in Counter(reason or "accepted" for reason in reasons).most_common():
    print(f"{reason:25}{count:>5}")
```
```output
1510 records tonight
accepted                  1460
more than one component     20
element not allowed         10
unreadable                  10
impossible valence          10
```

None of what follows changes this chemistry. Monitoring sits around the steps: it records what
each one did, checks that the records add up, compares the data with what we expect, and tells a
person when something is off.

![The monitoring loop: each run is recorded in the run history, checked against rules, and an alert reaches a person when a check fails](figures/monitoring-loop.svg)

## 2. Structured logs

Module 1 ([Why log and not print](../01-graphs-and-matrices/#why-log-and-not-print)) gave the
reasons to log rather than print: every line has a level, so a job can run quietly in production
and verbosely when debugging, and handlers send the same line to the screen, a file and a log
service at once. Every module since has used the plain logger from its Setup block, which writes a
level and a message. A nightly job needs more from its logs than that, and this section builds it
on the same `logging` module: a formatter of our own, two handlers and a named logger for the
pipeline.

A free-text line such as `validated 1500 rows, 50 bad` is easy to write and hard to use:
to count bad rows across a month of runs, someone has to write a regular expression for it. A
**structured log** writes one JSON object per line, with the same fields every time: the time, the
level, the event, the run, the step and its counts. Log services (Elasticsearch, Loki, CloudWatch,
Datadog) index those fields; so can DuckDB, as we will see.

Two more things go into the formatter. Its time comes from a **clock object we pass in** (an
injected clock), not from the computer's clock, so a test or a lesson can set the time and get the
same output on every run. And it **removes secrets**: connection strings with passwords, API
tokens. Logs are copied, shipped and read by many people; a password written into one has leaked.

```python
class Clock:
    """The time, as the pipeline sees it: set and advanced by hand (an injected clock).

    In production the same interface would return datetime.now(timezone.utc).
    """

    def __init__(self, start):
        self.time = start

    def now(self):
        """The current time (UTC)."""
        return self.time

    def advance(self, seconds):
        """Move the clock forward."""
        self.time += timedelta(seconds=seconds)


PASSWORD_IN_URL = re.compile(r"(://[^:/@\s]+):[^@\s]+@")
SECRET_FIELD = re.compile(r"((?:password|token|api_key)=)[^&\s\"]+", re.IGNORECASE)


def redact(text):
    """Replace passwords and tokens in a line of text with ***."""
    text = PASSWORD_IN_URL.sub(r"\1:***@", text)
    return SECRET_FIELD.sub(r"\1***", text)


class JsonFormatter(logging.Formatter):
    """Format each log record as one line of JSON, with its fields, and secrets removed."""

    def __init__(self, clock):
        super().__init__()
        self.clock = clock

    def format(self, record):
        """The record as a JSON line."""
        event = {
            "time": self.clock.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        event.update(getattr(record, "fields", {}))
        return redact(json.dumps(event))


def make_logger(clock, path, screen_level=logging.INFO):
    """A logger that writes JSON lines to a file (everything) and to the screen (from a level).

    Args:
        clock: Where the times come from.
        path: The log file.
        screen_level: The lowest level to show on screen.

    Returns:
        The logger.
    """
    pipeline_log = logging.getLogger("supplier_pipeline")
    for old in list(pipeline_log.handlers):  # running this twice must not double every line
        old.close()
        pipeline_log.removeHandler(old)
    pipeline_log.setLevel(logging.INFO)
    pipeline_log.propagate = False  # its lines are JSON; keep them out of the plain Setup handler
    screen = logging.StreamHandler()
    screen.setLevel(screen_level)
    file = logging.FileHandler(path, mode="w", encoding="utf-8")
    for handler in (screen, file):
        handler.setFormatter(JsonFormatter(clock))
        pipeline_log.addHandler(handler)
    return pipeline_log


clock = Clock(FIRST_NIGHT)
pipeline_log = make_logger(clock, LOG_FILE)
```

The logger is named `supplier_pipeline`, so its lines are kept apart from the lesson's own `log`
and from the libraries' loggers, and it has two handlers: the screen shows INFO and above, the file
keeps everything the logger lets through. Now the start of a run, written to it:

```python
source = "postgresql://loader:s3cret@chemdb.example.org/suppliers"
pipeline_log.info("run started", extra={"fields": {"run_id": "run-0001", "source": source}})
pipeline_log.debug("atom-by-atom detail: below the logger's level, so it is dropped")
clock.advance(4)
n_bad = sum(reason != "" for reason in reasons)
fields = {"run_id": "run-0001", "step": "validate", "rows_in": len(tonight), "quarantined": n_bad}
pipeline_log.warning("records quarantined", extra={"fields": fields})
```
```output
{"time": "2027-01-04T02:00:00", "level": "INFO", "event": "run started", "run_id": "run-0001", "source": "postgresql://loader:***@chemdb.example.org/suppliers"}
{"time": "2027-01-04T02:00:04", "level": "WARNING", "event": "records quarantined", "run_id": "run-0001", "step": "validate", "rows_in": 1510, "quarantined": 50}
```

The password in the connection string never reached the screen or the file, and the DEBUG line
was dropped. Because every line is JSON, the log file is a table. DuckDB reads it directly, which
is how you would answer "how many warnings did last night's run write?" without a regular
expression:

```python
print(
    duckdb.sql(
        f"SELECT level, count(*) AS events FROM read_json_auto('{LOG_FILE.as_posix()}') "
        "GROUP BY level ORDER BY level"
    ).df().to_string(index=False)
)
```
```output
  level  events
   INFO       1
WARNING       1
```

## 3. A run history

Logs are a stream of events. To compare runs (was last night's run slower, did it quarantine more
than usual?) we also keep a **run history**: a table with one row per run and one per step, with
start and finish times and the counts in and out. Here it lives in DuckDB; a team that shares it
would put the same two tables in PostgreSQL (Module 4), and workflow tools such as Airflow, Dagster
and Prefect keep a table much like it for every task they run.

```python
HISTORY_DB.unlink(missing_ok=True)  # start each run of the lesson from an empty history
db = duckdb.connect(str(HISTORY_DB))
db.execute("""
    CREATE TABLE runs (
        run_id VARCHAR PRIMARY KEY, started TIMESTAMP, finished TIMESTAMP, status VARCHAR,
        rows_in INTEGER, rows_out INTEGER, quarantined INTEGER, duplicates INTEGER,
        message VARCHAR)
""")
db.execute("""
    CREATE TABLE steps (
        run_id VARCHAR, step_no INTEGER, step VARCHAR, started TIMESTAMP, finished TIMESTAMP,
        rows_in INTEGER, rows_out INTEGER, quarantined INTEGER, duplicates INTEGER)
""")
db.execute("CREATE TABLE quarantine (run_id VARCHAR, id VARCHAR, smiles VARCHAR, reason VARCHAR)")
```

Each step is a function that takes a table and returns three things: the rows it keeps, the rows
it quarantines (with a reason), and how many duplicates it removed. Keeping that shape for every
step is what makes the counts checkable later. Validation keeps each RDKit molecule in a `mol`
column, so later steps do not read the SMILES again (reading is a large share of the time).

```python
NO_ROWS = pd.DataFrame(columns=["id", "smiles", "reason"])
VENDORS = pd.DataFrame(
    {
        "vendor": ["Vendor A", "Vendor B", "Vendor C"],
        "country": ["UK", "Germany", "Ukraine"],
        "lead_time_days": [5, 7, 14],
    }
)


def validate(df):
    """Keep records that pass `check`, with their molecule; quarantine the rest with a reason."""
    checked = [check(smiles) for smiles in df["smiles"]]
    df = df.assign(mol=[mol for mol, _ in checked], reason=[reason for _, reason in checked])
    bad = df["reason"] != ""
    return df[~bad].drop(columns="reason"), df.loc[bad, ["id", "smiles", "reason"]], 0


def deduplicate(df):
    """Keep the first record of each molecule, by InChIKey (as in Module 3)."""
    keys = [Chem.MolToInchiKey(mol) for mol in df["mol"]]
    df = df.assign(inchikey=keys)
    kept = df.drop_duplicates("inchikey")
    return kept, NO_ROWS, len(df) - len(kept)


def enrich(df):
    """Add each vendor's country and lead time; quarantine records from an unknown vendor."""
    merged = df.merge(VENDORS, on="vendor", how="left", indicator=True)
    unknown = merged["_merge"] == "left_only"
    quarantined = merged.loc[unknown, ["id", "smiles"]].assign(reason="unknown vendor")
    return merged[~unknown].drop(columns="_merge"), quarantined, 0


def describe(df):
    """Add molecular weight and logP, the two properties we watch for drift."""
    df = df.assign(
        mw=[round(Descriptors.MolWt(mol), 2) for mol in df["mol"]],
        logp=[round(Descriptors.MolLogP(mol), 2) for mol in df["mol"]],
    )
    return df, NO_ROWS, 0
```

The runner calls the steps in order and records each one. The work is real; the time each step
takes is simulated (each step's milliseconds per row, `MS_PER_ROW` in the Setup block, give or
take a seeded random 20%, move the clock on), so the run history comes out the same on every
computer. In production the clock is the real one and nothing else changes.

```python
def run_step(run_id, step_no, name, func, df, rng):
    """Run one step, move the clock on, and record what the step did.

    Args:
        run_id: The run.
        step_no: The step's position in the run.
        name: The step's name.
        func: The step: a table in; kept rows, quarantined rows and duplicates removed out.
        df: The rows going in.
        rng: The random generator for the simulated duration.

    Returns:
        The rows the step kept.
    """
    started = clock.now()
    kept, quarantined, duplicates = func(df)
    clock.advance(len(df) * MS_PER_ROW[name] / 1000 * rng.uniform(0.8, 1.2))
    db.execute(
        "INSERT INTO steps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [run_id, step_no, name, started, clock.now(), len(df), len(kept), len(quarantined),
         duplicates],
    )
    if len(quarantined):
        db.execute("INSERT INTO quarantine SELECT ?, id, smiles, reason FROM quarantined", [run_id])
    pipeline_log.info("step finished", extra={"fields": {
        "run_id": run_id, "step": name, "rows_in": len(df), "rows_out": len(kept),
        "quarantined": len(quarantined), "duplicates": duplicates}})
    return kept
```

DuckDB's `FROM quarantined` reads the pandas table of that name straight from Python. Now one run,
with the log on screen showing warnings only, so the per-step lines go to the file:

```python
STEPS = [("validate", validate), ("deduplicate", deduplicate), ("enrich", enrich),
         ("describe", describe)]


def run_pipeline(run_id, batch, steps, rng):
    """Run every step over a batch and record the run (status, counts) in the run history."""
    db.execute("INSERT INTO runs (run_id, started, status) VALUES (?, ?, 'running')",
               [run_id, clock.now()])
    pipeline_log.info("run started", extra={"fields": {"run_id": run_id, "rows": len(batch)}})
    df = batch
    for step_no, (name, func) in enumerate(steps, start=1):
        df = run_step(run_id, step_no, name, func, df, rng)
    return df


pipeline_log = make_logger(clock, LOG_FILE, screen_level=logging.WARNING)
published = run_pipeline("run-0001", tonight, STEPS, np.random.default_rng(TIMING_SEED))
print(db.sql("SELECT step, rows_in, rows_out, quarantined, duplicates FROM steps "
             "WHERE run_id = 'run-0001' ORDER BY step_no").df().to_string(index=False))
```
```output
       step  rows_in  rows_out  quarantined  duplicates
   validate     1510      1460           50           0
deduplicate     1460      1449            0          11
     enrich     1449      1449            0           0
   describe     1449      1449            0           0
```

## 4. Counts that reconcile

Every row that enters a step must leave it by one of three doors: kept, quarantined or removed as a
duplicate. So for each step, **in = out + quarantined + duplicates**, and each step's input must be
the previous step's output. This is **reconciliation**, the oldest check in data engineering
(accountants call it balancing the books), and it is cheap: it needs only the counts we already
record. The check below fails loudly, with an exception, rather than writing a warning nobody
reads:

```python
class ReconciliationError(Exception):
    """The counts of a run do not add up: rows were lost or invented."""


def reconcile(run_id):
    """Check that every step's rows are accounted for and that the steps chain together.

    Raises:
        ReconciliationError: listing every step whose counts do not add up.
    """
    problems = db.execute("""
        SELECT step, rows_in, rows_out, quarantined, duplicates,
               rows_in - rows_out - quarantined - duplicates AS unaccounted,
               lag(rows_out) OVER (ORDER BY step_no) AS previous_out
        FROM steps WHERE run_id = ?
        ORDER BY step_no
    """, [run_id]).df()
    lost = problems["unaccounted"] != 0
    broken_chain = problems["previous_out"].notna() & (
        problems["rows_in"] != problems["previous_out"])
    messages = [f"{row.step}: {row.rows_in} in, {row.rows_out} out, {row.quarantined} quarantined,"
                f" {row.duplicates} duplicates, {row.unaccounted} unaccounted for"
                for row in problems[lost | broken_chain].itertuples()]
    if messages:
        raise ReconciliationError("; ".join(messages))


reconcile("run-0001")
log.info("%s reconciles", "run-0001")
```
```output
INFO run-0001 reconciles
```

Now the bug it exists for. Someone refreshes the vendor table from a spreadsheet that has not yet
caught up with Vendor C, and rewrites the enrichment step with pandas' `merge`, whose default is an
**inner join**: rows with no matching vendor simply disappear. Nothing crashes, the step "succeeds",
and the output looks like a normal, slightly small table.

```python
VENDORS_FROM_SPREADSHEET = VENDORS[VENDORS["vendor"] != "Vendor C"]


def enrich_inner_join(df):
    """The buggy version: merge's default inner join drops rows from vendors not in the table."""
    return df.merge(VENDORS_FROM_SPREADSHEET, on="vendor"), NO_ROWS, 0


buggy_steps = [("validate", validate), ("deduplicate", deduplicate),
               ("enrich", enrich_inner_join), ("describe", describe)]
clock.advance(600)
lost_rows = run_pipeline("run-0001-bug", tonight, buggy_steps, np.random.default_rng(TIMING_SEED))
print("rows published:", len(lost_rows), "instead of", len(published))
try:
    reconcile("run-0001-bug")
except ReconciliationError as err:
    print("ReconciliationError:", err)
```
```output
rows published: 955 instead of 1449
ReconciliationError: enrich: 1449 in, 955 out, 0 quarantined, 0 duplicates, 494 unaccounted for
```

A third of the batch would have vanished without a trace. Reconciliation names the step and the
number. The fix is the version we started with: a left join (`how="left"`), with unmatched rows
quarantined under a reason, so the counts add up and the quarantine rate (next section) shows the
missing vendor the same night.

The runner's last job is to reconcile before publishing, and to close the run's row with its totals
and status. Publishing only after the check means a run that fails reconciliation writes nothing
downstream:

```python
def finish_run(run_id, df, status, message=""):
    """Close a run: its finish time, status and totals (summed from its steps)."""
    db.execute("""
        UPDATE runs SET finished = ?, status = ?, message = ?,
            rows_in = (SELECT rows_in FROM steps WHERE run_id = ? AND step_no = 1),
            rows_out = ?,
            quarantined = (SELECT sum(quarantined) FROM steps WHERE run_id = ?),
            duplicates = (SELECT sum(duplicates) FROM steps WHERE run_id = ?)
        WHERE run_id = ?
    """, [clock.now(), status, message, run_id, len(df), run_id, run_id, run_id])


def run_and_publish(run_id, batch, steps, rng):
    """Run, reconcile, and only then publish the result as Parquet."""
    df = run_pipeline(run_id, batch, steps, rng)
    try:
        reconcile(run_id)
    except ReconciliationError as err:
        finish_run(run_id, df.iloc[0:0], "failed", str(err))
        pipeline_log.error("run failed reconciliation; nothing published",
                           extra={"fields": {"run_id": run_id}})
        return None
    df = df.drop(columns="mol")  # RDKit objects stay in memory; the SMILES is what we store
    PUBLISHED.mkdir(exist_ok=True)
    df.to_parquet(PUBLISHED / f"{run_id}.parquet", index=False)
    finish_run(run_id, df, "succeeded")
    return df
```

## 5. Metrics: throughput, rates and freshness

A few numbers per run, read from the run history, describe a pipeline's health:

- **throughput**, rows per second, which shows a run getting slower long before it times out;
- **quarantine rate**, the share of rows rejected; a sudden rise usually means the input changed,
  not the chemistry;
- **error rate**, the share of recent runs that failed;
- **freshness**, the time since the last successful run, against an agreed limit. For a nightly
  job, 26 hours is a common choice: one day plus some slack.

Freshness catches what no per-run check can: the run that never happened. If the scheduler stops,
there is no failed run to alert on, only data quietly growing old.

The limit is `FRESHNESS_LIMIT` in the Setup block.

```python
def freshness(now):
    """Time since the last successful run finished (None if there has never been one)."""
    last = db.execute("SELECT max(finished) FROM runs WHERE status = 'succeeded'").fetchall()[0][0]
    return None if last is None else now - last


clock.advance(600)
run_and_publish("run-0002", tonight, STEPS, np.random.default_rng(TIMING_SEED + 1))
metrics = db.sql("""
    SELECT run_id, status,
           round(rows_in / epoch(finished - started)) AS rows_per_s,
           round(100 * quarantined / rows_in, 1) AS quarantined_pct
    FROM runs WHERE status <> 'running' ORDER BY started
""").df()
print(metrics.to_string(index=False))
clock.advance(30 * 3600)  # thirty hours later, and no run since
age = freshness(clock.now())
print(f"freshness: {age.total_seconds() / 3600:.1f} h; within the limit: {age <= FRESHNESS_LIMIT}")
```
```output
  run_id    status  rows_per_s  quarantined_pct
run-0002 succeeded       908.0              3.3
freshness: 30.0 h; within the limit: False
```

The two first runs above were not closed by `finish_run` (we ran them before writing it), so they
stay `running` and the query leaves them out. In a real history, a run stuck in `running` for hours
is itself worth an alert: the process died without recording anything.

## 6. Drift in molecular properties

A run can reconcile perfectly and still deliver the wrong data. Suppose a supplier's export was
sorted by structure and only one page of it was sent: every molecule is valid, the counts add up,
and every molecule carries a phenyl and a fluorophenyl group. Models trained on the old data, and
chemists choosing compounds from it, would be misled. Watching the **distribution** of a few
properties catches this.

The **population stability index** (PSI) compares two distributions. Cut the reference into ten
bins with equal numbers of molecules (its deciles), count the share of the new batch in each bin,
and add up `(new - ref) × ln(new / ref)` over the bins. Identical distributions give 0; the bigger
the shift, the bigger the number. The **Kolmogorov–Smirnov statistic** is the largest vertical gap
between the two cumulative distributions, from 0 (the same) to 1 (no overlap). Both are a few lines
of NumPy:

```python
def psi(reference, new, bins=PSI_BINS):
    """Population stability index of `new` against `reference`, on the reference's quantiles."""
    edges = np.quantile(reference, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf  # catch values beyond the reference's range
    ref_share = np.histogram(reference, edges)[0] / len(reference)
    new_share = np.histogram(new, edges)[0] / len(new)
    ref_share = np.clip(ref_share, 1e-4, None)  # an empty bin would give log(0)
    new_share = np.clip(new_share, 1e-4, None)
    return float(np.sum((new_share - ref_share) * np.log(new_share / ref_share)))


def ks(reference, new):
    """Two-sample Kolmogorov-Smirnov statistic: the largest gap between the two CDFs."""
    values = np.concatenate([reference, new])
    cdf_ref = np.searchsorted(np.sort(reference), values, side="right") / len(reference)
    cdf_new = np.searchsorted(np.sort(new), values, side="right") / len(new)
    return float(np.max(np.abs(cdf_ref - cdf_new)))


def properties(smiles):
    """Molecular weight and logP of a list of SMILES, as two arrays."""
    mols = [Chem.MolFromSmiles(s) for s in smiles]
    return (np.array([Descriptors.MolWt(m) for m in mols]),
            np.array([Descriptors.MolLogP(m) for m in mols]))


reference = published  # run-0001's output, checked by a chemist: the reference
ordinary = properties(chemlib.library(NIGHTLY_MOLECULES, seed=LIBRARY_SEED + 2)["smiles"])
one_page_batch = next(
    chemlib.stream(NIGHTLY_MOLECULES, batch=NIGHTLY_MOLECULES, start=ONE_PAGE_START)
)
one_page = properties(one_page_batch["smiles"])
print(f"{'batch':10}{'PSI MW':>8}{'PSI logP':>10}{'KS MW':>8}{'KS logP':>9}")
for name, (mw, logp) in [("ordinary", ordinary), ("one page", one_page)]:
    print(f"{name:10}{psi(reference['mw'], mw):8.3f}{psi(reference['logp'], logp):10.3f}"
          f"{ks(reference['mw'], mw):8.3f}{ks(reference['logp'], logp):9.3f}")
```
```output
batch       PSI MW  PSI logP   KS MW  KS logP
ordinary     0.008     0.008   0.032    0.020
one page     2.576     5.935   0.492    0.788
```

![Molecular weight of the reference, an ordinary new batch and the one-page batch: the ordinary batch overlaps the reference; the one-page batch is shifted to heavier molecules](figures/drift-histograms.svg)

The usual reading of PSI comes from credit scoring: **below 0.1, no real change; 0.1 to 0.25, a
moderate shift worth a look; above 0.25, a significant shift**. These are rules of thumb, not
statistics: PSI grows with the number of bins and, for small batches, with sampling noise, so check
what your own ordinary batches score (here, about 0.01) before trusting any threshold. The KS
statistic comes with a p-value (`scipy.stats.ks_2samp`), but with thousands of molecules almost any
difference is "significant"; the size of the gap is the more useful number. Molecular weight and
logP are a start; heavy-atom count, ring count, fraction of sp3 carbons and the share of each
scaffold are other common choices.

## 7. Alerts that people will read

A check that nobody hears about is not monitoring. An **alert rule** pairs a metric with a
threshold and a severity. The common practice, from site reliability engineering, is to keep two
kinds: a **page**, which wakes someone because the data is wrong or missing now, and a **ticket**,
which can wait for working hours. The main risk is **alert fatigue**: a rule that fires every night
for something harmless trains people to ignore all of them. So alert on symptoms that need a person
(a failed run, stale data, a drifted batch), not on every warning in the log, and notify when a
rule **starts** firing and when it **resolves**, not on every check in between.

The thresholds come from the Setup block, so the rules and the checks above share one value each.

```python
class Rule(NamedTuple):
    """Alert when `metric` is above `threshold`."""

    name: str
    metric: str
    threshold: float
    severity: str  # "page" (now) or "ticket" (working hours)


freshness_hours = FRESHNESS_LIMIT.total_seconds() / 3600
RULES = [
    Rule("run failed", "failed", 0.5, "page"),
    Rule(f"data older than {freshness_hours:.0f} hours", "hours_since_success", freshness_hours,
         "page"),
    Rule(f"quarantine rate above {QUARANTINE_LIMIT:.0%}", "quarantine_rate", QUARANTINE_LIMIT,
         "ticket"),
    Rule(f"molecular weight drift (PSI above {PSI_ALERT})", "psi_mw", PSI_ALERT, "ticket"),
    Rule(f"logP drift (PSI above {PSI_ALERT})", "psi_logp", PSI_ALERT, "ticket"),
]


class Alerter:
    """Evaluate rules and notify only when a rule starts or stops firing."""

    def __init__(self, rules):
        self.rules = rules
        self.firing = set()

    def update(self, metrics):
        """Check every rule whose metric is in `metrics`; notify on changes."""
        for rule in self.rules:
            if rule.metric not in metrics:
                continue
            now_firing = metrics[rule.metric] > rule.threshold
            if now_firing and rule.name not in self.firing:
                self.firing.add(rule.name)
                self.notify(rule, "FIRING", metrics)
            elif not now_firing and rule.name in self.firing:
                self.firing.remove(rule.name)
                self.notify(rule, "resolved", metrics)

    def notify(self, rule, state, metrics):
        """Send one alert. Here it is a log line; a chat webhook or on-call service is one call more.

        With a webhook it would be: requests.post(url, json={"text": message}, timeout=10).
        """
        level = logging.ERROR if rule.severity == "page" and state == "FIRING" else logging.WARNING
        fields = {"alert": rule.name, "state": state, "severity": rule.severity,
                  "value": round(float(metrics[rule.metric]), 3), "run_id": metrics.get("run_id")}
        pipeline_log.log(level, "alert", extra={"fields": fields})
```

In a team the `notify` method posts to a chat channel (Slack and Microsoft Teams both accept a JSON
message at a webhook address) or to an on-call service (PagerDuty, Opsgenie) that pages whoever is
on the rota. The webhook address is a secret too: it belongs in an environment variable, never in
the code or the logs.

## 8. A fortnight of runs

Now everything together, over fourteen simulated nights. Each night at 02:00 a new file of 1,500
molecules arrives (a fresh sample of the library, with 4% faults) and the pipeline runs. Two nights
go wrong, on purpose: on **night 8** the inner-join bug from Section 4 is deployed, and on **night
11** the supplier sends the one-page batch from Section 6. Every morning at 09:00 a separate check
looks at freshness, as a scheduler would. Only warnings and errors are printed; the file has
everything.

```python
for table in ("runs", "steps", "quarantine"):  # a fresh history for the fortnight
    db.execute(f"DELETE FROM {table}")
db.execute("CREATE TABLE drift (run_id VARCHAR, psi_mw DOUBLE, psi_logp DOUBLE, "
           "ks_mw DOUBLE, ks_logp DOUBLE)")
alerter = Alerter(RULES)
rng = np.random.default_rng(FORTNIGHT_SEED)

for night in range(1, NIGHTS + 1):
    run_id = f"run-{night:04d}"
    clock.time = FIRST_NIGHT + timedelta(days=night - 1)
    if night == ONE_PAGE_NIGHT:  # one page of a sorted export
        batch = one_page_batch
    else:
        batch = chemlib.library(NIGHTLY_MOLECULES, seed=LIBRARY_SEED + night)
    batch = chemlib.add_defects(batch, rate=DEFECT_RATE, seed=night)
    steps = buggy_steps if night == BUG_NIGHT else STEPS
    out = run_and_publish(run_id, batch, steps, rng)
    run = db.execute("SELECT status, quarantined / rows_in FROM runs WHERE run_id = ?",
                     [run_id]).fetchall()[0]
    metrics = {"run_id": run_id, "failed": run[0] == "failed", "quarantine_rate": run[1]}
    if out is not None:
        drift = [psi(reference["mw"], out["mw"]), psi(reference["logp"], out["logp"]),
                 ks(reference["mw"], out["mw"]), ks(reference["logp"], out["logp"])]
        db.execute("INSERT INTO drift VALUES (?, ?, ?, ?, ?)", [run_id, *drift])
        metrics.update(psi_mw=drift[0], psi_logp=drift[1])
    alerter.update(metrics)
    clock.time = FIRST_NIGHT + timedelta(days=night - 1) + MORNING_CHECK  # 09:00: freshness
    age = freshness(clock.now())
    alerter.update({"run_id": run_id, "hours_since_success": age.total_seconds() / 3600})
```
```output
{"time": "2027-01-11T02:00:01", "level": "ERROR", "event": "run failed reconciliation; nothing published", "run_id": "run-0008"}
{"time": "2027-01-11T02:00:01", "level": "ERROR", "event": "alert", "alert": "run failed", "state": "FIRING", "severity": "page", "value": 1.0, "run_id": "run-0008"}
{"time": "2027-01-11T09:00:00", "level": "ERROR", "event": "alert", "alert": "data older than 26 hours", "state": "FIRING", "severity": "page", "value": 31.0, "run_id": "run-0008"}
{"time": "2027-01-12T02:00:02", "level": "WARNING", "event": "alert", "alert": "run failed", "state": "resolved", "severity": "page", "value": 0.0, "run_id": "run-0009"}
{"time": "2027-01-12T09:00:00", "level": "WARNING", "event": "alert", "alert": "data older than 26 hours", "state": "resolved", "severity": "page", "value": 6.999, "run_id": "run-0009"}
{"time": "2027-01-14T02:00:01", "level": "WARNING", "event": "alert", "alert": "molecular weight drift (PSI above 0.25)", "state": "FIRING", "severity": "ticket", "value": 2.574, "run_id": "run-0011"}
{"time": "2027-01-14T02:00:01", "level": "WARNING", "event": "alert", "alert": "logP drift (PSI above 0.25)", "state": "FIRING", "severity": "ticket", "value": 5.925, "run_id": "run-0011"}
{"time": "2027-01-15T02:00:01", "level": "WARNING", "event": "alert", "alert": "molecular weight drift (PSI above 0.25)", "state": "resolved", "severity": "ticket", "value": 0.018, "run_id": "run-0012"}
{"time": "2027-01-15T02:00:01", "level": "WARNING", "event": "alert", "alert": "logP drift (PSI above 0.25)", "state": "resolved", "severity": "ticket", "value": 0.009, "run_id": "run-0012"}
```

Night 8 paged twice: the run failed, and by the morning check the data was 31 hours old. Both
resolved after night 9, and each alert was sent once, not every night. Night 11's batch passed
every validation rule and reconciled, and only the drift rules caught it. The run history, from
DuckDB:

```python
history = db.sql("""
    SELECT r.run_id, r.status, r.rows_in, r.rows_out,
           round(100 * r.quarantined / r.rows_in, 1) AS quarantined_pct, r.duplicates,
           round(d.psi_mw, 3) AS psi_mw, round(d.psi_logp, 3) AS psi_logp
    FROM runs r LEFT JOIN drift d USING (run_id)
    ORDER BY r.run_id
""").df()
print(history.to_string(index=False))
failed = (history["status"] == "failed").sum()
print(f"error rate over the fortnight: {failed}/{len(history)} runs failed")
```
```output
  run_id    status  rows_in  rows_out  quarantined_pct  duplicates  psi_mw  psi_logp
run-0001 succeeded     1510      1449              3.3          11   0.000     0.000
run-0002 succeeded     1510      1450              3.3          10   0.008     0.009
run-0003 succeeded     1510      1450              3.3          10   0.015     0.010
run-0004 succeeded     1510      1450              3.3          10   0.023     0.015
run-0005 succeeded     1510      1450              3.3          10   0.011     0.012
run-0006 succeeded     1510      1449              3.3          11   0.033     0.006
run-0007 succeeded     1510      1449              3.3          11   0.010     0.024
run-0008    failed     1510         0              3.3          10     NaN       NaN
run-0009 succeeded     1510      1450              3.3          10   0.010     0.006
run-0010 succeeded     1510      1450              3.3          10   0.011     0.016
run-0011 succeeded     1510      1453              3.1          10   2.574     5.925
run-0012 succeeded     1510      1450              3.3          10   0.018     0.009
run-0013 succeeded     1510      1449              3.3          11   0.013     0.015
run-0014 succeeded     1510      1449              3.3          11   0.009     0.005
error rate over the fortnight: 1/14 runs failed
```

Night 1 is the reference itself, so its PSI is 0. The ordinary nights score between 0.005 and
0.033, well below 0.1, and night 11 scores 2.6 and 5.9. The quarantine rate stayed at about 3.3%
every night, so the 10% rule never fired: a threshold set above the normal level, so that it stays
quiet until something changes.

A small dashboard drawn from the same tables puts the fortnight on one page: rows in and out, the
quarantine rate, and the drift scores against the two PSI thresholds.

```python
def dashboard(db, path):
    """Draw the run history (counts, quarantine rate, drift) as one SVG figure.

    Args:
        db: The DuckDB connection holding the runs and drift tables.
        path: Where to save the figure.
    """
    runs = db.sql("SELECT * FROM runs LEFT JOIN drift USING (run_id) ORDER BY run_id").df()
    night = np.arange(1, len(runs) + 1)
    fig, (top, middle, bottom) = plt.subplots(3, 1, figsize=(7, 7.5), sharex=True)
    top.bar(night - 0.2, runs["rows_in"], 0.4, color=COLOURS["muted"], label="rows in")
    top.bar(night + 0.2, runs["rows_out"], 0.4, color=COLOURS["violet"], label="rows published")
    for n in night[runs["status"] == "failed"]:
        top.annotate("failed:\nnothing\npublished", (n + 0.2, 60), ha="center", fontsize=8,
                     color=COLOURS["ink"])
    top.set_ylabel("rows")
    top.set_ylim(0, 2000)
    top.legend(loc="upper center", ncol=2, fontsize=8, frameon=False)
    middle.plot(night, 100 * runs["quarantined"] / runs["rows_in"], "o-", color=COLOURS["cyan"])
    middle.axhline(100 * QUARANTINE_LIMIT, color=COLOURS["muted"], linestyle="--", linewidth=1)
    middle.text(0.6, 100 * QUARANTINE_LIMIT + 0.3, "alert threshold", fontsize=8, color=COLOURS["muted"])
    middle.set_ylabel("quarantined (%)")
    middle.set_ylim(0, 12)
    bottom.plot(night, runs["psi_mw"], "o-", color=COLOURS["violet"], label="molecular weight")
    bottom.plot(night, runs["psi_logp"], "s-", color=COLOURS["cyan"], label="logP")
    for level, text in [(PSI_LOOK, f"{PSI_LOOK}: look"), (PSI_ALERT, f"{PSI_ALERT}: alert")]:
        bottom.axhline(level, color=COLOURS["muted"], linestyle="--", linewidth=1)
        bottom.text(0.6, level * 1.08, text, fontsize=8, va="bottom", color=COLOURS["muted"])
    bottom.set_yscale("symlog", linthresh=0.1)
    bottom.set_ylim(0, 10)
    bottom.set_ylabel("PSI against reference")
    bottom.set_xlabel("night")
    bottom.set_xticks(night)
    bottom.legend(loc="upper center", ncol=2, fontsize=8, frameon=False)
    for ax in (top, middle, bottom):
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


dashboard(db, DASHBOARD)
db.close()
```

![A fortnight of runs: rows in and published per night (night 8 failed and published nothing), the quarantine rate (steady, below its 10% threshold), and PSI for molecular weight and logP (night 11 far above 0.25)](figures/run-dashboard.svg)

Grafana, Metabase or Superset would draw the same panels live from the same run-history tables;
the point is that the tables exist and every run writes to them.

## Try it yourself

The homework for this module is in `homework.md`: a few questions answered by running code like the
code above. Answers are published after the cohort's deadline.

## Further reading

- Ewaschuk, R. Monitoring distributed systems. In Beyer, B., Jones, C., Petoff, J. & Murphy, N. R.
  (eds.) (2016). *Site Reliability Engineering*. O'Reilly; free online edition.
  <https://sre.google/sre-book/monitoring-distributed-systems/>
- Breck, E., Cai, S., Nielsen, E., Salib, M. & Sculley, D. (2017). The ML test score: a rubric for
  ML production readiness and technical debt reduction. *2017 IEEE International Conference on Big
  Data (Big Data)*, 1123–1132. <https://doi.org/10.1109/BigData.2017.8258038>
- Yurdakul, B. (2018). *Statistical properties of population stability index*. Doctoral
  dissertation, Western Michigan University. <https://scholarworks.wmich.edu/dissertations/3208>
- The Python documentation. *logging: Logging facility for Python*, and the *Logging Cookbook*.
  <https://docs.python.org/3/library/logging.html>,
  <https://docs.python.org/3/howto/logging-cookbook.html>
- The DuckDB documentation. *JSON overview* (reading JSON lines files such as structured logs).
  <https://duckdb.org/docs/stable/data/json/overview>
