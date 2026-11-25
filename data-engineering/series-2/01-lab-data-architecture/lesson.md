---
title: Designing a lab data architecture
summary: From a folder of spreadsheets to layers a team can trust. Land the lab's files untouched, clean them in one place, shape them for the questions chemists ask, and see where each piece of Series 1 fits in a modern data stack.
requires: pandas, duckdb, numpy, rdkit
---

In Series 1 we worked with a small drug-discovery lab without naming it: its molecules came from
`chemlib`, and its measurements, in [Module 12](../../series-1/12-validating-data/), were
potencies against five kinases (enzymes that many cancer drugs target). In this series the lab
has a project and a timeline. Its target is **EGFR**, a kinase that drives several cancers. Each
week the chemists register about forty new compounds. The week after, each compound is tested on
EGFR, twice. The potent ones are then tested on four other kinases (ABL1, BRAF, CDK2 and JAK2), to
check that they are **selective**: that they hit EGFR and not the others.

Every week the lab's computers produce files: an export of the **compound registry** (the
spreadsheet in which the chemists record every compound they make) and the **assay results** from
the plate reader (the instrument that measures how strongly each compound blocks the enzyme). At
the moment these files go into a shared folder, and anyone with a question opens them in a
spreadsheet. This works for a few weeks. Then a file is sent twice, a software update renames a
column, one plate writes micromolar as `uM` and another as `µM`, and the answers people get from
the folder start to disagree.

This module designs the alternative: an **architecture**, meaning a decision about where data
lives, in which form, and how it moves from one form to the next. It is the plan the rest of the
series fills in with industry tools. As in Series 1, we build it by hand first, with DuckDB and
SQL, so that each tool, when it arrives, replaces something you have already seen work.

By the end of this module you will be able to:

- explain what goes wrong when a team works from a shared folder of files;
- describe the three layers of a modern data architecture (raw, staging and marts) and say what
  belongs in each;
- explain the difference between ETL and ELT, and why modern stacks keep the raw data untouched;
- build the three layers for the lab's first six weeks of files in DuckDB, so that a question has
  one answer;
- say where each module of Series 1 belongs in the architecture, and which tool of this series
  takes it over.

The lab's data comes from `labdata`, this series' companion to `chemlib`. It makes the lab's
files week by week, the same on every computer, with problems planted on purpose (a list says
which, and when). The potencies are made up, but they are not random: they follow from the
structure of each molecule, so later in the series the dashboards show real-looking patterns.
Every number in this module is therefore synthetic, made for teaching.

![The lab's data flow, from files to answers: the weekly files arrive in an inbox, are copied unchanged into the raw layer, cleaned and typed once in the staging layer, and shaped into marts that answer the chemists' questions; each later module of the series takes over one arrow](figures/three-layers.svg)

## Setup

Everything this lesson needs is imported and set here, so the settings can be changed in one
place. As in Series 1, pipeline steps report with `log`, and `print` is kept for showing you
results.

The block imports pandas (tables in Python), DuckDB (a database that runs inside Python, from
[Series 1, Module 4](../../series-1/04-databases-and-schemas/)) and `labdata`, which makes the
lab's files. From Python itself it imports `shutil`, to delete a folder so the lesson starts
clean, and `Path`, for file names.

```python
import logging
import shutil
from pathlib import Path

import duckdb
import pandas as pd

import labdata

# log lines: level and message only, so the lesson's outputs are the same on every run
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
INBOX = WORK / "inbox"  # where the lab's files arrive, one set per week
WAREHOUSE = WORK / "lab.duckdb"  # the database that holds the three layers
# how many weeks of the project this module loads (the lab's story runs for twelve)
WEEKS = 6
# the compound whose potency we ask about in sections 1 and 6
QUESTION_COMPOUND = "LAB-0057"

# start clean: a run of the lesson always begins with an empty inbox and an empty warehouse
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir()
lab = labdata.Lab()
```

## 1. The lab and its folder of files

First we let six weeks of the project happen. `lab.write_week(week, folder)` writes the files
that arrived in that week, exactly as the lab's computers produce them:

```python
for week in range(1, WEEKS + 1):
    written = lab.write_week(week, INBOX)
    log.info("week %d: %s", week, ", ".join(p.name for p in written))
```
```output
INFO week 1: registry_2026-09-07.csv
INFO week 2: registry_2026-09-14.csv, assay_2026-09-14.csv
INFO week 3: registry_2026-09-21.csv, assay_2026-09-21.csv
INFO week 4: registry_2026-09-28.csv, assay_2026-09-28.csv, assay_2026-09-21_resent.csv
INFO week 5: registry_2026-10-05.csv, assay_2026-10-05.csv
INFO week 6: registry_2026-10-12.csv, assay_2026-10-12.csv
```

Each file name carries the Monday of the week it arrived. Two kinds of file arrive: a registry
export every week, and from week 2 an assay file (in week 1 nothing has been tested yet). Here
are the first rows of each, as they are in the files:

```python
registry = pd.read_csv(INBOX / "registry_2026-10-12.csv")
print(registry.head(3).to_string(index=False))
print()
assay = pd.read_csv(INBOX / "assay_2026-09-14.csv")
print(assay.head(3).to_string(index=False))
```
```output
compound_id                                                           smiles salt  batch chemist   vendor registered_on
   LAB-0001            c1nc(c8ccco8)cc(n1)N2CCN(CC2)C(=O)c3ccc(OC(F)(F)F)cc3  NaN      1      CN Vendor A    2026-09-11
   LAB-0002 c1cc(CC)c(nc1)Nc2nc(c8ccco8)c(c8ccc(F)cc8)c(OC)n2.O=C(O)C(F)(F)F  TFA      1      AO Vendor C    2026-09-11
   LAB-0003        c1cc(C(C)C)c(nc1)Nc2nc(N(C)C)c(c8cn[nH]c8)c(c8cn[nH]c8)n2  NaN      1      AO Vendor A    2026-09-11

result_id compound_id target  plate  replicate relation  value units   run_date
  R-00001    LAB-0001   EGFR P02-01          1        =  150.0    nM 2026-09-16
  R-00002    LAB-0001   EGFR P02-01          2        =  101.0    nM 2026-09-16
  R-00003    LAB-0002   EGFR P02-01          1        =  703.0    nM 2026-09-16
```

A registry export is a **snapshot**: every compound registered so far, so each week's file is
longer than the last. In the `salt` column, `NaN` ("not a number") is how pandas shows an empty
cell: those compounds were registered without a salt; `LAB-0002` was registered as its salt with
trifluoroacetic acid (TFA), which is why its SMILES ends with a second molecule after a dot. An
assay file holds only that week's measurements. `relation` is `=` for a
measured IC50, the concentration at which the compound blocks half of the enzyme's activity, and
`>` when the compound was too weak to measure, so the value is only a lower limit. `labdata` also
keeps a list of the problems it planted, and when:

```python
print(lab.events.to_string(index=False))
```
```output
 week            kind                                                                    what  module
    2  unit spellings                    results in µM are written as uM or μM on some plates       2
    4     resent file                     week 3's assay file arrives again, under a new name       2
    5   schema change the plate reader's export renames 'units' to 'unit' and adds 'operator'       2
    7 re-registration                       LAB-0042's structure is corrected in the registry       6
    8 corrected plate   plate P08-01 is re-read; its corrected results replace the first ones       6
   10       late file                week 10's assay file arrives a week late, with week 11's       8
```

The last column says which module of this series deals with each problem. Three of them happen in
the six weeks we have: unit spellings from week 2, a file sent twice in week 4, and a renamed
column in week 5.

Now suppose a medicinal chemist asks a plain question: *how potent is compound
`LAB-0057` against EGFR?* With a folder of files, the natural answer is to open all the assay
files, stack them into one table and look the compound up. That is what pandas' `concat` does:

```python
files = sorted(INBOX.glob("assay_*.csv"))
stacked = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
answer = stacked[(stacked["compound_id"] == QUESTION_COMPOUND) & (stacked["target"] == "EGFR")]
print(answer[["result_id", "value", "units", "relation"]].to_string(index=False))
print(f"{len(stacked)} rows; {stacked['result_id'].duplicated().sum()} result ids appear twice")
print("columns:", list(stacked.columns))
```
```output
result_id  value units relation
  R-00209  228.0    nM        =
  R-00210  342.0    nM        =
  R-00209  228.0    nM        =
  R-00210  342.0    nM        =
832 rows; 176 result ids appear twice
columns: ['result_id', 'compound_id', 'target', 'plate', 'replicate', 'relation', 'value', 'units', 'run_date', 'unit', 'operator']
```

The answer looks reasonable, but the stacked table has three problems that nobody asked for:

- some results appear twice, because week 3's file arrived again in week 4 under a new name, so
  any average or count over the table is wrong;
- from week 5 the unit sits in a column called `unit`, not `units`, so the stacked table has both,
  each empty for half the rows: a filter on `units` silently misses the newer results;
- micromolar is written three ways (`µM`, `uM` and `μM`, the last with the Greek letter mu),
  so a table that converts units by spelling misses some of them.

Each person who uses the folder has to know all of this and fix it in their own copy, every time.
Two people who fix it differently get two different answers, and neither can show how they got
theirs. That is the problem an architecture solves: the fixes are made **once**, in a known place,
and everyone reads the result.

## 2. Three layers

A modern data architecture keeps data in three layers. The names vary between teams (some say
bronze, silver and gold), but the idea is the same:

- **Raw**: the data exactly as it arrived, copied into the warehouse with a note of where and when
  it came from, and never changed. If a cleaning step later turns out to be wrong, the original is
  still there to clean again.
- **Staging**: one cleaned table per source. Here each column gets its proper type (a number, a
  date), names and units are made consistent, duplicates are removed, and nothing else: no
  business questions yet. Every fix from section 1 is made here, once.
- **Marts**: tables shaped for the questions people ask, such as "how potent is each compound on
  each target?" or "which compounds are selective?". A mart joins and summarises staging tables;
  dashboards and models read marts, never raw files.

A **warehouse** is the database that holds the layers. Ours is a DuckDB file; in a large company
it may be a service such as Snowflake or BigQuery, but the layers are the same.

Moving data into a warehouse used to follow **ETL**: *extract* the data from its source,
*transform* it (clean and reshape it) on the way, then *load* only the result. If the
transformation had a mistake, the original was gone. Modern stacks follow **ELT**: extract and
*load* the data first, unchanged, into the raw layer, then *transform* it inside the warehouse,
where the raw copy stays. Storage is now cheap and warehouses are fast, so keeping everything
costs little, and it means any transformation can be fixed and run again.

The layers also split the work. In this series, **dlt** will load the raw layer (Module 2),
**dbt** will build the staging and mart layers from SQL (Modules 4 to 6), and **Prefect** will run
the whole thing every week (Module 7). In this module we build all three layers by hand, in a
DuckDB database, so that you see exactly what those tools will do.

DuckDB keeps related tables in **schemas**, named groups of tables in one database, like folders.
We make one schema per layer:

```python
db = duckdb.connect(str(WAREHOUSE))
for layer in ["raw", "staging", "marts"]:
    db.execute(f"CREATE SCHEMA IF NOT EXISTS {layer}")
print(db.sql("SELECT schema_name FROM information_schema.schemata "
             "WHERE catalog_name = 'lab' ORDER BY schema_name").fetchall())
```
```output
[('main',), ('marts',), ('raw',), ('staging',)]
```

`information_schema` is a set of tables every SQL database keeps about itself; here it lists the
schemas of our database (`lab`, after the file name), including `main`, which DuckDB always has.

## 3. The raw layer: the files, unchanged

The raw layer is a copy of every file, row for row. To make the copy faithful we tell DuckDB's
CSV reader three things:

- `all_varchar = true`: keep every value as text, exactly as written, instead of guessing types;
  guessing is a kind of transformation, and transformations belong in staging;
- `union_by_name = true`: line the files up by column name, so a file with a renamed or extra
  column still loads (the missing columns are left empty);
- `filename = true`: add a column saying which file each row came from, so every row can be traced
  back to the file it arrived in.

Loading the raw layer is then one statement per source. `CREATE OR REPLACE TABLE ... AS SELECT`
builds a table from a query, replacing any earlier version:

```python
def load_raw(db: duckdb.DuckDBPyConnection) -> None:
    """Copy every file in the inbox into the raw layer, as text and unchanged."""
    for source in ["registry", "assay"]:
        db.execute(f"""
            CREATE OR REPLACE TABLE raw.{source} AS
            SELECT * FROM read_csv('{INBOX.as_posix()}/{source}_*.csv',
                                   all_varchar = true, union_by_name = true, filename = true)
        """)
        rows = db.sql(f"SELECT count(*) FROM raw.{source}").fetchall()[0][0]
        log.info("raw.%s: %d rows", source, rows)


load_raw(db)
print(db.sql("DESCRIBE raw.assay").df()[["column_name", "column_type"]].to_string(index=False))
```
```output
INFO raw.registry: 840 rows
INFO raw.assay: 832 rows
column_name column_type
  result_id     VARCHAR
compound_id     VARCHAR
     target     VARCHAR
      plate     VARCHAR
  replicate     VARCHAR
   relation     VARCHAR
      value     VARCHAR
      units     VARCHAR
   run_date     VARCHAR
       unit     VARCHAR
   operator     VARCHAR
   filename     VARCHAR
```

Every column is `VARCHAR` (text), as intended. The raw assay table has both `units` and `unit`,
and `operator`, the column added in week 5: the raw layer records what arrived, problems
included. Rebuilding the raw layer from the inbox gives the same tables every time, so loading is
**idempotent**: running it twice does no harm ([Series 1, Module
10](../../series-1/10-pipelines-that-survive-failure/)). Real pipelines load only the files they
have not seen before, which Module 2 does with dlt.

## 4. The staging layer: each fix made once

Staging tables are built from raw tables with SQL. We make them **views**: a view is a saved
query that looks like a table and runs whenever it is read, so it is always up to date with the
raw layer beneath it.

First the compounds. Every registry export is a full snapshot, so the current registry is simply
the latest file. In each SMILES, the salt (if any) follows a dot, after the parent molecule;
`split_part(smiles, '.', 1)` keeps the part before the first dot, the parent that was tested.
`::DATE` and `::INTEGER` give each column its type:

```python
db.execute("""
    CREATE OR REPLACE VIEW staging.compounds AS
    SELECT compound_id,
           smiles                       AS smiles_as_registered,
           split_part(smiles, '.', 1)   AS parent_smiles,
           coalesce(salt, '')           AS salt,
           batch::INTEGER               AS batch,
           chemist,
           vendor,
           registered_on::DATE          AS registered_on
    FROM raw.registry
    WHERE filename = (SELECT max(filename) FROM raw.registry)
""")
print(db.sql("SELECT count(*) AS compounds, count(*) FILTER (WHERE salt <> '') AS salts "
             "FROM staging.compounds").df().to_string(index=False))
```
```output
 compounds  salts
       240     33
```

`max(filename)` picks the latest file because the names carry their dates in year-month-day
order, which sorts in time order as text. `count(*) FILTER (WHERE ...)` counts only the rows that
match.

Then the results, where all three problems of section 1 are fixed. Each fix is one line of SQL,
with a comment saying why it is there:

- `coalesce(unit, units)` takes the first of the two that is not empty, so the renamed column and
  the old one become one column again;
- a small table of known unit spellings converts every value to nanomolar; a spelling not in the
  table gives an empty value, which we count instead of hiding;
- `QUALIFY row_number() OVER (PARTITION BY result_id ORDER BY filename) = 1` keeps one row per
  `result_id`: `row_number()` numbers the copies of each result in order of file name, and
  `QUALIFY` keeps only the first. The resent file's copies are numbered 2 and dropped.

The view also works out the **pIC50**, the negative log of the molar IC50 (9 − log₁₀ of the value
in nanomolar), which chemists use because each unit is a factor of ten in potency.

```python
db.execute("""
    CREATE OR REPLACE TABLE staging.unit_to_nm AS
    SELECT * FROM (VALUES ('nM', 1.0), ('µM', 1000.0), ('uM', 1000.0), ('μM', 1000.0))
           AS t(unit, factor)
""")
db.execute("""
    CREATE OR REPLACE VIEW staging.results AS
    WITH typed AS (
        SELECT result_id, compound_id, target, plate,
               replicate::INTEGER          AS replicate,
               relation,
               value::DOUBLE               AS value,
               coalesce(unit, units)       AS unit,      -- 'units' was renamed 'unit' in week 5
               run_date::DATE              AS run_date,
               filename
        FROM raw.assay
        -- week 3's file was sent twice: keep the first copy of every result
        QUALIFY row_number() OVER (PARTITION BY result_id ORDER BY filename) = 1
    )
    SELECT typed.* EXCLUDE (filename),
           value * u.factor                    AS ic50_nm,   -- empty if the unit is unknown
           9 - log10(value * u.factor)         AS pic50,
           filename                            AS source_file
    FROM typed LEFT JOIN staging.unit_to_nm AS u USING (unit)
""")
print(db.sql("""
    SELECT count(*)                                  AS results,
           count(DISTINCT result_id)                 AS distinct_ids,
           count(*) FILTER (WHERE ic50_nm IS NULL)   AS unknown_units,
           string_agg(DISTINCT unit, ', ' ORDER BY unit) AS spellings
    FROM staging.results
""").df().to_string(index=False))
```
```output
 results  distinct_ids  unknown_units      spellings
     656           656              0 nM, uM, µM, μM
```

Every result appears once, every unit spelling is known and every value is in nanomolar. The
spellings are still there to see in the `unit` column, because staging cleans data without hiding
where it came from; `source_file` keeps the file name too.

A `LEFT JOIN` keeps every result even if its unit is not in the table (its `ic50_nm` is then
empty), and `EXCLUDE` leaves a column out of `*`. Section 4 of [Series 1, Module
12](../../series-1/12-validating-data/) explained why spellings are converted by a written table
rather than guessed: the table is a decision, on record, that a new spelling has to pass.

## 5. Marts: tables for the chemists' questions

A mart answers a kind of question directly. The lab's first is the one from section 1, for every
compound at once: the potency of each compound on each target. Each compound is measured twice,
so the mart averages the measured replicates, and counts those reported only as weaker than the
highest concentration tested (`>`), which cannot be averaged:

```python
db.execute("""
    CREATE OR REPLACE VIEW marts.potency AS
    SELECT r.compound_id,
           c.parent_smiles,
           r.target,
           count(*)                                   AS n_results,
           count(*) FILTER (WHERE r.relation = '=')   AS n_measured,
           round(avg(r.pic50) FILTER (WHERE r.relation = '='), 2) AS mean_pic50
    FROM staging.results AS r
    JOIN staging.compounds AS c USING (compound_id)
    GROUP BY ALL
""")
print(db.sql("SELECT * FROM marts.potency ORDER BY mean_pic50 DESC NULLS LAST LIMIT 5")
      .df().to_string(index=False))
```
```output
compound_id                                            parent_smiles target  n_results  n_measured  mean_pic50
   LAB-0023  c1cc(C(F)(F)F)c(nc1)Nc2nc(N8CCCC8)c(C(C)C)c(C8CCNCC8)n2   EGFR          2           2        8.37
   LAB-0036 c1cc(C)c(nc1)Nc2nc(c8ccncc8)c(c8cn[nH]c8)c(c8cn[nH]c8)n2   EGFR          2           2        8.01
   LAB-0042                          O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2   EGFR          2           2        7.91
   LAB-0076               c1cc(Cl)c(nc1)Nc2nc(Br)c(c8cn[nH]c8)c(O)n2   EGFR          2           2        7.79
   LAB-0119    c1cc(C8CCOCC8)c(nc1)Nc2nc(Br)c(c8cn[nH]c8)c(C(=O)N)n2   EGFR          2           2        7.77
```

`GROUP BY ALL` groups by every column that is not a summary (here the compound, its SMILES and
the target), and `NULLS LAST` puts compounds with no measured value at the end. The second mart
answers the project's own question: which compounds are both potent on EGFR and selective? We
call a compound's **selectivity** the difference between its EGFR pIC50 and its best pIC50 on the
other four kinases: a difference of 2 means it is a hundred times more potent on EGFR.

```python
db.execute("""
    CREATE OR REPLACE VIEW marts.selectivity AS
    WITH egfr AS (SELECT compound_id, mean_pic50 AS egfr_pic50
                  FROM marts.potency WHERE target = 'EGFR'),
         panel AS (SELECT compound_id, max(mean_pic50) AS best_other_pic50,
                          count(*) AS panel_targets
                   FROM marts.potency WHERE target <> 'EGFR' GROUP BY compound_id)
    SELECT compound_id, egfr_pic50, best_other_pic50, panel_targets,
           round(egfr_pic50 - best_other_pic50, 2) AS selectivity
    FROM egfr JOIN panel USING (compound_id)
""")
print(db.sql("SELECT count(*) AS on_panel FROM marts.selectivity").fetchall()[0][0],
      "compounds have been through the selectivity panel")
print(db.sql("SELECT * FROM marts.selectivity ORDER BY selectivity DESC LIMIT 5")
      .df().to_string(index=False))
```
```output
32 compounds have been through the selectivity panel
compound_id  egfr_pic50  best_other_pic50  panel_targets  selectivity
   LAB-0023        8.37              5.45              4         2.92
   LAB-0015        7.42              4.70              4         2.72
   LAB-0042        7.91              5.35              4         2.56
   LAB-0039        7.66              5.12              4         2.54
   LAB-0115        7.41              5.03              4         2.38
```

`WITH` gives names to two intermediate queries (`egfr` and `panel`) so the final `SELECT` reads
like the sentence it answers. In the panel's `max`, a compound reported as `>` on a kinase has no
mean, so its weak result does not count as its best: the selectivity shown is the margin over the
kinases where it did show activity.

## 6. The question again

Back to the chemist's question. With the layers in place, everyone reads the same mart:

```python
print(db.sql(f"""
    SELECT compound_id, target, n_results, n_measured, mean_pic50
    FROM marts.potency
    WHERE compound_id = '{QUESTION_COMPOUND}' AND target = 'EGFR'
""").df().to_string(index=False))
print(f"(the truth labdata made it from: pIC50 {lab.true_pic50(QUESTION_COMPOUND, 'EGFR'):.2f})")
```
```output
compound_id target  n_results  n_measured  mean_pic50
   LAB-0057   EGFR          2           2        6.55
(the truth labdata made it from: pIC50 6.66)
```

Two measurements, not four: the duplicate from the resent file is gone. Because `labdata` made the
data, we can compare with the potency it started from; the mart's mean is within the measurement
noise of it. In a real lab nobody knows the truth, which is exactly why the steps between the
files and the answer must be written down, tested and run the same way every time.

The layers can also be checked against each other, which is how a team trusts them. Every
distinct result in the raw layer should be in staging exactly once, and every staged result
should reach the mart:

```python
raw_ids = db.sql("SELECT count(DISTINCT result_id) FROM raw.assay").fetchall()[0][0]
staged = db.sql("SELECT count(*) FROM staging.results").fetchall()[0][0]
in_mart = db.sql("SELECT sum(n_results) FROM marts.potency").fetchall()[0][0]
print(f"raw distinct results {raw_ids} = staged {staged} = counted in the mart {in_mart}:",
      raw_ids == staged == in_mart)
db.close()
```
```output
raw distinct results 656 = staged 656 = counted in the mart 656: True
```

Counts that **reconcile** (agree from one layer to the next) were the backbone of monitoring in
[Series 1, Module 14](../../series-1/14-monitoring-pipelines/). In this series they become tests
that run on every build (Module 5).

## 7. Where Series 1 fits

Series 1 built each part of a chemical data pipeline by hand. In the architecture, each part has a
layer, and in this series each is taken over by a tool:

| Series 1 module (built by hand) | Layer | Series 2 module (the tool) |
|---|---|---|
| 3. Files and identity; 11. Incremental ingestion | Raw | 2. Declarative ingestion (dlt) |
| 4. Databases and schemas | Marts (the shape) | 3. Modelling the warehouse (DuckDB) |
| 6. Validating molecules; 7. Standardisation; 12. Validating data | Staging | 4. Transformations (dbt); 5. Tests and contracts (dbt, pandera-chem) |
| 13. Versioning everything | All layers | 6. History and corrections (dbt); 9. Continuous integration |
| 10. Pipelines that survive failure | Moving between layers | 7. Orchestration (Prefect) |
| 14. Monitoring pipelines | All layers | 8. Observability |
| 15. Capstone | All layers | 10. Dashboards (Streamlit); 11. Capstone |

The by-hand versions are not wasted. A tool does a known job faster and with fewer mistakes, but
when it fails or does something unexpected, the person who understands what it was doing is the
one who can fix it. Series 1 is what lets you understand each tool of this series.

Three principles from this module carry through the series:

1. **Keep the raw data untouched.** Every later step can be fixed and run again, because the
   original is always there.
2. **Make each fix once, in staging, and write down why.** Every reader then gets the same
   answer, and the reason for each fix is in the code, next to the fix.
3. **Check that the layers reconcile.** Counts that agree from raw to staging to marts are the
   first sign that nothing was lost or added on the way.

## Try it yourself

The homework is a few questions, answered by running code like the code above: in a new cell at
the end of the notebook, or in a script. It is at the end of the lesson's page, and in
`homework.md` in the module's folder. The answers are published after the cohort's deadline.

## Further reading

- Reis, J. & Housley, M. (2022). *Fundamentals of Data Engineering: Plan and Build Robust Data
  Systems*. O'Reilly Media. In particular chapter 3, on designing good data architecture.
- Kimball, R. & Ross, M. (2013). *The Data Warehouse Toolkit: The Definitive Guide to Dimensional
  Modeling*, 3rd edition. Wiley. The classic book on shaping data for questions, the subject of
  Module 3.
- The dbt documentation. *How we structure our dbt projects*: the staging, intermediate and marts
  layers, as dbt users build them.
  <https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview>
- The Databricks documentation. *What is the medallion lakehouse architecture?*: the same three
  layers, named bronze, silver and gold. <https://docs.databricks.com/aws/en/lakehouse/medallion>
- The DuckDB documentation. *CSV import*: every option of `read_csv`, including `union_by_name`
  and `filename`. <https://duckdb.org/docs/stable/data/csv/overview>
- Free, S. M. & Wilson, J. W. (1964). A Mathematical Contribution to Structure-Activity Studies.
  *Journal of Medicinal Chemistry*, 7(4), 395–399. The additive model `labdata` uses to make
  potencies from structure. <https://doi.org/10.1021/jm00334a001>
