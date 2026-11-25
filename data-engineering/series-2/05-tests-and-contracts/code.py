"""Tests and contracts in the warehouse: the code of the lesson, in order.

Check every build. dbt tests for keys, values, relationships and the grain, written once next to the models and run after each one; a contract that fixes a table's columns and types; chemistry checks on the compound dimension with pandera-chem. Then two new weeks of data arrive, a test fails, and dbt keeps the wrong rows out of the marts.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/05-tests-and-contracts/
Run it from anywhere, e.g. from the series folder: uv run python 05-tests-and-contracts/code.py
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
import pandera.pandas as pa
import pandera_chem as pc

import labdata
import labstack

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
WAREHOUSE = WORK / "lab.duckdb"
PROJECT = WORK / "lab_dbt"
WEEKS = 6  # the lab is at the end of week 6; weeks 7 and 8 arrive in section 6

shutil.rmtree(WORK, ignore_errors=True)  # start clean
lab = labdata.Lab()
pipeline = labstack.load_raw(lab, WEEKS, WORK / "inbox", WAREHOUSE, WORK / "dlt")
labstack.dbt_project(PROJECT, after=4)


def write(name: str, text: str) -> None:
    """Save one file of the dbt project (made, with its folders, if it is new)."""
    path = PROJECT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8", newline="\n")


def dbt(*args: str):
    """Run a dbt command on the lab's project and log what it did (labstack.dbt)."""
    return labstack.dbt(PROJECT, *args, log=log)


def query(sql: str) -> pd.DataFrame:
    """Run one SQL query on the warehouse and return the answer as a table."""
    with duckdb.connect(str(WAREHOUSE)) as db:
        return db.sql(sql).df()
built = dbt("build")

# ---- 1. dbt's four built-in tests ----
write("models/staging/_staging.yml", """
models:
  - name: stg_compounds
    description: The current registry, one row per compound.
    columns:
      - name: compound_id
        data_tests: [unique, not_null]
  - name: stg_results
    description: One row per result, every value in nanomolar.
    columns:
      - name: result_id
        data_tests: [unique, not_null]
      - name: compound_id
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('stg_compounds')
                field: compound_id
      - name: relation
        data_tests:
          - accepted_values:
              arguments:
                values: ['=', '>']
      - name: ic50_nm
        description: Empty if the unit is not in the unit_to_nm seed.
        data_tests: [not_null]
""")
write("models/marts/_marts.yml", """
models:
  - name: dim_compound
    description: One row per compound in the current registry, with its chemical series and
      properties worked out once with RDKit.
    columns:
      - name: compound_key
        description: The warehouse's key for the compound (a surrogate key).
        data_tests: [unique, not_null]
      - name: compound_id
        description: The lab's ID for the compound (the natural key), e.g. LAB-0042.
        data_tests: [unique, not_null]
      - name: series
        description: The series whose core the parent contains; empty if none or several, for a
          person to check.
      - name: clogp
        description: Crippen's estimate of the octanol-water partition coefficient (RDKit).
  - name: dim_target
    columns:
      - name: target_key
        data_tests: [unique, not_null]
      - name: role
        data_tests:
          - accepted_values:
              arguments:
                values: [primary, panel]
  - name: dim_date
    columns:
      - name: date_key
        data_tests: [unique, not_null]
  - name: fact_measurement
    description: One row per measurement of one compound on one target, in one well of one plate.
    columns:
      - name: compound_key
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_compound')
                field: compound_key
      - name: target_key
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_target')
                field: target_key
      - name: run_date
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_date')
                field: date_key
      - name: relation
        description: "'=' for a measured value; '>' when the compound was weaker than the highest
          concentration tested, so ic50_nm is only a bound."
      - name: pic50
        description: 9 - log10(ic50_nm). Average potencies as pIC50, over measured values only.
  - name: measurements_wide
    description: The star joined once, for dashboards. Built from the star; never edit it.
""")
results = dbt("test")
print(sum(r.status == "pass" for r in results), "of", len(results), "tests passed")

# ---- 2. Your own tests ----
write("macros/unique_combination.sql", """
{% test unique_combination(model, columns) %}
-- every combination of the columns appears once: the rows returned are the ones that repeat
select {{ columns | join(', ') }}, count(*) as copies
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
""")
text = (PROJECT / "models" / "staging" / "_staging.yml").read_text(encoding="utf-8")
write("models/staging/_staging.yml", text.replace(
    """  - name: stg_results
    description: One row per result, every value in nanomolar.
""",
    """  - name: stg_results
    description: One row per result, every value in nanomolar.
    data_tests:
      - unique_combination:  # the grain: one result per compound, target and well
          arguments:
            columns: [compound_id, target, plate, replicate]
""",
))
write("tests/pic50_matches_ic50.sql", """
-- every pIC50 is 9 - log10 of its IC50 in nanomolar
select result_id, ic50_nm, pic50
from {{ ref('fact_measurement') }}
where abs(pic50 - (9 - log10(ic50_nm))) > 1e-9
""")
write("tests/potency_in_plausible_range.sql", """
{{ config(severity='warn') }}
-- measured potencies outside 3 to 10 are possible but rare: a person should look
select result_id, compound_key, target_key, pic50
from {{ ref('fact_measurement') }}
where relation = '=' and (pic50 < 3 or pic50 > 10)
""")
results = dbt("test", "--select", "unique_combination_stg_results_compound_id__target__plate"
              "__replicate pic50_matches_ic50 potency_in_plausible_range")

# ---- 3. A contract ----
CONTRACT = """
  - name: fact_measurement
    description: One row per measurement of one compound on one target, in one well of one plate.
    config:
      contract:
        enforced: true
    columns:
      - name: result_id
        data_type: varchar
        constraints: [{type: not_null}, {type: primary_key}]
      - name: compound_key
        data_type: bigint
        constraints: [{type: not_null}]
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_compound')
                field: compound_key
      - name: target_key
        data_type: bigint
        constraints: [{type: not_null}]
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_target')
                field: target_key
      - name: run_date
        data_type: date
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_date')
                field: date_key
      - name: plate
        data_type: varchar
      - name: replicate
        data_type: integer
      - name: relation
        data_type: varchar
        description: "'=' for a measured value; '>' when the compound was weaker than the highest
          concentration tested, so ic50_nm is only a bound."
      - name: ic50_nm
        data_type: double
      - name: pic50
        data_type: double
        description: 9 - log10(ic50_nm). Average potencies as pIC50, over measured values only.
      - name: source_file
        data_type: varchar
"""
text = (PROJECT / "models" / "marts" / "_marts.yml").read_text(encoding="utf-8")
start = text.index("  - name: fact_measurement")
end = text.index("  - name: measurements_wide")
write("models/marts/_marts.yml", text[:start] + CONTRACT.lstrip("\n") + text[end:])
built = dbt("build", "--select", "fact_measurement")
model = PROJECT / "models" / "marts" / "fact_measurement.sql"
good = model.read_text(encoding="utf-8")
model.write_text(good.replace("r.replicate,", "r.replicate::varchar as replicate,"),
                 encoding="utf-8", newline="\n")
try:
    dbt("build", "--select", "fact_measurement")
except RuntimeError as error:
    print("\n".join(line for line in str(error).splitlines() if line.strip().startswith("|")))
model.write_text(good, encoding="utf-8", newline="\n")  # put the model back

# ---- 4. Checking the chemistry ----
compound_rules = pa.DataFrameSchema({
    "parent_smiles": pa.Column(str, [
        pc.valid_smiles(),
        pc.single_fragment(),
        pc.allowed_elements({"H", "C", "N", "O", "F", "S", "Cl", "Br"}),
        pc.heavy_atoms(10, 60),
        pc.mol_weight(700),
        pc.unique_molecules(),
    ]),
    "series": pa.Column(str, nullable=False),
})
compounds = query("SELECT * FROM marts.dim_compound ORDER BY compound_key")
checked = pc.split(compounds, compound_rules)
print(checked.report)
print(checked.quarantined[["compound_id", "parent_smiles", "reasons"]].to_string(index=False))

# ---- 5. Two more weeks ----
labstack.load_raw(lab, range(7, 9), WORK / "inbox", WAREHOUSE, WORK / "dlt")
built = dbt("build")
print(query("SELECT count(*) AS measurements, max(run_date) AS latest FROM marts.fact_measurement")
      .to_string(index=False))
print(query("""
    SELECT compound_id, target, plate, replicate, count(*) AS copies
    FROM staging.stg_results
    GROUP BY ALL HAVING count(*) > 1
    ORDER BY plate, compound_id, target, replicate
""").head(4).to_string(index=False))
print(query("""
    SELECT result_id, compound_id, target, replicate, value, status
    FROM raw.assay
    WHERE compound_id = 'LAB-0202' AND target = 'ABL1' AND plate = 'P08-01'
    ORDER BY replicate, result_id
""").to_string(index=False))
compounds = query("SELECT * FROM marts.dim_compound ORDER BY compound_key")
checked = pc.split(compounds, compound_rules)
print(checked.report)
print(compounds.loc[compounds["compound_id"] == "LAB-0042", ["compound_id", "parent_smiles",
                                                                "series"]].to_string(index=False))
