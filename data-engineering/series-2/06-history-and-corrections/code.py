"""History and corrections: the code of the lesson, in order.

Labs correct their data. Keep every version of each compound with dbt snapshots, taken week by week; keep superseded assay readings on record but out of the marts; and build the fact table incrementally, so that each week's build processes only that week's results.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/06-history-and-corrections/
Run it from anywhere, e.g. from the series folder: uv run python 06-history-and-corrections/code.py
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

# ---- 2. Snapshots, taken week by week ----
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
for week in range(1, 9):
    labstack.load_raw(lab, range(week, week + 1), INBOX, WAREHOUSE, PIPELINES)
    dbt("snapshot")
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

# ---- 3. A history dimension ----
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

# ---- 4. Corrected results ----
write("models/staging/stg_results.sql", """
-- one row per result, every reading kept with its status; every value in nanomolar
{%- set columns = adapter.get_columns_in_relation(source('raw', 'assay'))
    | map(attribute='name') | list %}
with typed as (
    select result_id, compound_id, target, plate,
           replicate::integer      as replicate,
           relation,
           value::double           as value,
           coalesce(unit, units)   as unit,  -- 'units' was renamed 'unit' in week 5
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

# ---- 5. An incremental fact table ----
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
edit("models/marts/measurements_wide.sql",
     "join {{ ref('dim_date') }} as d on d.date_key = f.run_date\n",
     "join {{ ref('dim_date') }} as d on d.date_key = f.run_date\n"
     "where f.status <> 'superseded'  -- a corrected reading replaces it\n")
built = dbt("build", "--full-refresh")
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

# ---- 6. What the warehouse keeps now ----
log.info("everything built from the snapshot:")
names = dbt("ls", "--select", "registry_history+")
