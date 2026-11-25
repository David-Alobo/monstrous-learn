"""Orchestration: the code of the lesson, in order.

Run the lab's weekly pipeline as a Prefect flow. Receive the files, load them, snapshot, build and test, check the chemistry, draw the new compounds and publish, as tasks that retry when something flaky fails, reuse work already done, stop before publishing anything wrong, and keep a record of every run. Then schedule it.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/07-orchestration/
Run it from anywhere, e.g. from the series folder: uv run python 07-orchestration/code.py
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
import shutil
from collections import Counter
from pathlib import Path

WORK = Path("work")  # where the lesson writes its files (git-ignored)
shutil.rmtree(WORK, ignore_errors=True)  # start clean, before Prefect keeps its files in work/
(WORK / "prefect").mkdir(parents=True)
os.environ["PREFECT_HOME"] = str((WORK / "prefect").resolve())
os.environ["PREFECT_SERVER_ANALYTICS_ENABLED"] = "false"

import duckdb
import pandas as pd
import pandera.pandas as pa
import pandera_chem as pc
from prefect import flow, get_run_logger, task
from prefect.cache_policies import INPUTS
from prefect.client.orchestration import get_client
from rdkit import Chem, RDLogger
from rdkit.Chem import Draw

import labdata
import labstack

RDLogger.DisableLog("rdApp.*")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)  # not every request Prefect makes
quiet = logging.getLogger("dbt-lines")  # labstack.dbt logs one line per model here: unseen
quiet.propagate = False


def named(record: logging.LogRecord) -> bool:
    """Start each of Prefect's lines with its run's name, and leave out tracebacks."""
    name = getattr(record, "task_run_name", None) or getattr(record, "flow_run_name", None)
    if name:
        record.msg, record.args = f"{name}: {record.getMessage()}", ()
    record.exc_info = record.exc_text = None  # the full traceback stays in Prefect's record
    return True


def no_server_notice(record: logging.LogRecord) -> bool:
    """Hide Prefect's notice of the temporary server it starts (its time and port vary)."""
    return "temporary server" not in record.getMessage()


for name in ("prefect.flow_runs", "prefect.task_runs"):
    logging.getLogger(name).addFilter(named)
logging.getLogger("prefect").addFilter(no_server_notice)

INBOX = WORK / "inbox"
WAREHOUSE = WORK / "lab.duckdb"
PUBLISHED = WORK / "published"  # what the dashboards of Module 10 read
SHARE_FAILS_ONCE = {9}  # weeks in which the lab's file share fails at the first attempt

lab = labdata.Lab()
PROJECT = labstack.warehouse_at(lab, 8, WORK)
pipeline = labstack.lab_pipeline(WAREHOUSE, WORK / "dlt")
attempts = Counter()  # how often each week's files have been asked for

# ---- 1. Tasks and a flow ----
@task(retries=2, retry_delay_seconds=1, task_run_name="receive week {week}")
def receive(week: int) -> list[str]:
    """Copy the week's files from the lab's share into the inbox."""
    attempts[week] += 1
    if week in SHARE_FAILS_ONCE and attempts[week] == 1:
        raise ConnectionError("the lab's file share did not answer")
    files = [path.name for path in lab.write_week(week, INBOX)]
    get_run_logger().info("received %s", ", ".join(files))
    return files


@task(task_run_name="load week {week}")
def load(week: int, files: list[str]) -> dict[str, int]:
    """Load what is new in the inbox into the raw layer, with Module 2's dlt pipeline."""
    rows = labstack.load_inbox(INBOX, pipeline)
    get_run_logger().info("loaded %s", rows)
    if not any(name.startswith("assay_") for name in files):
        get_run_logger().warning("no assay file arrived for week %d", week)
    return rows
@task(task_run_name="snapshot")
def snapshot() -> None:
    """Take this week's snapshot of the registry (Module 6), before anything else changes it."""
    labstack.dbt(PROJECT, "snapshot", log=quiet)


@task(task_run_name="build")
def build() -> dict[str, int]:
    """Build and test the warehouse with dbt; fail if any test fails."""
    try:
        results = labstack.dbt(PROJECT, "build", log=quiet)
    except labstack.BuildError as error:  # a model could not be built: say which, and why
        raise RuntimeError(error.short) from None
    counts = dict(sorted(Counter(str(r.status) for r in results).items()))
    get_run_logger().info("dbt build: %s", counts)
    failed = [r.node.name for r in results if r.status == "fail"]
    if failed:
        raise RuntimeError(f"tests failed: {failed}")
    return counts
COMPOUND_RULES = pa.DataFrameSchema({
    "parent_smiles": pa.Column(str, [pc.valid_smiles(), pc.single_fragment()]),
    "series": pa.Column(str, nullable=False),
})


def query(sql: str) -> pd.DataFrame:
    """Run one SQL query on the warehouse and return the answer as a table."""
    with duckdb.connect(str(WAREHOUSE)) as db:
        return db.sql(sql).df()


@task(task_run_name="check chemistry")
def check_chemistry() -> list[str]:
    """Check every compound's structure and series with pandera-chem; warn about any that fail."""
    checked = pc.split(query("SELECT * FROM marts.dim_compound"), COMPOUND_RULES)
    quarantined = sorted(checked.quarantined["compound_id"])
    if quarantined:
        get_run_logger().warning("for a chemist to look at: %s", quarantined)
    return quarantined


@task(cache_policy=INPUTS, task_run_name="draw week {week}'s compounds")
def draw(week: int, compounds: dict[str, str]) -> int:
    """Draw each new compound as an SVG picture for the dashboards."""
    folder = PUBLISHED / "structures"
    folder.mkdir(parents=True, exist_ok=True)
    for compound_id, smiles in compounds.items():
        svg = Draw.MolsToGridImage([Chem.MolFromSmiles(smiles)], subImgSize=(300, 220),
                                   useSVG=True)
        (folder / f"{compound_id}.svg").write_text(svg, encoding="utf-8")
    get_run_logger().info("drew %d compounds", len(compounds))
    return len(compounds)


@task(task_run_name="publish")
def publish() -> int:
    """Save the wide table, the dashboards' source, as a Parquet file."""
    PUBLISHED.mkdir(exist_ok=True)
    wide = query("SELECT * FROM marts.measurements_wide")
    wide.to_parquet(PUBLISHED / "measurements.parquet", index=False)
    return len(wide)
@flow(name="lab-weekly", flow_run_name="week {week}")
def weekly(week: int) -> dict:
    """The lab's weekly pipeline: receive, load, snapshot, build and test, check, draw, publish."""
    files = receive(week)
    load(week, files)
    snapshot()
    counts = build()
    quarantined = check_chemistry()
    new = query(f"""
        SELECT compound_id, parent_smiles FROM marts.dim_compound
        WHERE registered_on >= DATE '{labdata.monday(week)}'
          AND registered_on < DATE '{labdata.monday(week + 1)}'
    """)
    drawn = draw(week, dict(zip(new["compound_id"], new["parent_smiles"])))
    rows = publish()
    summary = {"tests": counts.get("pass", 0), "drawn": drawn, "published": rows,
               "quarantined": len(quarantined)}
    get_run_logger().info("%s", summary)
    return summary

# ---- 2. Running it ----
summary = weekly(9)
logging.getLogger("prefect.task_runs").setLevel(logging.WARNING)  # task warnings only, from here
for week in (10, 11, 12):
    state = weekly(week, return_state=True)
    log.info("week %d: %s", week, state.name)

# ---- 3. When a step fails ----
wide_sql = PROJECT / "models" / "marts" / "measurements_wide.sql"
good = wide_sql.read_text(encoding="utf-8")
wide_sql.write_text(good.replace("c.chemist,", "c.chemst,"), encoding="utf-8", newline="\n")
state = weekly(12, return_state=True)
log.info("week 12: %s", state.name)
wide_sql.write_text(good, encoding="utf-8", newline="\n")
logging.getLogger("prefect.task_runs").setLevel(logging.INFO)  # every task's lines again
summary = weekly(12)

# ---- 4. The record ----
with get_client(sync_client=True) as client:
    runs = client.read_flow_runs()
for run in sorted(runs, key=lambda r: r.expected_start_time):
    print(f"{run.name:8} {run.state_name}")
