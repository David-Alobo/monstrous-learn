"""Transformations with lineage: the code of the lesson, in order.

Hand the staging and mart layers to dbt. Each table becomes one SELECT in a file; dbt works out the order to build them in from the references between them, builds them in DuckDB, records the lineage from raw table to mart, and writes the documentation. The compound dimension's chemistry runs as a Python model.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/04-transformations-with-lineage/
Run it from anywhere, e.g. from the series folder: uv run python 04-transformations-with-lineage/code.py
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
import json
import logging
import os
import shutil
from pathlib import Path

import duckdb
import pandas as pd
from dbt.cli.main import dbtRunner

import labdata
import labstack

os.environ["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"  # no usage statistics sent to dbt's makers
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
WAREHOUSE = WORK / "lab.duckdb"
PROJECT = WORK / "lab_dbt"  # the lab's dbt project: one folder of text files
WEEKS = 6  # the lab is at the end of week 6, as in Modules 1 to 3

shutil.rmtree(WORK, ignore_errors=True)  # start clean
lab = labdata.Lab()
labstack.load_raw(lab, WEEKS, WORK / "inbox", WAREHOUSE, WORK / "dlt")


def write(name: str, text: str) -> None:
    """Save one file of the dbt project (made, with its folders, if it is new)."""
    path = PROJECT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8", newline="\n")


def dbt(*args: str):
    """Run a dbt command on the lab's project, like `dbt <args>` in a terminal; log what it did."""
    result = dbtRunner().invoke(
        [*args, "--quiet", "--project-dir", str(PROJECT), "--profiles-dir", str(PROJECT)]
    )
    if result.exception:
        raise result.exception
    if args[0] in ("build", "run", "seed", "test"):
        for item in result.result:
            log.info("%s %s: %s", item.node.resource_type, item.node.name, item.status)
        broken = [item.node.name for item in result.result if item.status == "error"]
        if broken:
            raise RuntimeError(f"dbt could not build {broken}: see {PROJECT}/logs/dbt.log")
    return result.result


def query(sql: str) -> pd.DataFrame:
    """Run one SQL query on the warehouse and return the answer as a table."""
    with duckdb.connect(str(WAREHOUSE)) as db:
        return db.sql(sql).df()

# ---- 1. A dbt project ----
write("dbt_project.yml", """
name: lab
version: "1.0.0"
profile: lab

vars:  # settings the models read with var('...')
  project_start: "2026-09-07"  # the Monday of week 1
  project_end: "2026-11-30"  # the Monday after week 12

models:
  lab:
    staging:
      +schema: staging
      +materialized: view
    marts:
      +schema: marts
      +materialized: table

seeds:
  lab:
    +schema: staging
""")
write("profiles.yml", """
lab:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "{{ env_var('LAB_WAREHOUSE', 'work/lab.duckdb') }}"
      threads: 1
""")
write("macros/generate_schema_name.sql", """
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name or target.schema }}
{%- endmacro %}
""")

# ---- 2. Sources and seeds ----
write("models/staging/_sources.yml", """
sources:
  - name: raw
    description: The lab's files, loaded unchanged by dlt (Module 2).
    schema: raw
    tables:
      - name: registry
        description: The latest compound registry export. Replaced on every load.
      - name: assay
        description: Every row of every assay file, merged on result_id.
""")
write("seeds/unit_to_nm.csv", """
unit,factor
nM,1.0
µM,1000.0
uM,1000.0
μM,1000.0
""")
targets = pd.DataFrame(
    [(gene, chembl_id, "primary" if gene == labdata.PRIMARY else "panel")
     for gene, chembl_id in labdata.TARGETS.items()],
    columns=["target", "chembl_id", "role"],
)
write("seeds/targets.csv", targets.to_csv(index=False, lineterminator="\n"))
dbt("seed")
print(query("SELECT * FROM staging.targets").to_string(index=False))

# ---- 3. Staging models ----
write("models/staging/stg_compounds.sql", """
-- the current registry: one row per compound, the salt split from the parent that was tested
select compound_id,
       smiles                      as smiles_as_registered,
       split_part(smiles, '.', 1)  as parent_smiles,
       coalesce(salt, '')          as salt,
       batch::integer              as batch,
       chemist,
       vendor,
       registered_on::date         as registered_on
from {{ source('raw', 'registry') }}
""")
write("models/staging/stg_results.sql", """
-- one row per result: the unit columns joined back together, every value in nanomolar
with typed as (
    select result_id, compound_id, target, plate,
           replicate::integer      as replicate,
           relation,
           value::double           as value,
           coalesce(unit, units)   as unit,  -- 'units' was renamed 'unit' in week 5
           run_date::date          as run_date,
           file_name
    from {{ source('raw', 'assay') }}
)
select typed.* exclude (file_name),
       value * u.factor              as ic50_nm,
       9 - log10(value * u.factor)   as pic50,
       file_name                     as source_file
from typed
left join {{ ref('unit_to_nm') }} as u using (unit)
""")
dbt("run", "--select", "staging")
compiled = PROJECT / "target" / "compiled" / "lab" / "models" / "staging" / "stg_results.sql"
print("\n".join(compiled.read_text(encoding="utf-8").splitlines()[-3:]))

# ---- 4. The marts ----
write("models/marts/dim_target.sql", """
-- one row per kinase; the primary target gets key 1
select row_number() over (order by role desc, target) as target_key,
       target, chembl_id, role
from {{ ref('targets') }}
""")
write("models/marts/dim_date.sql", """
-- one row per day of the project, with each way the lab groups days
with days as (
    select day::date as date_key
    from generate_series(date '{{ var("project_start") }}', date '{{ var("project_end") }}',
                         interval 1 day) as t(day)
)
select date_key,
       (datediff('day', date '{{ var("project_start") }}', date_key) // 7) + 1 as project_week,
       isodow(date_key) > 5   as weekend,
       dayname(date_key)      as weekday,
       monthname(date_key)    as month
from days
""")
write("models/marts/dim_compound.py", '''
"""One row per compound, with its series and properties worked out once (Module 3)."""
from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, Lipinski

RDLogger.DisableLog("rdApp.*")
# the three chemical series, each as the core its compounds share
SERIES = {
    "aminopyrimidines": "c1ccc(nc1)Nc2ncccn2",
    "pyrimidine piperazines": "c1nccc(n1)N2CCN(CC2)C(=O)c3ccccc3",
    "ureas": "O=C(Nc1ccccc1)Nc2cccnc2",
}
CORES = {name: Chem.MolFromSmiles(core) for name, core in SERIES.items()}


def series_of(mol):
    """The series whose core the molecule contains (None if no core, or several)."""
    hits = [name for name, core in CORES.items() if mol.HasSubstructMatch(core)]
    return hits[0] if len(hits) == 1 else None


def model(dbt, session):
    compounds = dbt.ref("stg_compounds").df().sort_values("compound_id", ignore_index=True)
    mols = [Chem.MolFromSmiles(s) for s in compounds["parent_smiles"]]
    compounds.insert(0, "compound_key", range(1, len(compounds) + 1))
    compounds["series"] = [series_of(m) for m in mols]
    compounds["mw"] = [round(Descriptors.MolWt(m), 1) for m in mols]
    compounds["clogp"] = [round(Crippen.MolLogP(m), 2) for m in mols]
    compounds["hbd"] = [Lipinski.NumHDonors(m) for m in mols]
    compounds["hba"] = [Lipinski.NumHAcceptors(m) for m in mols]
    compounds["heavy_atoms"] = [m.GetNumHeavyAtoms() for m in mols]
    return compounds
''')
write("models/marts/fact_measurement.sql", """
-- one row per measurement: one compound, one target, one well (replicate) of one plate
select r.result_id,
       c.compound_key,
       t.target_key,
       r.run_date,
       r.plate,
       r.replicate,
       r.relation,
       r.ic50_nm,
       r.pic50,
       r.source_file
from {{ ref('stg_results') }} as r
join {{ ref('dim_compound') }} as c using (compound_id)
join {{ ref('dim_target') }} as t using (target)
""")
write("models/marts/measurements_wide.sql", """
{{ config(materialized='view') }}
-- the star joined once, for dashboards and spreadsheets
select f.result_id, f.plate, f.replicate, f.relation, f.ic50_nm, f.pic50,
       c.compound_id, c.parent_smiles, c.series, c.chemist, c.vendor, c.mw, c.clogp,
       t.target, t.role as target_role,
       d.date_key as run_date, d.project_week as run_week
from {{ ref('fact_measurement') }} as f
join {{ ref('dim_compound') }} as c using (compound_key)
join {{ ref('dim_target') }} as t using (target_key)
join {{ ref('dim_date') }} as d on d.date_key = f.run_date
""")
built = dbt("build")
print(query("""
    SELECT (SELECT count(*) FROM marts.dim_compound)      AS compounds,
           (SELECT count(*) FROM marts.dim_compound WHERE series IS NULL) AS without_series,
           (SELECT count(*) FROM marts.dim_date)          AS days,
           (SELECT count(*) FROM marts.fact_measurement)  AS measurements,
           (SELECT count(*) FROM marts.measurements_wide) AS wide_rows
""").to_string(index=False))

# ---- 5. Lineage ----
manifest = json.loads((PROJECT / "target" / "manifest.json").read_text(encoding="utf-8"))
for node in sorted(manifest["nodes"].values(), key=lambda n: n["name"]):
    if node["resource_type"] == "model":
        parents = sorted(p.split(".")[-1] for p in node["depends_on"]["nodes"])
        print(f"{node['name']:18} <- {', '.join(parents)}")
log.info("upstream of fact_measurement:")
upstream = dbt("ls", "--select", "+fact_measurement")
log.info("downstream of stg_compounds:")
downstream = dbt("ls", "--select", "stg_compounds+")
text = (PROJECT / "models" / "staging" / "stg_results.sql").read_text(encoding="utf-8")
write("models/staging/stg_results.sql", text.replace(
    "       9 - log10(value * u.factor)   as pic50,",
    "       9 - log10(value * u.factor)   as pic50,\n"
    "       relation = '='                as is_measured,  -- a value, not a bound",
))
rebuilt = dbt("build", "--select", "stg_results+")
print(query("SELECT is_measured, count(*) AS results FROM staging.stg_results "
            "GROUP BY ALL ORDER BY is_measured").to_string(index=False))

# ---- 6. Documentation ----
write("models/marts/_marts.yml", """
models:
  - name: dim_compound
    description: One row per compound in the current registry, with its chemical series and
      properties worked out once with RDKit.
    columns:
      - name: compound_key
        description: The warehouse's key for the compound (a surrogate key).
      - name: compound_id
        description: The lab's ID for the compound (the natural key), e.g. LAB-0042.
      - name: series
        description: The series whose core the parent contains; empty if none or several, for a
          person to check.
      - name: clogp
        description: Crippen's estimate of the octanol-water partition coefficient (RDKit).
  - name: fact_measurement
    description: One row per measurement of one compound on one target, in one well of one plate.
    columns:
      - name: relation
        description: "'=' for a measured value; '>' when the compound was weaker than the highest
          concentration tested, so ic50_nm is only a bound."
      - name: pic50
        description: 9 - log10(ic50_nm). Average potencies as pIC50, over measured values only.
  - name: measurements_wide
    description: The star joined once, for dashboards. Built from the star; never edit it.
""")
dbt("docs", "generate")
catalog = json.loads((PROJECT / "target" / "catalog.json").read_text(encoding="utf-8"))
columns = catalog["nodes"]["model.lab.fact_measurement"]["columns"]
print({name: column["type"] for name, column in columns.items()})
manifest = json.loads((PROJECT / "target" / "manifest.json").read_text(encoding="utf-8"))
print(manifest["nodes"]["model.lab.fact_measurement"]["columns"]["pic50"]["description"])
for path in sorted(PROJECT.rglob("*")):
    made_by_dbt = {"target", "logs"} & set(path.relative_to(PROJECT).parts)  # dbt's own output
    if path.is_file() and not made_by_dbt:
        print(path.relative_to(PROJECT).as_posix())
