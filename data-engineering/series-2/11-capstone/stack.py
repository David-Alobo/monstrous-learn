"""The lab's whole data stack in one module: the capstone of Series 2.

One Prefect flow runs a lab's week from files to dashboard, with the tools of Modules 2 to 10:

    receive   the week's files arrive in the inbox (retried if the share fails)      Module 7
    load      dlt loads what is new into the raw layer                             Module 2
    snapshot  dbt keeps every version of every registration                        Module 6
    build     dbt builds and tests staging and marts; a failure stops the week     Modules 4-6
    chemistry pandera-chem checks this week's new compounds                        Module 5
    monitor   metrics are recorded and five checks compare them with history       Module 8
    alert     what the checks found is logged, kept and posted to a chat channel   Module 8
    publish   a read-only copy of the warehouse for the dashboard                  Module 10

Use it like this (see the lesson for each step):

    import labdata, stack

    settings = stack.Settings(work="work", seed=2)        # every setting has a default
    stack.prepare(settings)                               # folders, dbt project, monitoring
    summary = stack.run_weeks(settings, range(1, 13))     # one flow run per week
"""

from __future__ import annotations

import functools
import json
import logging
import os
import shutil
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pandera.pandas as pa
import pandera_chem as pc
import requests
from prefect import flow, get_run_logger, task
from prefect.cache_policies import NO_CACHE

import labdata
import labstack

QUIET = logging.getLogger("stack.dbt")  # labstack.dbt logs one line per model here: unseen
QUIET.propagate = False


@dataclass(frozen=True)
class Settings:
    """Everything a run of the stack can change, in one place.

    Every value is plain (text, numbers, lists), so the settings can be passed to the flow and
    kept in Prefect's record of each run. The chat channel's address is not among them: it works
    like a password, so it is read from the environment variable LAB_ALERT_WEBHOOK when an alert
    is sent, and never recorded.

    Attributes:
        work: The working folder: inbox, warehouse, dlt's folder, the dbt project, published copy.
        seed: Which lab: labdata.Lab(seed), the same on every computer.
        baseline_weeks: The weeks the drift check treats as normal.
        drift_limit: Alert when a property moves this many baseline standard deviations.
        volume_range: Alert when a week brings less than the first or more than the second
            multiple of the usual number of assay rows.
        share_fails_once: Weeks in which the lab's share fails at the first attempt (for practice).
    """

    work: str = "work"
    seed: int = 0
    baseline_weeks: int = 4
    drift_limit: float = 1.0
    volume_range: tuple[float, float] = (0.5, 1.5)
    share_fails_once: tuple[int, ...] = ()

    def as_dict(self) -> dict:
        """The settings as plain values, for the flow's parameters."""
        return asdict(self)

    @property
    def folder(self) -> Path:
        """The working folder, as a path."""
        return Path(self.work)

    @property
    def warehouse(self) -> Path:
        """The working warehouse (the dbt profile's default, work/lab.duckdb)."""
        return self.folder / "lab.duckdb"

    @property
    def published(self) -> Path:
        """The read-only copy the dashboard reads."""
        return self.folder / "published" / "lab.duckdb"

    @property
    def project(self) -> Path:
        """The dbt project."""
        return self.folder / "lab_dbt"


@functools.cache
def lab_for(seed: int) -> labdata.Lab:
    """The lab of a seed, made once and then reused.

    Args:
        seed: Which lab.

    Returns:
        The lab.
    """
    return labdata.Lab(seed=seed)


# ---------------------------------------------------------------- the warehouse
def query(settings: Settings, sql: str, *parameters) -> pd.DataFrame:
    """Run one SQL query on the working warehouse and return the answer as a table.

    Args:
        settings: The stack's settings.
        sql: The query; each ? is filled with the next of `parameters`.
        *parameters: The values for the query's ? marks.

    Returns:
        The answer.
    """
    with duckdb.connect(str(settings.warehouse)) as db:
        return db.execute(sql, list(parameters)).df()


def has_table(settings: Settings, schema: str, table: str) -> bool:
    """Whether the warehouse has a table (or view) yet.

    Args:
        settings: The stack's settings.
        schema: Its schema.
        table: Its name.

    Returns:
        True if it exists.
    """
    found = query(settings, "SELECT count(*) AS n FROM information_schema.tables "
                            "WHERE table_schema = ? AND table_name = ?", schema, table)  # fmt: skip
    return bool(found["n"][0])


def prepare(settings: Settings) -> None:
    """Make the folders, copy the dbt project (as Module 6 left it) and the monitoring tables.

    Args:
        settings: The stack's settings.
    """
    settings.folder.mkdir(parents=True, exist_ok=True)
    labstack.dbt_project(settings.project, after=6)
    with duckdb.connect(str(settings.warehouse)) as db:
        db.execute("CREATE SCHEMA IF NOT EXISTS monitoring")
        db.execute("CREATE TABLE IF NOT EXISTS monitoring.metrics "
                   "(week INTEGER, name VARCHAR, value DOUBLE)")  # fmt: skip
        db.execute("CREATE TABLE IF NOT EXISTS monitoring.alerts "
                   "(week INTEGER, check_name VARCHAR, message VARCHAR)")  # fmt: skip


# ---------------------------------------------------------------- the pipeline's tasks
@task(retries=2, retry_delay_seconds=1, cache_policy=NO_CACHE, task_run_name="receive week {week}")
def receive(lab: labdata.Lab, settings: Settings, week: int, attempt: list[int]) -> list[str]:
    """Copy the week's files from the lab's share into the inbox (Module 7).

    Args:
        lab: The lab.
        settings: The stack's settings.
        week: The week.
        attempt: A one-item list counting the attempts (so that practice failures happen once).

    Returns:
        The names of the files that arrived.

    Raises:
        ConnectionError: On the first attempt in a week listed in settings.share_fails_once.
    """
    attempt[0] += 1
    if week in settings.share_fails_once and attempt[0] == 1:
        raise ConnectionError("the lab's file share did not answer")
    return [path.name for path in lab.write_week(week, settings.folder / "inbox")]


@task(cache_policy=NO_CACHE, task_run_name="load week {week}")
def load(settings: Settings, week: int, files: list[str]) -> dict[str, int]:
    """Load what is new in the inbox into the raw layer with dlt (Module 2).

    Args:
        settings: The stack's settings.
        week: The week (for the run's name).
        files: The files that arrived (so that the order is explicit).

    Returns:
        How many rows each of the lab's tables received.
    """
    pipeline = labstack.lab_pipeline(settings.warehouse, settings.folder / "dlt")
    return labstack.load_inbox(settings.folder / "inbox", pipeline)


@task(cache_policy=NO_CACHE, task_run_name="snapshot")
def snapshot(settings: Settings) -> None:
    """Keep this week's version of every registration (Module 6).

    Args:
        settings: The stack's settings.
    """
    labstack.dbt(settings.project, "snapshot", log=QUIET)


@task(cache_policy=NO_CACHE, task_run_name="build")
def build(settings: Settings) -> dict[str, int]:
    """Build and test the warehouse with dbt; fail on a failed test or model (Modules 4 to 6).

    Args:
        settings: The stack's settings.

    Until the first assay file has arrived (in week 1 nothing has been tested yet), there is no
    raw.assay table, so the models built from it (stg_results and everything downstream) wait.

    Returns:
        How many models, seeds and snapshots succeeded and how many tests passed.

    Raises:
        RuntimeError: If a model could not be built or a test failed.
    """
    wait = [] if has_table(settings, "raw", "assay") else ["--exclude", "stg_results+"]
    try:
        results = labstack.dbt(settings.project, "build", *wait, log=QUIET)
    except labstack.BuildError as error:
        raise RuntimeError(error.short) from None
    failed = [r.node.name for r in results if str(r.status) == "fail"]
    if failed:
        raise RuntimeError(f"tests failed: {failed}")
    return dict(sorted(Counter(str(r.status) for r in results).items()))


COMPOUND_RULES = pa.DataFrameSchema(
    {
        "parent_smiles": pa.Column(str, [pc.valid_smiles(), pc.single_fragment()]),
        "series": pa.Column(str, nullable=False),
    }
)


def week_of(dates: pd.Series) -> pd.Series:
    """The project week of each date (week 1 starts on labdata.START).

    Args:
        dates: Dates, as pandas timestamps.

    Returns:
        The weeks.
    """
    return (dates - pd.Timestamp(labdata.START)).dt.days // 7 + 1


@task(cache_policy=NO_CACHE, task_run_name="check chemistry")
def check_chemistry(settings: Settings, week: int) -> list[str]:
    """Check this week's new compounds with pandera-chem (Module 5).

    Only the week's new compounds are checked, so a compound in quarantine is reported once.

    Args:
        settings: The stack's settings.
        week: The week.

    Returns:
        One alert per quarantined compound.
    """
    compounds = query(settings, "SELECT * FROM marts.dim_compound")
    new = compounds[week_of(compounds["registered_on"]) == week].reset_index(drop=True)
    checked = pc.split(new, COMPOUND_RULES)
    return [f"{row.compound_id} failed {row.reasons}"
            for row in checked.quarantined.itertuples()]  # fmt: skip


# ---------------------------------------------------------------- monitoring (Module 8)
def record(settings: Settings, week: int, name: str, value: float) -> None:
    """Save one metric of the week.

    Args:
        settings: The stack's settings.
        week: The week.
        name: The metric.
        value: Its value.
    """
    with duckdb.connect(str(settings.warehouse)) as db:
        db.execute("INSERT INTO monitoring.metrics VALUES (?, ?, ?)", [week, name, float(value)])


def metric(settings: Settings, name: str, before: int) -> pd.Series:
    """A metric's history: its value in each week before `before`, by week.

    Args:
        settings: The stack's settings.
        name: The metric.
        before: The first week not to include.

    Returns:
        The values, indexed by week.
    """
    found = query(settings, "SELECT week, value FROM monitoring.metrics "
                            "WHERE name = ? AND week < ? ORDER BY week", name, before)  # fmt: skip
    return found.set_index("week")["value"]


@task(cache_policy=NO_CACHE, task_run_name="record metrics")
def record_metrics(settings: Settings, week: int, rows: dict[str, int]) -> None:
    """Record the week's assay rows, newest run date and schema version.

    Args:
        settings: The stack's settings.
        week: The week.
        rows: What dlt loaded this week.
    """
    version = query(settings, "SELECT max(version) AS v FROM raw._dlt_version")["v"][0]
    record(settings, week, "assay_rows", rows.get("assay", 0))
    record(settings, week, "schema_version", version)
    if has_table(settings, "marts", "fact_measurement"):  # from the first assay file on
        newest = query(settings, "SELECT max(run_date) AS d FROM marts.fact_measurement")["d"][0]
        record(settings, week, "newest_run_date", newest.toordinal())


def check_freshness(settings: Settings, week: int) -> list[str]:
    """The newest result should have been run this week (from week 2, when testing starts).

    Args:
        settings: The stack's settings.
        week: The week.

    Returns:
        The alerts.
    """
    history = metric(settings, "newest_run_date", week + 1)
    if week < 2:
        return []
    newest = history.get(week, float("nan"))
    expected = (labdata.monday(week) + timedelta(days=2)).toordinal()
    if not newest >= expected:
        return ["no plates were run this week: the newest result is older than this week"]
    return []


def check_volume(settings: Settings, week: int) -> list[str]:
    """About as many assay rows as usual should have arrived (with three weeks of history).

    Args:
        settings: The stack's settings.
        week: The week.

    Returns:
        The alerts.
    """
    history = metric(settings, "assay_rows", week + 1)
    history = history[history.index >= 2]  # week 1 has no assay file
    if len(history) < 4:
        return []
    usual, now = history.iloc[:-1].median(), history.iloc[-1]
    low, high = settings.volume_range
    if not low * usual <= now <= high * usual:
        return [f"{now:.0f} assay rows arrived; usually about {usual:.0f}"]
    return []


def check_schema(settings: Settings, week: int) -> list[str]:
    """An existing raw table's columns should not change without someone knowing.

    Args:
        settings: The stack's settings.
        week: The week.

    Returns:
        The alerts.
    """
    versions = metric(settings, "schema_version", week + 1)
    if len(versions) < 2 or versions.iloc[-1] == versions.iloc[-2]:
        return []

    def columns(version: float) -> dict[str, set[str]]:
        found = query(settings, "SELECT schema FROM raw._dlt_version WHERE version = ?",
                      int(version))  # fmt: skip
        tables = json.loads(found["schema"][0])["tables"]
        return {n: set(t["columns"]) for n, t in tables.items() if not n.startswith("_dlt")}

    old, new = columns(versions.iloc[-2]), columns(versions.iloc[-1])
    alerts = []
    for table in sorted(set(old) & set(new)):  # tables that existed before
        added, removed = new[table] - old[table], old[table] - new[table]
        if added or removed:
            alerts.append(f"raw.{table} changed: added {sorted(added)}, removed {sorted(removed)}")
    return alerts


def check_registrations(settings: Settings, week: int) -> list[str]:
    """A compound registered before should not change without someone knowing.

    Args:
        settings: The stack's settings.
        week: The week.

    Returns:
        The alerts.
    """
    changed = query(settings, "SELECT compound_id FROM marts.dim_compound_history "
                              "WHERE version > 1 AND valid_from = ? ORDER BY compound_id",
                    labdata.monday(week))["compound_id"].tolist()  # fmt: skip
    return [f"registration changed: {', '.join(changed)}"] if changed else []


def check_drift(settings: Settings, week: int) -> list[str]:
    """This week's compounds should look like the baseline's, or someone should know why.

    Args:
        settings: The stack's settings.
        week: The week.

    Returns:
        The alerts.
    """
    if week <= settings.baseline_weeks:
        return []
    compounds = query(settings, "SELECT * FROM marts.dim_compound")
    compounds["week"] = week_of(compounds["registered_on"])
    baseline = compounds[compounds["week"] <= settings.baseline_weeks]
    earlier, new = compounds[compounds["week"] < week], compounds[compounds["week"] == week]
    alerts = []
    for prop in ("mw", "clogp", "heavy_atoms"):
        moved = (new[prop].mean() - baseline[prop].mean()) / baseline[prop].std()
        record(settings, week, f"drift_{prop}", moved)
        if abs(moved) >= settings.drift_limit:
            alerts.append(f"{prop} moved {moved:+.1f} SD from the baseline")
    for column in ("chemist", "vendor"):
        unseen = sorted(set(new[column]) - set(earlier[column]))
        if unseen:
            alerts.append(f"new {column}: {', '.join(unseen)}")
    return alerts


CHECKS = {
    "freshness": check_freshness,
    "volume": check_volume,
    "schema": check_schema,
    "registrations": check_registrations,
    "drift": check_drift,
}


@task(cache_policy=NO_CACHE, task_run_name="monitor")
def monitor(settings: Settings, week: int) -> dict[str, list[str]]:
    """Run every check of Module 8 on the week.

    Args:
        settings: The stack's settings.
        week: The week.

    Returns:
        Each check's alerts.
    """
    return {name: check(settings, week) for name, check in CHECKS.items()}


@task(cache_policy=NO_CACHE, task_run_name="alert")
def alert(settings: Settings, week: int, found: dict[str, list[str]]) -> int:
    """Log each alert, keep it in monitoring.alerts, and post it to the chat channel if set up.

    Args:
        settings: The stack's settings.
        week: The week.
        found: Each check's alerts.

    Returns:
        How many alerts there were.
    """
    count = 0
    for check_name, messages in found.items():
        for message in messages:
            get_run_logger().warning("%s: %s", check_name, message)
            with duckdb.connect(str(settings.warehouse)) as db:
                db.execute("INSERT INTO monitoring.alerts VALUES (?, ?, ?)",
                           [week, check_name, message])  # fmt: skip
            webhook = os.environ.get("LAB_ALERT_WEBHOOK")  # e.g. a Slack or Teams webhook
            if webhook:
                requests.post(webhook, json={"text": f"Week {week}: {message}"}, timeout=10)
            count += 1
    return count


@task(cache_policy=NO_CACHE, task_run_name="publish")
def publish(settings: Settings) -> None:
    """Replace the dashboard's read-only copy with this week's warehouse (Module 10).

    Args:
        settings: The stack's settings.
    """
    fresh = settings.published.with_suffix(".new")
    fresh.parent.mkdir(parents=True, exist_ok=True)
    fresh.unlink(missing_ok=True)
    with duckdb.connect(str(settings.warehouse)) as db:
        db.execute(f"ATTACH '{fresh.as_posix()}' AS fresh")
        db.execute("COPY FROM DATABASE lab TO fresh")
        db.execute("DETACH fresh")
    os.replace(fresh, settings.published)  # readers see the old copy or the new, never half


# ---------------------------------------------------------------- the flow
@flow(name="lab-stack", flow_run_name="week {week}")
def weekly(week: int, settings: dict) -> dict:
    """One week of the lab, from files to dashboard.

    Args:
        week: The week.
        settings: The stack's settings, as plain values (Settings.as_dict()).

    Returns:
        The week's summary: rows loaded, tests passed and alerts.
    """
    settings = Settings(**settings)
    lab = lab_for(settings.seed)
    files = receive(lab, settings, week, [0])
    rows = load(settings, week, files)
    snapshot(settings)
    counts = build(settings)
    record_metrics(settings, week, rows)
    found = monitor(settings, week)
    found["chemistry"] = check_chemistry(settings, week)
    alerts = alert(settings, week, found)
    publish(settings)
    return {"assay rows": rows.get("assay", 0), "tests passed": counts.get("pass", 0),
            "alerts": alerts}  # fmt: skip


def run_weeks(settings: Settings, weeks: range) -> pd.DataFrame:
    """Run the weekly flow for each week in turn and summarise what happened.

    Args:
        settings: The stack's settings.
        weeks: The weeks to run.

    A failed week does not stop the weeks after it: the next week's run starts from the warehouse
    as the failed one left it, as a real schedule would, and the failure is in the summary and in
    Prefect's record, with its reason.

    Returns:
        One row per week: whether its flow completed, and its summary.
    """
    rows = []
    for week in weeks:
        try:
            summary = weekly(week, settings.as_dict())
            rows.append({"week": week, "state": "Completed", **summary})
        except Exception:  # noqa: BLE001 - any failure: Prefect has recorded it, with its reason
            rows.append({"week": week, "state": "Failed"})
    return pd.DataFrame(rows).set_index("week")


def remove(settings: Settings) -> None:
    """Delete the stack's working folder (to start again).

    Args:
        settings: The stack's settings.
    """
    shutil.rmtree(settings.folder, ignore_errors=True)
