---
title: History and corrections
summary: Labs correct their data. Keep every version of each compound with dbt snapshots, taken week by week; keep superseded assay readings on record but out of the marts; and build the fact table incrementally, so that each week's build processes only that week's results.
requires: dlt[duckdb], dbt-core, dbt-duckdb, duckdb, pandas, numpy, rdkit
files: ../stages/after-05/**/*
---

[Module 5](../05-tests-and-contracts/) ended with two corrections and a question. In week 7 the
lab registered LAB-0042 again with its right structure, and the warehouse simply replaced the old
one: no trace was left of what the registry had said, or of what the dashboards had shown, for six
weeks. In week 8 a plate was read again, and the corrected results arrived next to the first ones;
the grain test caught the duplicates and dbt kept them out of the marts, but nothing yet says which
reading counts.

Both are **corrections**, and a warehouse that serves a lab must handle them on purpose. Chemists
ask about the present ("what is LAB-0042?"), auditors and anyone checking an old decision ask about
the past ("what did we believe LAB-0042 was when we chose it for the panel?"), and both must get a
true answer. [Series 1, Module 13](../../series-1/13-versioning-everything/) versioned files and
code by hand; here the warehouse keeps the versions of its own data.

By the end of this module you will be able to:

- name the ways a dimension can handle change (the **slowly changing dimension** types) and choose
  between them;
- take **snapshots** with dbt, so that every version of every compound is kept with the dates it
  was valid;
- build a history dimension from the snapshots and answer questions "as of" a date;
- keep corrected results on record and out of the marts, with a test that says what the grain
  means now;
- build the fact table **incrementally**, so that a build processes only new data, and know when
  to rebuild it in full.

## Setup

This module needs the lab's history, so it starts again from week 1 and lets the weeks pass in
section 2. The dbt project is the one [Module 5](../05-tests-and-contracts/) finished, with its
tests; `labstack.dbt_project` copies it, and the functions are those of Module 5.

```python
import logging
import shutil
from pathlib import Path

import duckdb
import pandas as pd

import labdata
import labstack

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
INBOX = WORK / "inbox"
WAREHOUSE = WORK / "lab.duckdb"
PIPELINES = WORK / "dlt"
PROJECT = WORK / "lab_dbt"

shutil.rmtree(WORK, ignore_errors=True)  # start clean
lab = labdata.Lab()
labstack.dbt_project(PROJECT, after=5)


def write(name: str, text: str) -> None:
    """Save one file of the dbt project (made, with its folders, if it is new)."""
    path = PROJECT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8", newline="\n")


def edit(name: str, old: str, new: str) -> None:
    """Change one passage of a file of the dbt project (it must be there exactly once)."""
    text = (PROJECT / name).read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{name}: the passage to change is not there exactly once"
    write(name, text.replace(old, new))


def dbt(*args: str):
    """Run a dbt command on the lab's project and log what it did (labstack.dbt)."""
    return labstack.dbt(PROJECT, *args, log=log)


def query(sql: str) -> pd.DataFrame:
    """Run one SQL query on the warehouse and return the answer as a table."""
    with duckdb.connect(str(WAREHOUSE)) as db:
        return db.sql(sql).df()
```

`edit` is new: most changes in this module are a few lines in a file that already exists, and
`edit` makes them without repeating the whole file, refusing if the passage to change is missing or
appears twice.

## 1. How a dimension can change

Kimball and Ross name the ways a dimension can handle a changed description the **slowly changing
dimension** (SCD) types. The three that matter in practice:

- **Type 0: never change.** The first value stays. Right for things that cannot change, such as the
  date a compound was first registered.
- **Type 1: overwrite.** The new value replaces the old, and the old is gone. This is what the
  warehouse has done so far: the registry export is a snapshot, dlt replaces it, and `dim_compound`
  shows only today's structure. Right when the old value was simply wrong and nobody will ask about
  it again.
- **Type 2: add a version.** The old row stays, marked as no longer valid from a date, and a new row
  is added, valid from that date. Every version is kept, and a question can be asked "as of" any
  date.

A lab needs type 1 for its everyday questions (structure-activity work uses the true structure) and
type 2 for its record (what did we believe, and when?). We keep both: `dim_compound` stays current,
and a new `dim_compound_history` keeps every version.

## 2. Snapshots, taken week by week

Type 2 needs a record of every version, and the registry export cannot provide one: each week's file
has only that week's view. Something must look at the registry every week and keep what changed.
In dbt that is a **snapshot**. Each time `dbt snapshot` runs, it compares the source with the
versions it has kept, by a key, and for each row that changed it closes the old version and adds a
new one.

A snapshot is declared in YAML: which table to watch, its key, and how to tell that a row changed.
The `check` strategy compares the columns listed in `check_cols`. We list the registry's own
columns and leave out `file_name`, which dlt adds and which changes every week: listing it would
make a new version of every compound every week, though nothing about them had changed.

```python
write("snapshots/registry_history.yml", """
snapshots:
  - name: registry_history
    description: Every version of every compound the registry has held, kept week by week.
    relation: source('raw', 'registry')
    config:
      schema: snapshots
      unique_key: compound_id
      strategy: check
      check_cols: [smiles, salt, batch, chemist, vendor]
""")
```

A snapshot only sees what is there when it runs, so it must run every time new data arrives. Here
the lab's first eight weeks pass, one at a time: each week the files arrive, dlt loads them, and
dbt takes a snapshot. (This is the job [Module 7](../07-orchestration/) hands to an orchestrator.)

```python
for week in range(1, 9):
    labstack.load_raw(lab, range(week, week + 1), INBOX, WAREHOUSE, PIPELINES)
    dbt("snapshot")
```
```output
INFO snapshot registry_history: success
INFO snapshot registry_history: success
INFO snapshot registry_history: success
INFO snapshot registry_history: success
INFO snapshot registry_history: success
INFO snapshot registry_history: success
INFO snapshot registry_history: success
INFO snapshot registry_history: success
```

One snapshot a week, the first creating the table, the others adding to it. Here is what it kept
for LAB-0042:

```python
print(query("""
    SELECT compound_id, smiles, file_name, dbt_valid_to IS NULL AS current
    FROM snapshots.registry_history
    WHERE compound_id = 'LAB-0042'
    ORDER BY dbt_valid_from
""").to_string(index=False))
print(query("""
    SELECT count(*) AS versions, count(DISTINCT compound_id) AS compounds
    FROM snapshots.registry_history
""").to_string(index=False))
```
```output
compound_id                          smiles               file_name  current
   LAB-0042 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2 registry_2026-09-14.csv    False
   LAB-0042 O=C(Nc1ccc(O)cc1)Nc2ccc(C#N)nc2 registry_2026-10-19.csv     True
 versions  compounds
      321        320
```

Two versions: the wrong structure, first seen in week 2's export, and the corrected one, first seen
in week 7's. Every other compound has one version, so the table has one row more than there are
compounds. dbt added four columns: `dbt_scd_id` (a key for each version), `dbt_updated_at`,
`dbt_valid_from` and `dbt_valid_to`, empty for the current version. Those two dates are the times
the snapshots *ran*, which here were seconds apart, because eight weeks passed in one cell. In a
real lab they would be a week apart, but they would still be the times dbt ran, not the times the
lab made the changes. The lab's own dates are in the data: each version kept the name of the
export it first appeared in, and the export's name carries its date.

## 3. A history dimension

`dim_compound_history` turns the snapshot into a dimension with the lab's dates: one row per
version, valid from the date of the export that first held it until the date the next version
appeared. `lead(...) OVER (...)` reads a column from the next row of the same compound, in order;
`regexp_extract` takes the date out of the file name.

```python
write("models/marts/dim_compound_history.sql", """
-- every version of every compound (SCD type 2), dated by the lab's own exports
with versions as (
    select compound_id,
           split_part(smiles, '.', 1)  as parent_smiles,
           coalesce(salt, '')          as salt,
           chemist,
           vendor,
           registered_on::date         as registered_on,
           regexp_extract(file_name, '\\d{4}-\\d{2}-\\d{2}')::date as valid_from,
           dbt_valid_to is null        as is_current,
           dbt_valid_from              as snapshot_from
    from {{ ref('registry_history') }}
)
select row_number() over (order by compound_id, snapshot_from) as compound_version_key,
       compound_id,
       row_number() over (partition by compound_id order by snapshot_from) as version,
       parent_smiles, salt, chemist, vendor, registered_on,
       valid_from,
       lead(valid_from) over (partition by compound_id order by snapshot_from) as valid_to,
       is_current
from versions
""")
built = dbt("build", "--select", "dim_compound_history")
```
```output
INFO model dim_compound_history: success
```

The SQL is inside a Python string, so its backslashes are doubled: dbt receives `\d{4}`, "four
digits". Now a question only history can answer: when LAB-0042 was measured, what structure did
the registry give it? The marts are rebuilt only in section 5, so this question reads the
measurements' dates from the raw layer, and matches each with the version valid on its run date:

```python
print(query("""
    SELECT a.result_id, a.target, a.run_date::DATE AS run_date, h.version, h.parent_smiles
    FROM raw.assay AS a
    JOIN marts.dim_compound_history AS h
      ON h.compound_id = a.compound_id
     AND a.run_date::DATE >= h.valid_from
     AND (a.run_date::DATE < h.valid_to OR h.valid_to IS NULL)
    WHERE a.compound_id = 'LAB-0042'
    ORDER BY run_date, a.target, a.result_id
""").to_string(index=False))
```
```output
result_id target   run_date  version                   parent_smiles
  R-00179   EGFR 2026-09-23        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00180   EGFR 2026-09-23        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00257   ABL1 2026-09-30        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00258   ABL1 2026-09-30        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00259   BRAF 2026-09-30        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00260   BRAF 2026-09-30        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00261   CDK2 2026-09-30        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00262   CDK2 2026-09-30        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00263   JAK2 2026-09-30        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
  R-00264   JAK2 2026-09-30        1 O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2
```

Every measurement of LAB-0042 was made while the registry still held the wrong structure. So any
structure-activity conclusion drawn before week 7 used a molecule that was never made, and with
the history in the warehouse anyone can now find which ones. The condition `run_date >= valid_from AND run_date <
valid_to` picks the one version valid on a date, and `valid_to IS NULL` lets the current version
run on forever. That pattern is how every "as of" question is asked of a type 2 dimension.

## 4. Corrected results

The plate read twice in week 8 is a correction of facts, not of a dimension. The lab's file says
what happened: a `status` column marks the first reading `superseded` and the second `corrected`,
and every other result is `final`. The warehouse should keep all of them (a superseded reading is
part of the record) and use only the readings that count.

First, staging passes the status on. One difficulty: the `status` column exists only in files from
week 8 on, so in a warehouse holding earlier weeks only, the raw table has no such column and the
model would fail. dbt can ask the warehouse which columns a table has while it compiles the model:
`adapter.get_columns_in_relation(...)` returns them, and a Jinja `if` then writes `status` if it is
there and `'final'` if it is not. The same is true of `unit`, which arrived in week 5: the model
now copes with a raw table from any week of the project, which [Module 8](../08-observability/)
needs. The model also passes on `load_id` (dlt's `_dlt_load_id`, the load that brought each row),
which section 5 needs:

```python
write("models/staging/stg_results.sql", """
-- one row per result, every reading kept with its status; every value in nanomolar
{%- set columns = adapter.get_columns_in_relation(source('raw', 'assay'))
    | map(attribute='name') | list %}
with typed as (
    select result_id, compound_id, target, plate,
           replicate::integer      as replicate,
           relation,
           value::double           as value,
           -- 'units' was renamed 'unit' in week 5
           {% if 'unit' in columns %}coalesce(unit, units){% else %}units{% endif %}
                                   as unit,
           -- 'status' arrived in week 8: superseded, corrected or final
           {% if 'status' in columns %}coalesce(status, 'final'){% else %}'final'{% endif %}
                                   as status,
           run_date::date          as run_date,
           file_name,
           _dlt_load_id            as load_id
    from {{ source('raw', 'assay') }}
)
select typed.* exclude (file_name),
       value * u.factor              as ic50_nm,
       9 - log10(value * u.factor)   as pic50,
       relation = '='                as is_measured,  -- a value, not a bound
       file_name                     as source_file
from typed
left join {{ ref('unit_to_nm') }} as u using (unit)
""")
```

Second, the grain. A superseded reading and its correction share a well, so the grain of Module 3
holds only for the readings that count. A test's `where` setting restricts the rows it checks, and
writing it down makes the grain precise: *one row per compound, target and well among the readings
that are not superseded*. And `status` gets a test of its own, so a fourth value cannot creep in:

```python
edit("models/staging/_staging.yml",
     "            columns: [compound_id, target, plate, replicate]\n",
     "            columns: [compound_id, target, plate, replicate]\n"
     "          config:\n"
     "            where: \"status <> 'superseded'\"  # a superseded reading shares its well\n")
edit("models/staging/_staging.yml",
     "      - name: ic50_nm\n",
     "      - name: status\n"
     "        data_tests:\n"
     "          - accepted_values:\n"
     "              arguments:\n"
     "                values: [final, superseded, corrected]\n"
     "      - name: ic50_nm\n")
```

## 5. An incremental fact table

The fact table so far is rebuilt in full on every build: every result of every week, joined again.
At 1,000 rows that takes a moment; at the hundred million of a large screening group it takes
hours, every night, to add one night's data. An **incremental** model is built in full once, and
after that each build only adds (or updates) the rows that are new.

Three settings make `fact_measurement` incremental: `materialized='incremental'`; a `unique_key`,
so that a row that arrives again (a result whose status changed, say) replaces its old version
instead of being added twice; and `on_schema_change='fail'`, so that a change of columns stops the
build instead of quietly altering the table. The query then says which rows are new. `is_incremental()`
is true when the table already exists, and `{{ this }}` is the table itself, so the `where` clause
takes only the rows of loads newer than the newest already in the table. The fact table also
keeps each row's `status` and `load_id` now, so its contract gains those two columns:

```python
write("models/marts/fact_measurement.sql", """
-- one row per reading (superseded ones included, with their status); built incrementally
{{ config(materialized='incremental', unique_key='result_id', on_schema_change='fail') }}
select r.result_id,
       c.compound_key,
       t.target_key,
       r.run_date,
       r.plate,
       r.replicate,
       r.relation,
       r.ic50_nm,
       r.pic50,
       r.status,
       r.source_file,
       r.load_id
from {{ ref('stg_results') }} as r
join {{ ref('dim_compound') }} as c using (compound_id)
join {{ ref('dim_target') }} as t using (target)
{% if is_incremental() %}
-- only the loads that arrived since the last build
where r.load_id > (select max(load_id) from {{ this }})
{% endif %}
""")
edit("models/marts/_marts.yml",
     "      - name: source_file\n        data_type: varchar\n  - name: measurements_wide\n",
     "      - name: status\n        data_type: varchar\n"
     "      - name: source_file\n        data_type: varchar\n"
     "      - name: load_id\n        data_type: varchar\n"
     "        description: The dlt load that brought the row; the incremental build uses it.\n"
     "  - name: measurements_wide\n")
```

`load_id` works as a cursor because dlt gives each load an ID that grows with time, like the file
names of Module 2. The marts' readers want only the readings that count, so the wide view leaves
out the superseded ones; the fact table keeps them, and an analyst can still see them there:

```python
edit("models/marts/measurements_wide.sql",
     "join {{ ref('dim_date') }} as d on d.date_key = f.run_date\n",
     "join {{ ref('dim_date') }} as d on d.date_key = f.run_date\n"
     "where f.status <> 'superseded'  -- a corrected reading replaces it\n")
built = dbt("build", "--full-refresh")
```
```output
INFO model dim_date: success
INFO model stg_compounds: success
INFO seed targets: success
INFO seed unit_to_nm: success
INFO snapshot registry_history: success
INFO test not_null_dim_date_date_key: pass
INFO test unique_dim_date_date_key: pass
INFO test not_null_stg_compounds_compound_id: pass
INFO test unique_stg_compounds_compound_id: pass
INFO model dim_target: success
INFO model stg_results: success
INFO model dim_compound_history: success
INFO model dim_compound: success
INFO test accepted_values_dim_target_role__primary__panel: pass
INFO test not_null_dim_target_target_key: pass
INFO test unique_dim_target_target_key: pass
INFO test accepted_values_stg_results_relation______: pass
INFO test accepted_values_stg_results_status__final__superseded__corrected: pass
INFO test not_null_stg_results_compound_id: pass
INFO test not_null_stg_results_ic50_nm: pass
INFO test not_null_stg_results_result_id: pass
INFO test relationships_stg_results_compound_id__compound_id__ref_stg_compounds_: pass
INFO test unique_combination_stg_results_compound_id__target__plate__replicate: pass
INFO test unique_stg_results_result_id: pass
INFO test not_null_dim_compound_compound_id: pass
INFO test not_null_dim_compound_compound_key: pass
INFO test unique_dim_compound_compound_id: pass
INFO test unique_dim_compound_compound_key: pass
INFO model fact_measurement: success
INFO test pic50_matches_ic50: pass
INFO test potency_in_plausible_range: pass
INFO test relationships_fact_measurement_compound_key__compound_key__ref_dim_compound_: pass
INFO test relationships_fact_measurement_run_date__date_key__ref_dim_date_: pass
INFO test relationships_fact_measurement_target_key__target_key__ref_dim_target_: pass
INFO model measurements_wide: success
```

`--full-refresh` tells dbt to build incremental models from scratch, which is needed here because
the old fact table had a different shape. Every test passed, the grain test included. The fact
table now has the readings of all eight weeks, each with its status:

```python
print(query("""
    SELECT status, count(*) AS readings,
           count(*) FILTER (WHERE result_id LIKE '%-c') AS with_new_ids
    FROM marts.fact_measurement GROUP BY ALL ORDER BY status
""").to_string(index=False))
print(query("""
    SELECT compound_id, target, round(avg(pic50), 2) AS mean_pic50, count(*) AS readings
    FROM marts.measurements_wide
    WHERE compound_id = 'LAB-0202' AND relation = '='
    GROUP BY ALL ORDER BY target
""").to_string(index=False))
```
```output
    status  readings  with_new_ids
 corrected        40            40
     final       952             0
superseded        40             0
compound_id target  mean_pic50  readings
   LAB-0202   ABL1        4.90         1
   LAB-0202   BRAF        6.10         2
   LAB-0202   CDK2        5.63         2
   LAB-0202   EGFR        7.73         2
   LAB-0202   JAK2        5.60         2
```

The 40 superseded readings are on record in the fact table and out of the wide view, where
LAB-0202's potencies now come from the corrected plate alone.

Now the point of making it incremental. Week 9's files arrive, dlt loads them, and the warehouse
is built again, this time without `--full-refresh`. The compiled SQL (in `target/compiled/`) shows
the `where` clause that `is_incremental()` switched on, and counting the rows by load shows what it
did:

```python
before = query("SELECT count(*) AS n, max(load_id) AS newest FROM marts.fact_measurement")
labstack.load_raw(lab, range(9, 10), INBOX, WAREHOUSE, PIPELINES)
built = dbt("build", "--select", "stg_results+")
compiled = PROJECT / "target" / "compiled" / "lab" / "models" / "marts" / "fact_measurement.sql"
print("\n".join(line for line in compiled.read_text(encoding="utf-8").splitlines()
                if "load_id >" in line))
newest = before["newest"][0]
print(query(f"""
    SELECT load_id > '{newest}' AS from_this_build,
           string_agg(DISTINCT source_file, ', ' ORDER BY source_file) AS files,
           count(*) AS readings
    FROM marts.fact_measurement GROUP BY ALL ORDER BY from_this_build
""").to_string(index=False, max_colwidth=50))
print("readings before the build:", before["n"][0])
```
```output
INFO model stg_results: success
INFO test accepted_values_stg_results_relation______: pass
INFO test accepted_values_stg_results_status__final__superseded__corrected: pass
INFO test not_null_stg_results_compound_id: pass
INFO test not_null_stg_results_ic50_nm: pass
INFO test not_null_stg_results_result_id: pass
INFO test relationships_stg_results_compound_id__compound_id__ref_stg_compounds_: pass
INFO test unique_combination_stg_results_compound_id__target__plate__replicate: pass
INFO test unique_stg_results_result_id: pass
INFO model fact_measurement: success
INFO test pic50_matches_ic50: pass
INFO test potency_in_plausible_range: pass
INFO test relationships_fact_measurement_compound_key__compound_key__ref_dim_compound_: pass
INFO test relationships_fact_measurement_run_date__date_key__ref_dim_date_: pass
INFO test relationships_fact_measurement_target_key__target_key__ref_dim_target_: pass
INFO model measurements_wide: success
where r.load_id > (select max(load_id) from "lab"."marts"."fact_measurement")
 from_this_build                                              files  readings
           False assay_2026-09-14.csv, assay_2026-09-21_resent.c...      1032
            True                               assay_2026-11-02.csv       144
readings before the build: 1032
```

The build took only the rows of the newest load, week 9's file, and merged them into the table;
weeks 1 to 8 were not read again. Incremental models come with a duty, though. A change to the
model's logic (a new column, a corrected formula) applies only to rows built after the change, so
the table ends up half old and half new. Any change to an incremental model's SQL needs
`--full-refresh` once, and a team should know which of its models are incremental and why.

## 6. What the warehouse keeps now

The warehouse keeps every version of every compound (`snapshots.registry_history`, and
`dim_compound_history` with the lab's dates), every reading with its status (`fact_measurement`),
and the current, correct view for everyday questions (`dim_compound`, `measurements_wide`). Here
is the project's lineage, with the snapshot in it:

```python
log.info("everything built from the snapshot:")
names = dbt("ls", "--select", "registry_history+")
```
```output
INFO everything built from the snapshot:
lab.marts.dim_compound_history
lab.registry_history
```

So far every week's load, snapshot and build has been started by hand, in the right order, by
someone who knew to do it. Skip a week's snapshot and that week's changes are lost for good. In
[Module 7](../07-orchestration/) the weekly run becomes a **flow** that an orchestrator, Prefect,
starts on a schedule and when new files arrive, retries when something fails, and records.

## Try it yourself

The homework is a few questions, answered by running code like the code above: in a new cell at
the end of the notebook, or in a script. It is at the end of the lesson's page, and in
`homework.md` in the module's folder. The answers are published after the cohort's deadline.

## Further reading

- The dbt documentation. *Add snapshots to your DAG*: strategies, `check_cols`, the meta-fields and
  hard deletes. <https://docs.getdbt.com/docs/build/snapshots>
- The dbt documentation. *Configure incremental models*: `is_incremental()`, `unique_key`,
  strategies and `on_schema_change`. <https://docs.getdbt.com/docs/build/incremental-models>
- Kimball, R. & Ross, M. (2013). *The Data Warehouse Toolkit: The Definitive Guide to Dimensional
  Modeling* (3rd ed.). Wiley. Chapter 5: slowly changing dimension types 0 to 7.
- Snodgrass, R. T. (1999). *Developing Time-Oriented Database Applications in SQL*. Morgan
  Kaufmann. Valid time and transaction time: the two clocks of section 2, in depth.
