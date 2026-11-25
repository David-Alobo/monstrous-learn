"""Observability: the code of the lesson, in order.

Know when something is wrong before the chemists do. After each weekly run, record what arrived and what the warehouse holds, and check it against what is normal - freshness on two clocks, volume, schema changes, changed registrations and drift in the molecules' properties - and send an alert when a check fails. Run the lab's weeks 5 to 12 and see every planted problem reported in the week it happened.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/08-observability/
Run it from anywhere, e.g. from the series folder: uv run python 08-observability/code.py
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
from datetime import timedelta
from pathlib import Path

WORK = Path("work")  # where the lesson writes its files (git-ignored)
shutil.rmtree(WORK, ignore_errors=True)  # start clean, before Prefect keeps its files in work/
(WORK / "prefect").mkdir(parents=True)
os.environ["PREFECT_HOME"] = str((WORK / "prefect").resolve())
os.environ["PREFECT_SERVER_ANALYTICS_ENABLED"] = "false"

import duckdb
import pandas as pd
import requests
from prefect import flow, get_run_logger, task

import labdata
import labstack

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
    record.exc_info = record.exc_text = None
    return True


for name in ("prefect.flow_runs", "prefect.task_runs"):
    logging.getLogger(name).addFilter(named)
logging.getLogger("prefect").addFilter(lambda r: "temporary server" not in r.getMessage())

INBOX = WORK / "inbox"
WAREHOUSE = WORK / "lab.duckdb"
BASELINE_WEEKS = 4  # the weeks the checks treat as normal, to compare the others with
DRIFT_LIMIT = 1.0  # alert when a property moves this many reference standard deviations
VOLUME_RANGE = (0.5, 1.5)  # alert when a week brings less than half or more than 1.5 times usual

lab = labdata.Lab()
PROJECT = labstack.warehouse_at(lab, BASELINE_WEEKS, WORK)
pipeline = labstack.lab_pipeline(WAREHOUSE, WORK / "dlt")


def query(sql: str) -> pd.DataFrame:
    """Run one SQL query on the warehouse and return the answer as a table."""
    with duckdb.connect(str(WAREHOUSE)) as db:
        return db.sql(sql).df()


def execute(sql: str, *parameters) -> None:
    """Run one SQL statement that changes the warehouse."""
    with duckdb.connect(str(WAREHOUSE)) as db:
        db.execute(sql, list(parameters))

# ---- 1. What to watch ----
execute("CREATE SCHEMA monitoring")
execute("CREATE TABLE monitoring.metrics (week INTEGER, name VARCHAR, value DOUBLE)")
execute("CREATE TABLE monitoring.alerts (week INTEGER, check_name VARCHAR, message VARCHAR)")

# ---- 2. The weekly run, and its metrics ----
@task(task_run_name="run week {week}")
def run_week(week: int) -> dict[str, int]:
    """The weekly pipeline of Module 7: receive, load, snapshot, build and test."""
    lab.write_week(week, INBOX)
    rows = labstack.load_inbox(INBOX, pipeline)
    labstack.dbt(PROJECT, "snapshot", log=quiet)
    labstack.dbt(PROJECT, "build", log=quiet)
    return rows


@task(task_run_name="record metrics")
def record_metrics(week: int, rows: dict[str, int] | None) -> None:
    """Save this week's metrics, for the checks of later weeks to compare with."""
    newest = query("SELECT max(run_date) AS d FROM marts.fact_measurement")["d"][0]
    version = query("SELECT max(version) AS v FROM raw._dlt_version")["v"][0]
    metrics = {
        "newest_run_date": newest.toordinal(),  # a date, kept as a number of days
        "schema_version": version,
    }
    if rows is not None:  # how many rows arrived (unknown for the baseline week)
        metrics["assay_rows"] = rows.get("assay", 0)
    for name, value in metrics.items():
        execute("INSERT INTO monitoring.metrics VALUES (?, ?, ?)", week, name, float(value))


def metric(name: str, before: int) -> pd.Series:
    """A metric's history: its value in each week before `before`, by week."""
    return query(f"""
        SELECT week, value FROM monitoring.metrics
        WHERE name = '{name}' AND week < {before} ORDER BY week
    """).set_index("week")["value"]
record_metrics.fn(BASELINE_WEEKS, None)
print(query("SELECT * FROM monitoring.metrics").to_string(index=False))

# ---- 3. Freshness, on both clocks ----
sources = PROJECT / "models" / "staging" / "_sources.yml"
text = sources.read_text(encoding="utf-8")
sources.write_text(text.replace("""      - name: assay
        description: Every row of every assay file, merged on result_id.
""", """      - name: assay
        description: Every row of every assay file, merged on result_id.
        loaded_at_field: to_timestamp(_dlt_load_id::double)  # when dlt loaded the row
        freshness:
          warn_after: {count: 8, period: day}  # the lab loads every 7 days
          error_after: {count: 15, period: day}
"""), encoding="utf-8", newline="\n")
results = labstack.dbt(PROJECT, "source", "freshness", log=quiet)
print({r.node.name: str(r.status) for r in results})
@task(task_run_name="check freshness")
def check_freshness(week: int) -> list[str]:
    """The newest result should have been run this week."""
    newest = metric("newest_run_date", week + 1)[week]
    expected = (labdata.monday(week) + timedelta(days=2)).toordinal()  # the week's Wednesday
    behind = int(expected - newest)
    if behind > 0:
        return [f"the newest result is {behind} days old: no plates were run this week"]
    return []

# ---- 4. Volume and schema ----
@task(task_run_name="check volume")
def check_volume(week: int) -> list[str]:
    """About as many assay rows as usual should have arrived."""
    history = metric("assay_rows", week + 1)
    if len(history) < 3:
        return []
    usual, now = history.iloc[:-1].median(), history.iloc[-1]
    low, high = VOLUME_RANGE
    if not low * usual <= now <= high * usual:
        return [f"{now:.0f} assay rows arrived; usually about {usual:.0f}"]
    return []
def columns_in(version: int) -> dict[str, set[str]]:
    """The columns of each of the lab's tables in one version of dlt's schema."""
    schema = json.loads(query(f"SELECT schema FROM raw._dlt_version WHERE version = {version}")
                        ["schema"][0])
    return {name: set(table["columns"]) for name, table in schema["tables"].items()
            if not name.startswith("_dlt")}


@task(task_run_name="check schema")
def check_schema(week: int) -> list[str]:
    """The raw layer's columns should not change without someone knowing."""
    versions = metric("schema_version", week + 1)
    if len(versions) < 2 or versions.iloc[-1] == versions.iloc[-2]:
        return []
    old, new = columns_in(int(versions.iloc[-2])), columns_in(int(versions.iloc[-1]))
    alerts = []
    for table in sorted(new):
        added, removed = new[table] - old.get(table, set()), old.get(table, set()) - new[table]
        if added or removed:
            alerts.append(f"raw.{table} changed: added {sorted(added)}, removed {sorted(removed)}")
    return alerts
@task(task_run_name="check registrations")
def check_registrations(week: int) -> list[str]:
    """A compound registered before should not change without someone knowing."""
    changed = query(f"""
        SELECT compound_id FROM marts.dim_compound_history
        WHERE version > 1 AND valid_from = DATE '{labdata.monday(week)}'
        ORDER BY compound_id
    """)["compound_id"].tolist()
    return [f"registration changed: {', '.join(changed)}"] if changed else []

# ---- 5. Drift in the molecules ----
PROPERTIES = ["mw", "clogp", "heavy_atoms"]


@task(task_run_name="check drift")
def check_drift(week: int) -> list[str]:
    """This week's compounds should look like the usual ones, or someone should know why."""
    compounds = query("SELECT * FROM marts.dim_compound")
    days = compounds["registered_on"] - pd.Timestamp(labdata.START)
    compounds["week"] = days.dt.days // 7 + 1
    baseline = compounds[compounds["week"] <= BASELINE_WEEKS]
    earlier = compounds[compounds["week"] < week]
    new = compounds[compounds["week"] == week]
    alerts = []
    for prop in PROPERTIES:
        moved = (new[prop].mean() - baseline[prop].mean()) / baseline[prop].std()
        execute("INSERT INTO monitoring.metrics VALUES (?, ?, ?)", week, f"drift_{prop}", moved)
        if abs(moved) >= DRIFT_LIMIT:
            by_series = {
                series: (group[prop].mean() - baseline.loc[baseline["series"] == series, prop]
                         .mean()) / baseline[prop].std()
                for series, group in new.groupby("series")
            }
            worst = max(by_series, key=lambda s: abs(by_series[s]))
            alerts.append(f"{prop} moved {moved:+.1f} SD from the baseline, most in the "
                          f"{worst} ({by_series[worst]:+.1f} SD)")
    for column in ("chemist", "vendor"):
        unseen = sorted(set(new[column]) - set(earlier[column]))
        if unseen:
            alerts.append(f"new {column}: {', '.join(unseen)}")
    return alerts

# ---- 6. Alerts, and the weekly flow ----
@task(task_run_name="send alerts")
def send(week: int, check_name: str, alerts: list[str]) -> None:
    """Log each alert, keep it in monitoring.alerts and post it to the chat channel if set up."""
    webhook = os.environ.get("LAB_ALERT_WEBHOOK")  # e.g. a Slack or Teams incoming webhook
    for message in alerts:
        get_run_logger().warning("%s: %s", check_name, message)
        execute("INSERT INTO monitoring.alerts VALUES (?, ?, ?)", week, check_name, message)
        if webhook:
            requests.post(webhook, json={"text": f"Lab data, week {week}: {message}"}, timeout=10)


CHECKS = {
    "freshness": check_freshness,
    "volume": check_volume,
    "schema": check_schema,
    "registrations": check_registrations,
    "drift": check_drift,
}


@flow(name="lab-weekly-with-checks", flow_run_name="week {week}")
def weekly(week: int) -> int:
    """Run the week, record its metrics, run every check and send what they find."""
    rows = run_week(week)
    record_metrics(week, rows)
    found = 0
    for check_name, check in CHECKS.items():
        alerts = check(week)
        send(week, check_name, alerts)
        found += len(alerts)
    return found
logging.getLogger("prefect.task_runs").setLevel(logging.WARNING)  # warnings only
logging.getLogger("prefect.flow_runs").setLevel(logging.WARNING)
for week in range(5, 13):
    found = weekly(week)
    log.info("week %d: %d alerts", week, found)
alerts = query("SELECT * FROM monitoring.alerts ORDER BY week, check_name")
print(alerts.groupby("week")["check_name"].apply(lambda c: ", ".join(c)).to_string())
print(query("""
    SELECT week, name, round(value, 2) AS value FROM monitoring.metrics
    WHERE name LIKE 'drift_clogp' ORDER BY week
""").pivot(index="name", columns="week", values="value").to_string())
