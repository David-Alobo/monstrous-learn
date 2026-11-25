---
title: Declarative ingestion
summary: Load the lab's files and ChEMBL's API into the raw layer with dlt. Declare what to load and how to recognise each row; let the tool infer the schema, remember what it has loaded, absorb duplicates, and either follow or refuse a change in the data's shape.
requires: dlt[duckdb], duckdb, pandas, numpy, rdkit, requests
files: recorded/*.json
---

In [Module 1](../01-lab-data-architecture/) we filled the raw layer by hand: one SQL statement
per source, rebuilding each raw table from every file in the inbox. That was enough to see the
idea, but a real raw layer has more to do. It should load only the files it has not seen before,
so a year of files is not reread every week. It should recognise a row that arrives twice. It
should notice when a source changes the shape of its data, and decide whether to follow the change
or stop. And it should load from web services as well as from files.

In [Series 1, Module 11](../../series-1/11-incremental-ingestion/) we wrote all of that by hand
for ChEMBL: paging through the API, remembering the highest ID loaded (a high-water mark), retrying
politely, checking every response against a model and writing rows so that a rerun did no harm. It
took most of a module. **dlt** (data load tool) is an open-source Python library that does those
jobs for you. You *declare* what to load: where the data comes from, what identifies each row,
and how to tell new data from old. dlt does the rest. That is what **declarative** means here:
you say *what* should happen, not every step of *how*.

By the end of this module you will be able to:

- explain the parts of a dlt pipeline: resources, sources, the pipeline, the destination, the
  schema and the state;
- load a snapshot file (the compound registry) so that each load replaces the last;
- load files incrementally (the assay results), so each file is loaded once and a resent file
  does not create duplicates;
- see how dlt follows a change in the data's shape, and use a schema contract to stop instead,
  then recover cleanly after the stop;
- load ChEMBL's activities for the lab's five kinases with dlt's REST API source, incrementally,
  with the licence stored next to every row.

The lab's files come from `labdata`, as in Module 1. ChEMBL's answers come from the real service:
they were recorded once, into the module's `recorded/` folder, and the lesson replays them, so it
works offline and gives the same results on every computer. The small file `chembl_replay.py` in
the module's folder does the replaying; one setting, explained in section 5, makes the same code
call ChEMBL live instead.

## Setup

Everything this lesson needs is imported and set here. dlt keeps a folder of its own for each
pipeline (what it has loaded, and the schema it has inferred); we put it under `work/`, next to
the database, so a fresh run of the lesson starts from nothing. Two settings, made through
environment variables (settings a program reads from the computer it runs on, set here with
`os.environ`), keep dlt quiet: one stops it sending anonymous usage statistics to its makers, and
one stops it printing log lines with times in them, which would differ on every run.

From Python itself the block imports `os`, `re` (patterns that match text), `shutil` (to delete a
folder) and `Path`; and `PipelineStepFailed`, the error dlt raises when a step of a load fails.

```python
import logging
import os
import re
import shutil
from pathlib import Path

import dlt
import duckdb
import pandas as pd
from dlt.pipeline.exceptions import PipelineStepFailed
from dlt.sources.rest_api import rest_api_source

import chembl_replay
import labdata

os.environ["RUNTIME__DLTHUB_TELEMETRY"] = "false"  # no usage statistics sent to dlt's makers
os.environ["RUNTIME__LOG_LEVEL"] = "ERROR"  # dlt prints only errors, so the outputs are stable

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
INBOX = WORK / "inbox"  # where the lab's files arrive, one set per week
WAREHOUSE = WORK / "lab.duckdb"  # the database; dlt loads into its raw layer
PIPELINES = WORK / "dlt"  # dlt's own folder: what each pipeline has loaded, and its schema
WEEKS = 6  # how many weeks of the lab's files we load
# ChEMBL: where its API lives, which fields to ask for, and how many activities a page holds
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data/"
FIELDS = ("activity_id,molecule_chembl_id,canonical_smiles,standard_type,standard_relation,"
          "standard_value,standard_units,pchembl_value,target_chembl_id,document_chembl_id")
PAGE_SIZE = 100
CHEMBL_LICENCE = "ChEMBL, CC BY-SA 3.0 (https://www.ebi.ac.uk/chembl/)"

shutil.rmtree(WORK, ignore_errors=True)  # start clean
WORK.mkdir()
lab = labdata.Lab()


def query(sql: str) -> pd.DataFrame:
    """Run one SQL query on the warehouse and return the answer as a table."""
    with duckdb.connect(str(WAREHOUSE)) as db:
        return db.sql(sql).df()
```

`query` opens the database, runs one query and closes it again, so our reading never gets in the
way of dlt's writing.

## 1. The parts of a dlt pipeline

A dlt load has six parts, and every later section uses them:

- A **resource** is a Python function that **yields** rows: each row is a dictionary (column
  name to value), and `yield` hands rows over one batch at a time instead of building one huge list
  ([Series 1, Module 8](../../series-1/08-larger-than-memory/) used the same idea for files larger
  than memory). The decorator `@dlt.resource`, written on the line above the function, turns an
  ordinary function into a resource and says how its rows are to be loaded.
- A **source** is a group of resources that belong together, such as all of ChEMBL's endpoints.
- The **destination** is where the data goes: for us, the DuckDB database of Module 1.
- The **pipeline** connects resources to a destination. Its **dataset** is the schema (the
  group of tables) it loads into: ours is `raw`, the raw layer.
- The **schema** is dlt's description of every table and column it has loaded, with their types.
  dlt **infers** it, working it out from the data, and keeps it up to date.
- The **state** is what dlt remembers between runs, such as the last file loaded. It is stored
  with the pipeline, and also in the destination, so a pipeline can carry on where it stopped.

Each run goes through three steps: **extract** (call the resources and collect their rows),
**normalize** (fit the rows to the schema: types, column names, nested data split into tables)
and **load** (write them to the destination). When something goes wrong, dlt says which step
failed, which section 4 uses.

## 2. A snapshot: the compound registry

The registry export is a snapshot: each week's file holds every compound so far. So each load
should **replace** the registry table with the latest file. That is a resource's **write
disposition**: `"replace"` here; the other two are `"append"` (add the rows) and `"merge"` (add new
rows and update existing ones, section 3).

We read each file with pandas, keeping every value as text (`dtype=str`) and empty cells as empty
text (`keep_default_na=False`), so the raw layer holds the file exactly as written, as in Module 1.
`to_dict("records")` turns the table into a list of dictionaries, one per row, which is what a
resource yields:

```python
@dlt.resource(name="registry", write_disposition="replace")
def registry():
    """The latest registry export: every compound registered so far."""
    latest = max(INBOX.glob("registry_*.csv"))  # the names carry dates, so max is the newest
    table = pd.read_csv(latest, dtype=str, keep_default_na=False)
    table["file_name"] = latest.name
    yield table.to_dict("records")


pipeline = dlt.pipeline(
    pipeline_name="lab",
    destination=dlt.destinations.duckdb(str(WAREHOUSE)),
    dataset_name="raw",
    pipelines_dir=str(PIPELINES),
)
for week in range(1, WEEKS + 1):
    lab.write_week(week, INBOX)
    pipeline.run(registry())
print(query("SELECT count(*) AS compounds, max(file_name) AS from_file FROM raw.registry")
      .to_string(index=False))
```
```output
 compounds               from_file
       240 registry_2026-10-12.csv
```

Six weekly loads, and the table holds the 240 compounds of the latest export, not six copies of
the registry stacked together. dlt also wrote down the table's schema. `pipeline.default_schema`
holds it; here are the registry's columns with the type dlt inferred for each:

```python
columns = pipeline.default_schema.get_table_columns("registry")
print({name: column["data_type"] for name, column in columns.items()})
```
```output
{'compound_id': 'text', 'smiles': 'text', 'salt': 'text', 'batch': 'text', 'chemist': 'text', 'vendor': 'text', 'registered_on': 'text', 'file_name': 'text', '_dlt_load_id': 'text', '_dlt_id': 'text'}
```

Every column we yielded is `text`, as we read it. dlt added two of its own: `_dlt_load_id` says
which load wrote the row, and `_dlt_id` is a unique ID for the row. Both let any row be traced back
to the run that produced it, the same job `filename` did in Module 1.

## 3. Files, incrementally: the assay results

Assay files are different: each holds only one week's results, so every file must be loaded once,
and a file already loaded must not be loaded again. dlt calls this **incremental** loading. A
resource gets an argument `dlt.sources.incremental(...)` naming a **cursor**: a value that grows as
new data arrives. Here the cursor is the file name, because the names carry dates. After each run
dlt remembers the largest file name it has seen (`last_value`), and the resource skips every file
whose name is not larger.

The second decision is what makes a row the same row. Each result has a `result_id`; declaring it
the **primary key** (the column that identifies a row) and the write disposition `"merge"` tells
dlt to add new results and *replace* results whose key it already has, never to keep two. That is
what absorbs the file sent twice in week 4.

```python
@dlt.resource(name="assay", write_disposition="merge", primary_key="result_id")
def assay(files=dlt.sources.incremental("file_name", initial_value="")):
    """Every row of every assay file not loaded before."""
    for path in sorted(INBOX.glob("assay_*.csv")):
        if path.name <= files.last_value:
            continue  # loaded in an earlier run
        table = pd.read_csv(path, dtype=str, keep_default_na=False)
        table["file_name"] = path.name
        yield table.to_dict("records")


def rows_loaded(pipeline: dlt.Pipeline) -> dict[str, int]:
    """How many rows each table received in the pipeline's last run (dlt's own tables left out)."""
    info = pipeline.last_trace.last_normalize_info
    counts = info.row_counts if info else {}
    return {table: n for table, n in counts.items() if not table.startswith("_dlt")}


for week in range(1, WEEKS + 1):
    pipeline.run(assay())  # the files of all six weeks are already in the inbox
    log.info("run %d: %s", week, rows_loaded(pipeline))
```
```output
INFO run 1: {'assay': 832}
INFO run 2: {}
INFO run 3: {}
INFO run 4: {}
INFO run 5: {}
INFO run 6: {}
```

The first run found all the assay files at once, because section 2 already put six weeks of files
in the inbox; the next five runs found nothing new. In a real lab, the pipeline runs once a week
and loads that week's files. Either way, nothing is loaded twice. Here is what dlt remembers, and
what the table holds:

```python
cursor = pipeline.state["sources"]["lab"]["resources"]["assay"]["incremental"]["file_name"]
print("last file loaded:", cursor["last_value"])
print(query("SELECT count(*) AS rows, count(DISTINCT result_id) AS results FROM raw.assay")
      .to_string(index=False))
print(query("SELECT file_name, count(*) AS rows FROM raw.assay GROUP BY ALL ORDER BY file_name")
      .to_string(index=False))
```
```output
last file loaded: assay_2026-10-12.csv
 rows  results
  656      656
           file_name  rows
assay_2026-09-14.csv    80
assay_2026-09-21.csv   176
assay_2026-09-28.csv   136
assay_2026-10-05.csv   136
assay_2026-10-12.csv   128
```

The run read 832 rows but the table holds 656, one per result: the 176 rows of the resent file
(`assay_2026-09-21_resent.csv`, week 3's results sent again in week 4) were recognised by their
`result_id` and kept once. The file list has no rows from the resent file because both copies
arrived in the same load, and when that happens dlt keeps one of them. Which one is not defined
unless you say, with a hint called `dedup_sort`; here it kept the original. When a later load
brings a key the table already has, the new row replaces the old one, as section 4 shows.

Module 1 removed the same duplicates in staging with `QUALIFY`; with a primary key, the raw layer
never holds them at all. Note what this gives up: the raw layer no longer shows that week 3's file
arrived twice. If that matters (it might, when you need to tell a supplier their system sends
files twice), load with `"append"` and remove duplicates in staging, as Module 1 did. Both are
reasonable, and a team should choose on purpose.

## 4. When the data changes shape

In week 5 the plate reader's software was updated: it now writes the unit in a column called
`unit` instead of `units`, and adds a column `operator`. The load in section 3 did not fail. dlt
**evolved** the schema: it saw columns it had not seen and added them to the table.

```python
assay_columns = pipeline.default_schema.get_table_columns("assay")
print([name for name in assay_columns if not name.startswith("_dlt")])
print(query("SELECT count(units) AS with_units, count(unit) AS with_unit FROM raw.assay")
      .to_string(index=False))
```
```output
['result_id', 'compound_id', 'target', 'plate', 'replicate', 'relation', 'value', 'units', 'run_date', 'file_name', 'unit', 'operator']
 with_units  with_unit
        392        264
```

The old rows have `units`, the new rows have `unit`, and each is empty where the other is filled,
exactly as in Module 1's raw layer. Following a change automatically is often right for a raw
layer, because nothing is lost and staging can bring the two columns together (Module 1's
`coalesce(unit, units)`). But it can also hide a change that someone ought to know about: here, a
software update nobody announced, which might have changed more than a column's name.

A **schema contract** decides what dlt does when the data changes shape. `"evolve"` (what we have
had so far) follows the change; `"freeze"` refuses it and stops the load with an error;
`"discard_row"` and `"discard_value"` drop the rows or values that do not fit. Here we load the
same files into a second dataset, `raw_strict`, with the columns frozen. This time the files
arrive as they would in the lab, one week at a time, into a second inbox, and the pipeline runs
once a week. The `try`/`except` catches only dlt's own failure, as [Series 1, Module
10](../../series-1/10-pipelines-that-survive-failure/) taught, and prints the rule that was broken:

```python
WEEKLY = WORK / "weekly"  # a second inbox, filled one week at a time


@dlt.resource(name="assay", write_disposition="merge", primary_key="result_id",
              schema_contract={"columns": "freeze"})
def assay_strict(files=dlt.sources.incremental("file_name", initial_value="")):
    """The assay files in the weekly inbox, but the table's columns may not change."""
    for path in sorted(WEEKLY.glob("assay_*.csv")):
        if path.name <= files.last_value:
            continue
        table = pd.read_csv(path, dtype=str, keep_default_na=False)
        table["file_name"] = path.name
        yield table.to_dict("records")


strict = dlt.pipeline(pipeline_name="lab_strict", destination=dlt.destinations.duckdb(
    str(WAREHOUSE)), dataset_name="raw_strict", pipelines_dir=str(PIPELINES))
for week in range(1, WEEKS + 1):
    lab.write_week(week, WEEKLY)  # this week's files arrive
    try:
        strict.run(assay_strict())
        log.info("week %d: loaded %s", week, rows_loaded(strict))
    except PipelineStepFailed as error:
        rule = re.search(r"Can't add .*? are frozen", str(error.__cause__))
        log.error("week %d: the %s step failed: %s", week, error.step, rule.group(0))
        break
```
```output
INFO week 1: loaded {}
INFO week 2: loaded {'assay': 80}
INFO week 3: loaded {'assay': 176}
INFO week 4: loaded {'assay': 312}
ERROR week 5: the normalize step failed: Can't add table column `unit` to table `assay` because `columns` are frozen
```

Week 1 brings no assay file (nothing has been tested yet), so nothing is loaded. Weeks 2 to 4
load, week 4 with both its own file and the resent copy of week 3's. Week 5 stops at the
**normalize** step, the one that fits rows to the schema, with a message that says exactly which
column broke which rule. Nobody's analysis is touched until a person decides what the change
means.

Stopping is only half of it: the pipeline must also recover cleanly. dlt keeps the failed load as
a **pending package** (the rows it extracted, waiting to be loaded), and its state already says
week 5's file was read. A plain rerun would only fail again on the same package, and simply
deleting the files dlt keeps would lose track of what was loaded. `abort_packages()` is the clean
way out: it gives up the pending package and puts the state back to where it was before:

```python
strict.abort_packages()
cursor = strict.state["sources"]["lab_strict"]["resources"]["assay"]["incremental"]["file_name"]
print("pending packages left:", strict.has_pending_data)
print("last file loaded, back to:", cursor["last_value"])
```
```output
pending packages left: False
last file loaded, back to: assay_2026-09-28.csv
```

Now a person decides. Here the change is understood (the unit moved to a new column, and staging
already handles it), so we allow the new columns and run again. `apply_hints` changes a resource's
settings without rewriting it:

```python
allowed = assay_strict()
allowed.apply_hints(schema_contract={"columns": "evolve"})  # for this run only
strict.run(allowed)
log.info("week 5, after the decision: loaded %s", rows_loaded(strict))
lab.write_week(6, WEEKLY)
strict.run(assay_strict())  # frozen again, and week 6 fits the schema as it now is
log.info("week 6: loaded %s", rows_loaded(strict))
print(query("SELECT file_name, count(*) AS rows, count(unit) AS with_unit FROM raw_strict.assay "
            "GROUP BY ALL ORDER BY file_name").to_string(index=False))
```
```output
INFO week 5, after the decision: loaded {'assay': 136}
INFO week 6: loaded {'assay': 128}
                  file_name  rows  with_unit
       assay_2026-09-14.csv    80          0
assay_2026-09-21_resent.csv   176          0
       assay_2026-09-28.csv   136          0
       assay_2026-10-05.csv   136        136
       assay_2026-10-12.csv   128        128
```

Week 5's file was loaded after all, and week 6's in its turn, under the frozen contract again: the
schema now has `unit` and `operator`, so week 6 breaks no rule. The table holds the same 656
results as the `raw` dataset, but look at week 3's rows: here they carry the resent file's name.
In this pipeline the resent copy came in a later load than the original (week 4, not week 3), and
a row whose key is already in the table replaces the old one. A frozen contract turns a silent
change into a decision with a record.

## 5. An API, declared: ChEMBL

The lab also wants public data for its five targets, so its own potencies can be compared with
published ones. ChEMBL's API answers in pages of JSON, as [Series 1, Module
11](../../series-1/11-incremental-ingestion/) showed. dlt's **REST API source** turns an API into
resources from a configuration: a dictionary that says where the API is and, for each resource,
which endpoint (address) to call, with which **parameters** (the settings sent with the request),
where the rows are in each answer, and how to load them.

The configuration below asks ChEMBL for each kinase's IC50 activities that have a pChEMBL value,
in order of `activity_id`, one page of 100 per run. The `incremental` part says that
`activity_id` is the cursor, and that its last value is sent as the parameter `activity_id__gt`
("greater than"), so the next run asks only for newer activities. One page per run keeps the
lesson small and polite to ChEMBL's servers; a real job would follow ChEMBL's page links (dlt's
`json_link` paginator) to fetch everything.

```python
def chembl():
    """ChEMBL's IC50 activities for the lab's five kinases, one page of 100 per target per run."""
    resources = [
        {
            "name": f"chembl_{gene.lower()}",
            "table_name": "chembl_activities",  # the five resources fill one table
            "primary_key": "activity_id",
            "write_disposition": "merge",
            "endpoint": {
                "path": "activity.json",
                "params": {"target_chembl_id": target, "standard_type": "IC50",
                           "pchembl_value__isnull": "false", "order_by": "activity_id",
                           "limit": PAGE_SIZE, "only": FIELDS},
                "data_selector": "activities",  # the rows are in the answer's "activities" list
                "paginator": {"type": "single_page"},
                "incremental": {"cursor_path": "activity_id", "start_param": "activity_id__gt",
                                "initial_value": 0},
            },
        }
        for gene, target in labdata.TARGETS.items()
    ]
    source = rest_api_source(
        {"client": {"base_url": CHEMBL_API, "session": chembl_replay.session()},
         "resources": resources},
        name="chembl",
    )
    for resource in source.resources.values():  # keep the licence with every row
        resource.add_map(lambda row: {**row, "licence": CHEMBL_LICENCE})
    return source
```

`"session": chembl_replay.session()` is the only line about recording: it hands dlt a connection
that answers from `recorded/` instead of the internet. Set the environment variable `CHEMBL_MODE`
to `live` before running the lesson and the same configuration calls ChEMBL for real (the numbers
will then differ, because ChEMBL keeps growing). `add_map` runs a small function on every row
before it is loaded; here it adds the licence, because ChEMBL's data may be reused only with
credit and under the same licence ([Series 1, Module 11](../../series-1/11-incremental-ingestion/),
section 1).

Two runs, as if a week apart:

```python
public = dlt.pipeline(pipeline_name="chembl", destination=dlt.destinations.duckdb(str(WAREHOUSE)),
                      dataset_name="raw", pipelines_dir=str(PIPELINES))
for run in (1, 2):
    public.run(chembl())
    log.info("ChEMBL run %d: %s", run, rows_loaded(public))
print(query("""
    SELECT target_chembl_id, count(*) AS activities,
           min(activity_id) AS first_id, max(activity_id) AS last_id
    FROM raw.chembl_activities GROUP BY ALL ORDER BY target_chembl_id
""").to_string(index=False))
```
```output
INFO ChEMBL run 1: {'chembl_activities': 500}
INFO ChEMBL run 2: {'chembl_activities': 500}
target_chembl_id  activities  first_id  last_id
      CHEMBL1862         200    146141  2280450
       CHEMBL203         200     32260   130240
      CHEMBL2971         200    506160  3214186
       CHEMBL301         200    105376   815967
      CHEMBL5145         200   1666310  2240588
```

Each run brought 100 activities per target, and the second run's were all newer than the first's:
the cursor did its job. ChEMBL's answers are JSON with values in their own types, so dlt inferred
proper types this time:

```python
columns = public.default_schema.get_table_columns("chembl_activities")
print({name: column["data_type"] for name, column in columns.items()
       if not name.startswith("_dlt")})
```
```output
{'activity_id': 'bigint', 'canonical_smiles': 'text', 'document_chembl_id': 'text', 'molecule_chembl_id': 'text', 'pchembl_value': 'text', 'relation': 'text', 'standard_relation': 'text', 'standard_type': 'text', 'standard_units': 'text', 'standard_value': 'text', 'target_chembl_id': 'text', 'type': 'text', 'units': 'text', 'value': 'text', 'licence': 'text'}
```

`activity_id` is a whole number (`bigint`), so its order is numeric and the cursor compares
numbers. The potency values arrive from ChEMBL as text (`"6.0"`), and dlt keeps them as text:
the raw layer records what the source sent. ChEMBL also sent four fields we did not list in
`only`: `type`, `relation`, `value` and `units`, the values as the original paper reported them
(that `"6.0"` nM was published as `"0.006"` µM). The raw layer keeps them too. Turning values into
numbers, and units into nanomolar, is staging's job.

## 6. What dlt records about every load

dlt keeps a table `_dlt_loads` in each dataset, with one row per load: its ID, the schema, its
status and when it finished. With `_dlt_load_id` on every row, any row can be traced to the run
that wrote it:

```python
print(query("""
    SELECT schema_name, count(*) AS loads, max(status) AS status
    FROM raw._dlt_loads GROUP BY ALL ORDER BY schema_name
""").to_string(index=False))
print(query("SELECT schema_name FROM information_schema.schemata "
            "WHERE catalog_name = 'lab' ORDER BY schema_name").to_string(index=False))
```
```output
schema_name  loads  status
     chembl      2       0
        lab      7       0
       schema_name
              main
               raw
       raw_staging
        raw_strict
raw_strict_staging
```

Status `0` means the load completed. `main` is DuckDB's own default schema, empty here. The others
are what dlt made: `raw` and `raw_strict`, the two datasets; and `raw_staging` and `raw_strict_staging`, where dlt puts rows for a moment before
a merge. (These are dlt's own working tables, not the staging layer of Module 1, despite the
name.) The registry, the assay files and ChEMBL are now in the raw layer, loaded by a tool that
remembers what it loaded, absorbs duplicates, follows or refuses changes of shape, and keeps the
licence. In Module 3 we decide the shape of the marts, and in Module 4 dbt builds the staging and
mart layers from this raw layer.

## Try it yourself

The homework is a few questions, answered by running code like the code above: in a new cell at
the end of the notebook, or in a script. It is at the end of the lesson's page, and in
`homework.md` in the module's folder. The answers are published after the cohort's deadline.

## Further reading

- The dlt documentation. *Incremental loading*: cursors, `last_value` and the write dispositions.
  <https://dlthub.com/docs/general-usage/incremental-loading>
- The dlt documentation. *Schema and data contracts*: `evolve`, `freeze`, `discard_row` and
  `discard_value`, for tables, columns and types. <https://dlthub.com/docs/general-usage/schema-contracts>
- The dlt documentation. *REST API source*: the configuration dictionary, paginators and
  incremental loading from APIs.
  <https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/basic>
- The dlt documentation. *State*: what a pipeline remembers between runs, and where.
  <https://dlthub.com/docs/general-usage/state>
- Zdrazil, B. et al. (2024). The ChEMBL Database in 2023: a drug discovery platform spanning
  multiple bioactivity data types and time periods. *Nucleic Acids Research*, 52(D1), D1180–D1192.
  <https://doi.org/10.1093/nar/gkad1004>
- Reis, J. & Housley, M. (2022). *Fundamentals of Data Engineering*. O'Reilly Media. Chapter 7,
  on ingestion: batch and streaming, push and pull, and the trade-offs of each.
