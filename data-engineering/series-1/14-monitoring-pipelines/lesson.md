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

- write a log (the job's own diary of what it did) as one line of JSON per event, so a program can
  read it back, and keep passwords out of it;
- keep a run history: a small database table with one row for every run and every step;
- check that every record is accounted for (records in = records out + rejected + duplicates), and
  use that check to catch a bug that quietly loses a third of the data;
- work out, for each run, how fast it was, how many records it rejected, and how old the newest
  data is;
- tell when a new batch of molecules looks different from the usual ones (drift in molecular
  weight and logP);
- turn these checks into alerts that tell a person once when something goes wrong, and once when
  it is fixed.

This module uses what earlier modules built: the validation rules and the faults that `chemlib`
adds ([Module 6](../06-validating-molecules/)), InChIKeys for finding duplicates
([Module 3](../03-files-and-identity/)), Parquet files and DuckDB
([Module 8](../08-larger-than-memory/)), and logging ([Module 1](../01-graphs-and-matrices/)).

The lesson uses these Python packages (code other people wrote, which you load with `import`):

- **RDKit**, for reading molecules and calculating their properties;
- **NumPy** and **pandas**, for arrays of numbers and for tables;
- **pyarrow**, which pandas uses to write **Parquet** files (a compact file format for tables);
- **DuckDB**, a small database that lives in one file on your computer and answers questions
  written in SQL, the standard language for asking a database for data;
- **matplotlib**, for drawing figures.

The molecules come from the course's teaching library, `chemlib`, which makes realistic
drug-like molecules on demand. Everything here runs in Colab or on any laptop.

A few words come up again and again. A **run** is one execution of the pipeline, start to finish:
here, one night's load. A **step** is one stage inside a run (validate, deduplicate and so on).
To **quarantine** a record is to set it aside, with the reason, instead of deleting it, so a person
can look at it later. **JSON** is a way of writing data as text that both people and programs can
read: `{"step": "validate", "rows_in": 1510}` is one JSON object, a set of named fields.

## Setup

Everything this lesson needs is imported and set here, so the settings can be changed in one place.
Pipeline steps report with `log`; `print` is kept for showing you results; Module 1 explains why,
and Section 2 below takes logging further. Besides the packages above, the block imports some parts
of Python itself: `json` (writes and reads JSON), `re` (regular expressions, short patterns for
finding text, used in Section 2), `Counter` (counts things), `datetime` and `timedelta` (a date and
time, and a length of time), `Path` (file paths) and `NamedTuple` (a small record type, used in
Section 7).

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
Tonight's file holds 1,500 molecules, with faults added at a known rate of 4% (as in
[Module 6](../06-validating-molecules/)); the duplicates arrive as extra rows, so the file has
1,510 records. First, the validation rule every record goes through: the `check` function below
reads a SMILES and returns the molecule and an empty reason, or no molecule and the reason it was
rejected. `Counter`, imported in the Setup block, tallies the reasons: it counts and sorts in one
step. In the last line, `{reason:25}` prints the reason padded to 25 characters and `{count:>5}`
prints the count right-aligned in 5, so the numbers line up in a column; `reason or "accepted"`
uses the word "accepted" when the reason is empty.

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
on the same `logging` module from three parts:

- a **logger**, the object you call (`pipeline_log.info(...)`) to write a line;
- **handlers**, which decide where each line goes: one to the screen, one to a file;
- a **formatter**, which decides what each line looks like. We write our own, which turns each line
  into JSON.

A free-text line such as `validated 1500 rows, 50 bad` is easy to write and hard to use:
to count bad rows across a month of runs, someone has to write a pattern that picks the number out
of the sentence. A **structured log** writes one JSON object per line, with the same fields every
time: the time, the level, the event, the run, the step and its counts. Log services (programs that
collect the logs of many machines in one place and let you search them, such as Elasticsearch,
Loki, CloudWatch and Datadog) index those fields; so can DuckDB, as we will see.

Two more things go into the formatter. Its time comes from a **clock object we pass in** (an
injected clock), not from the computer's clock, so a test or a lesson can set the time and get the
same output on every run. And it **removes secrets**. A connection string, the address a program
uses to reach a database, often holds a user name and password
(`postgresql://loader:s3cret@chemdb...` below); an API token is a password-like key that a program
sends to a web service. Logs are copied, shipped and read by many people; a password written into
one has leaked.

The code below has four pieces. `Clock` is a class (a recipe for an object that keeps its own data,
here the time, and has its own functions, called methods). `redact` finds secrets with two
**regular expressions**, patterns for matching text: the first matches the `:password@` part of an
address, the second matches `password=`, `token=` or `api_key=` and the value after it; each match
is replaced with `***`. `JsonFormatter` builds on `logging`'s own formatter and changes only one
method, `format`, which turns a log record into a JSON line. `make_logger` puts them together. A
line can carry extra fields: we pass them as `extra={"fields": {...}}` when we log, and the
formatter adds them to the JSON.

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
expression. The question is written in SQL: `read_json_auto(...)` reads the file as a table,
`GROUP BY level` puts the lines with the same level together, and `count(*)` counts each group.
`.df()` hands the answer back as a pandas table:

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
would put the same two tables in PostgreSQL, a database server many people can use at once (Module
4), and workflow tools (programs that start pipelines on a timetable and keep track of them, such
as Airflow, Dagster and Prefect) keep a table much like it for every task they run.

The code connects to a DuckDB file and creates three empty tables with SQL's `CREATE TABLE`: `runs`,
`steps`, and `quarantine` for the rejected records. Each column is given a type: `VARCHAR` is text,
`INTEGER` a whole number, `TIMESTAMP` a date and time. `PRIMARY KEY` means no two rows may have the
same `run_id`.

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

The four steps:

- `validate` runs `check` on every record. `[mol for mol, _ in checked]` is a list comprehension,
  a one-line loop that builds a list: it takes the molecule out of each (molecule, reason) pair, and
  `_` is the usual name for the part we do not need. `bad` is True for rejected rows, and `~bad`
  means "not bad".
- `deduplicate` keeps the first record of each InChIKey
  ([Module 3](../03-files-and-identity/)).
- `enrich` adds each vendor's country and lead time from a small table, `VENDORS`. It uses pandas'
  `merge`, which **joins** two tables: for every row on the left (our compounds) it finds the row on
  the right (the vendors) with the same value in the shared column, here `vendor`, and adds that
  row's columns, much like VLOOKUP in a spreadsheet. With `how="left"`, every compound is kept even
  when its vendor is not in the table; `indicator=True` adds a column, `_merge`, that says
  `left_only` for those, so we can quarantine them.
- `describe` adds molecular weight and logP, rounded to two decimals.

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
computer. In production the clock is the real one and nothing else changes. `rng` is NumPy's random
number generator, made from a seed so it gives the same numbers on every run. In the SQL, each `?`
is a placeholder that DuckDB fills, in order, from the list of values after it; this is safer than
pasting values into the text of the query.

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
with the log on screen showing warnings only, so the per-step lines go to the file.
`enumerate(steps, start=1)` numbers the steps 1, 2, 3, 4 as the loop goes through them:

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
reads.

`class ReconciliationError(Exception)` makes a new kind of error of our own, so that whoever calls
`reconcile` can catch exactly this problem with `except ReconciliationError`. In the SQL,
`rows_in - rows_out - quarantined - duplicates` is the number of rows that went missing (it should
be 0), and `lag(rows_out) OVER (ORDER BY step_no)` takes `rows_out` from the step before, so we can
check that each step received what the last one passed on. `itertuples()` goes through the rows of
a pandas table one at a time:

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
caught up with Vendor C, and rewrites the enrichment step with pandas' `merge` but leaves out
`how="left"`. The default is then an **inner join**, which keeps only the rows found in both
tables: compounds with no matching vendor simply disappear. Nothing crashes, the step "succeeds",
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
downstream (nothing reaches the people and programs that use its output). `finish_run` fills in
the run's row with SQL's `UPDATE`, taking the totals from the `steps` table; `df.iloc[0:0]` is the
table with all its rows removed, so a failed run records 0 rows out:

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

Freshness catches what no per-run check can: the run that never happened. If the scheduler (the
program that starts the job every night) stops, there is no failed run to alert on, only data
quietly growing old.

The limit is `FRESHNESS_LIMIT` in the Setup block. In the SQL below, `epoch(finished - started)` is
the length of the run in seconds, and `<>` means "not equal to". In the last line,
`{...:.1f}` prints the number with one decimal place.

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
properties catches this. A change in the distribution from one batch to the next is called
**drift**. We compare each new batch with a **reference**: a batch we have checked and trust, here
the output of the first run.

The **population stability index** (PSI) compares two distributions. Cut the reference into ten
bins with equal numbers of molecules (its deciles), count the share of the new batch in each bin,
and add up `(new - ref) × ln(new / ref)` over the bins. Identical distributions give 0; the bigger
the shift, the bigger the number. The **Kolmogorov–Smirnov statistic** (KS) uses the cumulative
distribution: for each value of, say, molecular weight, the share of molecules at or below it,
which rises from 0 to 1. KS is the largest vertical gap between the two batches' cumulative
distributions, from 0 (the same) to 1 (no overlap). Both are a few lines of NumPy: `np.quantile`
finds the bin edges, `np.histogram` counts the molecules in each bin, and `np.searchsorted` counts,
for each value, how many molecules lie at or below it.

The batch for the one-page example comes from `chemlib.stream`, which hands out a library a batch
at a time (a generator, [Module 8](../08-larger-than-memory/)); `next(...)` takes its first batch.
The `print` lines use the same padding as in Section 1, and `:8.3f` means 8 characters wide with 3
decimals:

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
statistic comes with a p-value (the chance of a gap this large if nothing had changed; SciPy's
`scipy.stats.ks_2samp` gives it), but with thousands of molecules almost any difference is
"significant"; the size of the gap is the more useful number. Molecular weight and logP are a
start; heavy-atom count, ring count, fraction of sp3 carbons and the share of each scaffold are
other common choices.

## 7. Alerts that people will read

A check that nobody hears about is not monitoring. An **alert rule** pairs a metric (one of the
numbers above, such as the quarantine rate) with a threshold (the value above which something is
wrong) and a severity (how urgent it is). The common practice, from site reliability engineering
(the name Google gave to the job of keeping large computer systems running), is to keep two
kinds: a **page**, which wakes someone because the data is wrong or missing now, and a **ticket**,
which can wait for working hours. The main risk is **alert fatigue**: a rule that fires every night
for something harmless trains people to ignore all of them. So alert on symptoms that need a person
(a failed run, stale data, a drifted batch), not on every warning in the log, and notify when a
rule **starts** firing and when it **resolves**, not on every check in between.

The thresholds come from the Setup block, so the rules and the checks above share one value each.

Each rule is a **named tuple** ([Module 6](../06-validating-molecules/)): a small record with named
fields, here `name`, `metric`, `threshold` and `severity`. The `: str` and `: float` after each
field are type hints, notes that say what kind of value the field holds. In the rule names,
`{QUARANTINE_LIMIT:.0%}` prints 0.10 as "10%".

The `Alerter` class remembers which rules are firing now, in a set (`self.firing`, a collection of
names with no repeats). Each time it gets new metrics it checks every rule, and it sends a message
only when a rule changes state: from quiet to firing, or from firing back to quiet ("resolved").

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

In a team the `notify` method posts to a chat channel or to an on-call service. Slack and Microsoft
Teams both give you a **webhook address**: a web address that, when a program sends a JSON message
to it, posts that message in a chat channel. On-call services (PagerDuty, Opsgenie) phone or message
whoever is on the rota that week. The webhook address is a secret too, since anyone who has it can
post to your channel: it belongs in an environment variable (a named setting kept by the operating
system outside your code, [Module 10](../10-pipelines-that-survive-failure/)), never in the code or
the logs.

## 8. A fortnight of runs

Now everything together, over fourteen simulated nights. Each night at 02:00 a new file of 1,500
molecules arrives (a fresh sample of the library, with 4% faults) and the pipeline runs. Two nights
go wrong, on purpose: on **night 8** the inner-join bug from Section 4 is deployed, and on **night
11** the supplier sends the one-page batch from Section 6. Every morning at 09:00 a separate check
looks at freshness, as a scheduler would. Only warnings and errors are printed; the file has
everything.

The loop below is long, but each night does the same five things: set the clock to 02:00 on that
night, make the night's file, run the pipeline and publish (`run_and_publish`, Section 4), measure
drift against the reference and store it in a new `drift` table, and pass the night's metrics to
the alerter; then set the clock to 09:00 and pass it the freshness. `f"run-{night:04d}"` writes the
night as four digits, so night 8 becomes `run-0008`, and `*drift` passes the four drift numbers as
four separate values:

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
DuckDB. `LEFT JOIN drift d USING (run_id)` is SQL's version of the left join from Section 3: it
adds each run's drift scores and keeps the failed run, which has none (pandas shows the missing
values as `NaN`, "not a number"):

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
quarantine rate, and the drift scores against the two PSI thresholds. The code is matplotlib
drawing three panels one above the other; you do not need to follow every line of it, only to see
that it reads nothing but the `runs` and `drift` tables. The drift panel uses a scale that is
ordinary below 0.1 and logarithmic above (`symlog`), so the small and the very large scores both
fit. The figure is saved to a file, shown under the code.

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

Dashboard programs such as Grafana, Metabase or Superset would draw the same panels live, in a web
page, from the same run-history tables; the point is that the tables exist and every run writes to
them. The last line, `db.close()`, closes the run history; to use it again in a new cell, reconnect
with `db = duckdb.connect(str(HISTORY_DB))`.

## Try it yourself

The homework is a few questions, answered by running code like the code above: in a new cell at
the end of the notebook, or in a script. It is at the end of the lesson's page, and in
`homework.md` in the module's folder. The answers are published after the cohort's deadline.

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
