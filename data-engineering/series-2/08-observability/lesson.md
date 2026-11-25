---
title: Observability
summary: Know when something is wrong before the chemists do. After each weekly run, record what arrived and what the warehouse holds, and check it against what is normal - freshness on two clocks, volume, schema changes, changed registrations and drift in the molecules' properties - and send an alert when a check fails. Run the lab's weeks 5 to 12 and see every planted problem reported in the week it happened.
requires: dlt[duckdb], dbt-core, dbt-duckdb, duckdb, pandas, numpy, rdkit, prefect, requests
files: ../stages/after-06/**/*
---

The weekly flow of [Module 7](../07-orchestration/) fails when something is clearly broken: a
model that will not build, a test that does not pass. But in week 10 it finished in state
`Completed` although no assay results had arrived, and nobody would have known unless they read
the warnings in that run's log. Most problems in data are like that: nothing fails, the numbers
are just wrong, late or strange. A file that did not come, a table that stopped growing, a column
that was renamed, a batch of compounds unlike the others. The dashboards keep showing something,
and the first person to notice is a chemist who trusted it.

**Observability** means the pipeline watches its own data and says when something looks wrong.
[Series 1, Module 14](../../series-1/14-monitoring-pipelines/) built the pieces by hand for one
pipeline: run metrics, checks against thresholds, alerts. Here they are applied to the warehouse,
week by week, as a Prefect flow, and to the things a lab's data does: arrive late, change shape,
change meaning and drift.

By the end of this module you will be able to:

- name the four things most data checks watch (freshness, volume, schema and distribution) and
  tell the pipeline's clock from the data's clock;
- record metrics for every run, so that each week can be compared with the weeks before;
- check freshness with dbt (did the loader run?) and with the data's own dates (did the results
  come?);
- notice schema changes from dlt's record of them, and changed registrations from the snapshots;
- measure drift in the molecules' properties against a reference, and find where it comes from;
- send alerts somewhere people will see them, and keep them few enough to be read.

## Setup

The Setup is Module 7's, with two changes. The warehouse is built only to the end of week 4 (by
`labstack.warehouse_at`, as Module 6 would), because the checks should meet the lab's problems as
they happen, from week 5's renamed column on. And `requests` sends the alerts to a chat channel,
if one is set up (section 6).

```python
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
```

`execute` is `query`'s twin for statements that change the warehouse: the checks keep their
record in it, in a schema of their own. Each `?` in its statement is filled, safely, with the next
of `parameters` ([Series 1, Module 4](../../series-1/04-databases-and-schemas/) explained why
values are never pasted into SQL).

## 1. What to watch

Data teams group the checks that catch most problems into four kinds:

- **Freshness**: is the data as recent as it should be? A missing file shows up here.
- **Volume**: did about as much arrive as usual? A half-empty file, or two files at once.
- **Schema**: did the shape change? A renamed column, a new one, a different type.
- **Distribution**: do the values look like the usual ones? A unit off by a thousand, a batch of
  compounds unlike any before.

Freshness has a trap: there are two clocks. The **pipeline's clock** says when the data was
loaded; the **data's clock** says when the data is *about* (here, the date a plate was run). A
pipeline can run every Monday, punctually, and load nothing new for a month: fresh on the first
clock, stale on the second. Each needs its own check.

A check compares the present with something. Some rules are fixed (a run every week), but most
compare with history: is this week like the usual weeks? So the first thing the flow does after
each run is record **metrics** about it, in a table of their own, where the next week can find
them. The warehouse gets a `monitoring` schema with two tables: one for metrics, one for the
alerts the checks raise.

```python
execute("CREATE SCHEMA monitoring")
execute("CREATE TABLE monitoring.metrics (week INTEGER, name VARCHAR, value DOUBLE)")
execute("CREATE TABLE monitoring.alerts (week INTEGER, check_name VARCHAR, message VARCHAR)")
```

## 2. The weekly run, and its metrics

The run itself is Module 7's flow, shortened to one task: receive the week's files, load them,
take the snapshot and build. It returns what dlt loaded. The second task records the week's
metrics: how many assay rows arrived, the newest run date in the warehouse, and the version of
the raw layer's schema (section 4).

```python
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
```

`toordinal` turns a date into a whole number of days, so it fits the `value` column. `metric`
reads a metric's history back. The checks compare each week with the one before, so the baseline
week's metrics are recorded now, once. `.fn` is the plain function inside a task, run without
Prefect; the baseline's row count is left out, because week 4 brought the resent file and would
make every later week look small:

```python
record_metrics.fn(BASELINE_WEEKS, None)
print(query("SELECT * FROM monitoring.metrics").to_string(index=False))
```
```output
 week            name    value
    4 newest_run_date 739889.0
    4  schema_version      4.0
```

The SQL in `metric` is built from `name` and `before`, which is safe here
only because both come from this code, never from outside.

## 3. Freshness, on both clocks

The pipeline's clock first. dbt has a check for it built in: **source freshness**. Each source
says which of its columns records when a row was loaded, and how old that may get before dbt warns
or errors. dlt gives every row a load ID that is the time of the load in seconds since 1970, so
`to_timestamp(_dlt_load_id::double)` turns it into a time:

```python
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
```
```output
{'assay': 'pass'}
```

`pass`: dlt loaded the assay table moments ago. On a real schedule, this is the check that
notices a pipeline that stopped running: a server that went down, a schedule someone switched off.
It cannot notice what happened in week 10, though, because in week 10 the pipeline ran on time.

The data's clock needs the data's own dates. A plate is run on the Wednesday of its week, so by the
end of week *n* the newest result in the warehouse should be from week *n*. The check compares the
newest run date with the Wednesday of the week just finished:

```python
@task(task_run_name="check freshness")
def check_freshness(week: int) -> list[str]:
    """The newest result should have been run this week."""
    newest = metric("newest_run_date", week + 1)[week]
    expected = (labdata.monday(week) + timedelta(days=2)).toordinal()  # the week's Wednesday
    behind = int(expected - newest)
    if behind > 0:
        return [f"the newest result is {behind} days old: no plates were run this week"]
    return []
```

## 4. Volume and schema

Volume compares this week's assay rows with the usual: the **median** of the weeks before (the
middle value, which one strange week cannot drag far, unlike the mean). Fewer than half or more
than one and a half times the usual raises an alert. The first two monitored weeks have too little
history to compare with, so the check waits for three.

```python
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
```

Schema changes are recorded by dlt itself. Every time the schema it inferred changes, dlt stores
the new version in `raw._dlt_version`, with the whole schema as JSON. So the check compares this
week's version with last week's, and if it changed, it says which columns of which tables
appeared or disappeared, by comparing the two versions' JSON:

```python
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
```

A changed registration is a schema change of another kind: same columns, different meaning for one
compound. The snapshot of [Module 6](../06-history-and-corrections/) already knows: a compound with a
new version this week was changed in the registry. `dim_compound_history` dates each version by its
export, so the check looks for versions after the first that are valid from this week:

```python
@task(task_run_name="check registrations")
def check_registrations(week: int) -> list[str]:
    """A compound registered before should not change without someone knowing."""
    changed = query(f"""
        SELECT compound_id FROM marts.dim_compound_history
        WHERE version > 1 AND valid_from = DATE '{labdata.monday(week)}'
        ORDER BY compound_id
    """)["compound_id"].tolist()
    return [f"registration changed: {', '.join(changed)}"] if changed else []
```

## 5. Drift in the molecules

The last kind of check asks whether this week's compounds look like the usual ones. Medicinal
chemistry moves on purpose (a series is optimised, a new idea is tried), so a change is not always
a problem; but it should never be a surprise, and a sudden one can be a mistake (a structure drawn
with a wrong group, a vendor's batch with a different salt).

The check compares the compounds registered this week with those of the baseline weeks, property
by property. Its measure is how far this week's mean has moved, in units of the baseline's
**standard deviation** (the usual spread of the property): a move of 1 means this week's average
compound differs from the usual one by as much as typical compounds differ from each other. When a
property moves by `DRIFT_LIMIT` or more, the check looks for where the move comes from, series by
series. It also notices who and what is new: a chemist or a vendor never seen before.

```python
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
```

Each series is compared with its own baseline, because series differ from each other: a week with
more ureas than usual would move the overall average without any compound being unusual for its
series. The drift measures are recorded as metrics too, so they can be plotted week by week.

## 6. Alerts, and the weekly flow

An alert is only useful if it reaches someone who can act on it, and only read if alerts are rare.
`send` does three things with each one: logs it as a warning (in Prefect's record of the run),
keeps it in `monitoring.alerts`, and, if a **webhook** is set up, posts it to a chat channel. A
webhook is a web address that a service such as Slack, Microsoft Teams or Discord gives you for a
channel: anything posted to it as JSON appears in the channel. Its address works like a password,
so it comes from an environment variable, never from the code ([Series 1, Module
4](../../series-1/04-databases-and-schemas/), section 9). Here none is set, so nothing is posted.

```python
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
```

Each check is a separate task, so a check that crashes is recorded as failed without hiding what
the others found, and each can be rerun on its own. Now the weeks pass, 5 to 12, with only the
warnings on the screen:

```python
logging.getLogger("prefect.task_runs").setLevel(logging.WARNING)  # warnings only
logging.getLogger("prefect.flow_runs").setLevel(logging.WARNING)
for week in range(5, 13):
    found = weekly(week)
    log.info("week %d: %d alerts", week, found)
```
```output
WARNING send alerts: schema: raw.assay changed: added ['operator', 'unit'], removed []
INFO week 5: 1 alerts
INFO week 6: 0 alerts
WARNING send alerts: registrations: registration changed: LAB-0042
INFO week 7: 1 alerts
WARNING send alerts: volume: 224 assay rows arrived; usually about 136
WARNING send alerts: schema: raw.assay changed: added ['status'], removed []
INFO week 8: 2 alerts
INFO week 9: 0 alerts
WARNING send alerts: freshness: the newest result is 7 days old: no plates were run this week
WARNING send alerts: volume: 0 assay rows arrived; usually about 144
INFO week 10: 2 alerts
WARNING send alerts: volume: 328 assay rows arrived; usually about 140
WARNING send alerts: drift: mw moved +1.2 SD from the baseline, most in the aminopyrimidines (+1.7 SD)
WARNING send alerts: drift: clogp moved +1.5 SD from the baseline, most in the aminopyrimidines (+2.2 SD)
WARNING send alerts: drift: heavy_atoms moved +1.1 SD from the baseline, most in the aminopyrimidines (+1.6 SD)
WARNING send alerts: drift: new chemist: EF
INFO week 11: 5 alerts
WARNING send alerts: drift: clogp moved +1.2 SD from the baseline, most in the aminopyrimidines (+2.3 SD)
INFO week 12: 1 alerts
```

Every planted problem was reported, in the week it happened, and the quiet weeks stayed quiet:

- **Week 5**: the plate reader's software update (`units` renamed `unit`, a new `operator`
  column), from dlt's own record of the schema.
- **Week 7**: LAB-0042's corrected registration, from the snapshot.
- **Week 8**: the new `status` column of the re-read plate, and more rows than usual: the
  corrected readings come on top of a busy week.
- **Week 10**: no plates run, and no assay rows at all: the late file, on both checks that can see
  it, while dbt's source freshness, on the pipeline's clock, would have passed.
- **Week 11**: two weeks' rows at once (the late file arriving), the new chemist, EF, and the drift:
  heavier, greasier compounds, all coming from one series.
- **Week 12**: the drift again, because EF went on making the same kind of compound.

Here is the record the checks kept, the table a dashboard of the pipeline's health would read:

```python
alerts = query("SELECT * FROM monitoring.alerts ORDER BY week, check_name")
print(alerts.groupby("week")["check_name"].apply(lambda c: ", ".join(c)).to_string())
print(query("""
    SELECT week, name, round(value, 2) AS value FROM monitoring.metrics
    WHERE name LIKE 'drift_clogp' ORDER BY week
""").pivot(index="name", columns="week", values="value").to_string())
```
```output
week
5                                 schema
7                          registrations
8                         schema, volume
10                     freshness, volume
11    drift, drift, drift, drift, volume
12                                 drift
week           5    6     7     8     9     10    11    12
name                                                      
drift_clogp -0.34  0.0 -0.04 -0.14  0.14 -0.16  1.46  1.18
```

The cLogP drift stays near zero for six weeks and jumps in week 11. Whether that is a problem is
for a chemist to say (EF may have been asked to make greasier compounds), but now a chemist is the
one who says it, in the week it starts, instead of finding out from a dashboard months later.

Three habits keep alerts useful:

- **Few, and worth acting on.** Every alert should lead to a person doing something. A check that
  fires every week and is always ignored trains people to ignore all of them; change its limit, or
  remove it.
- **Say what and where.** "cLogP moved +1.6 SD, most in the aminopyrimidines" can be acted on;
  "drift detected" cannot.
- **Limits are decisions.** `DRIFT_LIMIT` and `VOLUME_RANGE` were chosen by looking at normal
  weeks, and written down where they can be reviewed and changed, like the unit seed of Module 4.

The checks so far watch the data. [Module 9](../09-continuous-integration/) watches the code: every
change to the dbt project is built and tested before it reaches the warehouse.

## Try it yourself

The homework is a few questions, answered by running code like the code above: in a new cell at
the end of the notebook, or in a script. It is at the end of the lesson's page, and in
`homework.md` in the module's folder. The answers are published after the cohort's deadline.

## Further reading

- The dbt documentation. *Source freshness*: `loaded_at_field`, `warn_after`, `error_after` and how
  to run it on a schedule. <https://docs.getdbt.com/docs/deploy/source-freshness>
- The dlt documentation. *Schema evolution*: how dlt records each version of a schema, and how to be
  told when it changes. <https://dlthub.com/docs/general-usage/schema-evolution>
- Moses, B., Gavish, L. & Vorwerck, M. (2022). *Data Quality Fundamentals*. O'Reilly Media. The
  five pillars of data observability (freshness, volume, schema, distribution, lineage) and how
  teams use them.
- Beyer, B., Jones, C., Petoff, J. & Murphy, N. R. (eds.) (2016). *Site Reliability Engineering*.
  O'Reilly Media. Chapter 6, "Monitoring Distributed Systems": alerts that people act on.
  <https://sre.google/sre-book/monitoring-distributed-systems/>
