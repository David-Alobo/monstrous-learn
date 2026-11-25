"""Designing a lab data architecture: the code of the lesson, in order.

From a folder of spreadsheets to layers a team can trust. Land the lab's files untouched, clean them in one place, shape them for the questions chemists ask, and see where each piece of Series 1 fits in a modern data stack.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/01-lab-data-architecture/
Run it from anywhere, e.g. from the series folder: uv run python 01-lab-data-architecture/code.py
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

# ---- 1. The lab and its folder of files ----
for week in range(1, WEEKS + 1):
    written = lab.write_week(week, INBOX)
    log.info("week %d: %s", week, ", ".join(p.name for p in written))
registry = pd.read_csv(INBOX / "registry_2026-10-12.csv")
print(registry.head(3).to_string(index=False))
print()
assay = pd.read_csv(INBOX / "assay_2026-09-14.csv")
print(assay.head(3).to_string(index=False))
print(lab.events.to_string(index=False))
files = sorted(INBOX.glob("assay_*.csv"))
stacked = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
answer = stacked[(stacked["compound_id"] == QUESTION_COMPOUND) & (stacked["target"] == "EGFR")]
print(answer[["result_id", "value", "units", "relation"]].to_string(index=False))
print(f"{len(stacked)} rows; {stacked['result_id'].duplicated().sum()} result ids appear twice")
print("columns:", list(stacked.columns))

# ---- 2. Three layers ----
db = duckdb.connect(str(WAREHOUSE))
for layer in ["raw", "staging", "marts"]:
    db.execute(f"CREATE SCHEMA IF NOT EXISTS {layer}")
print(db.sql("SELECT schema_name FROM information_schema.schemata "
             "WHERE catalog_name = 'lab' ORDER BY schema_name").fetchall())

# ---- 3. The raw layer: the files, unchanged ----
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

# ---- 4. The staging layer: each fix made once ----
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

# ---- 5. Marts: tables for the chemists' questions ----
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

# ---- 6. The question again ----
print(db.sql(f"""
    SELECT compound_id, target, n_results, n_measured, mean_pic50
    FROM marts.potency
    WHERE compound_id = '{QUESTION_COMPOUND}' AND target = 'EGFR'
""").df().to_string(index=False))
print(f"(the truth labdata made it from: pIC50 {lab.true_pic50(QUESTION_COMPOUND, 'EGFR'):.2f})")
raw_ids = db.sql("SELECT count(DISTINCT result_id) FROM raw.assay").fetchall()[0][0]
staged = db.sql("SELECT count(*) FROM staging.results").fetchall()[0][0]
in_mart = db.sql("SELECT sum(n_results) FROM marts.potency").fetchall()[0][0]
print(f"raw distinct results {raw_ids} = staged {staged} = counted in the mart {in_mart}:",
      raw_ids == staged == in_mart)
db.close()
