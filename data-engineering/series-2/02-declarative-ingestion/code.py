"""Declarative ingestion: the code of the lesson, in order.

Load the lab's files and ChEMBL's API into the raw layer with dlt. Declare what to load and how to recognise each row; let the tool infer the schema, remember what it has loaded, absorb duplicates, and either follow or refuse a change in the data's shape.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/02-declarative-ingestion/
Run it from anywhere, e.g. from the series folder: uv run python 02-declarative-ingestion/code.py
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

# ---- 2. A snapshot: the compound registry ----
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
columns = pipeline.default_schema.get_table_columns("registry")
print({name: column["data_type"] for name, column in columns.items()})

# ---- 3. Files, incrementally: the assay results ----
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
    # sorted by table: dlt's own order can change from run to run
    return {table: n for table, n in sorted(counts.items()) if not table.startswith("_dlt")}


for week in range(1, WEEKS + 1):
    pipeline.run(assay())  # the files of all six weeks are already in the inbox
    log.info("run %d: %s", week, rows_loaded(pipeline))
cursor = pipeline.state["sources"]["lab"]["resources"]["assay"]["incremental"]["file_name"]
print("last file loaded:", cursor["last_value"])
print(query("SELECT count(*) AS rows, count(DISTINCT result_id) AS results FROM raw.assay")
      .to_string(index=False))
print(query("SELECT file_name, count(*) AS rows FROM raw.assay GROUP BY ALL ORDER BY file_name")
      .to_string(index=False))

# ---- 4. When the data changes shape ----
assay_columns = pipeline.default_schema.get_table_columns("assay")
print([name for name in assay_columns if not name.startswith("_dlt")])
print(query("SELECT count(units) AS with_units, count(unit) AS with_unit FROM raw.assay")
      .to_string(index=False))
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
strict.abort_packages()
cursor = strict.state["sources"]["lab_strict"]["resources"]["assay"]["incremental"]["file_name"]
print("pending packages left:", strict.has_pending_data)
print("last file loaded, back to:", cursor["last_value"])
allowed = assay_strict()
allowed.apply_hints(schema_contract={"columns": "evolve"})  # for this run only
strict.run(allowed)
log.info("week 5, after the decision: loaded %s", rows_loaded(strict))
lab.write_week(6, WEEKLY)
strict.run(assay_strict())  # frozen again, and week 6 fits the schema as it now is
log.info("week 6: loaded %s", rows_loaded(strict))
print(query("SELECT file_name, count(*) AS rows, count(unit) AS with_unit FROM raw_strict.assay "
            "GROUP BY ALL ORDER BY file_name").to_string(index=False))

# ---- 5. An API, declared: ChEMBL ----
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
columns = public.default_schema.get_table_columns("chembl_activities")
print({name: column["data_type"] for name, column in columns.items()
       if not name.startswith("_dlt")})

# ---- 6. What dlt records about every load ----
print(query("""
    SELECT schema_name, count(*) AS loads, max(status) AS status
    FROM raw._dlt_loads GROUP BY ALL ORDER BY schema_name
""").to_string(index=False))
print(query("SELECT schema_name FROM information_schema.schemata "
            "WHERE catalog_name = 'lab' ORDER BY schema_name").to_string(index=False))
