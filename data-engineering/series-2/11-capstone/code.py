""""Capstone: a running data stack for a small lab": the code of the lesson, in order.

Ingest, model, test, schedule, monitor and serve one lab's chemistry data end to end, with every tool of the series in one module, stack.py. Run a new lab's twelve weeks through it, read the record it keeps, open its dashboard, and write what a colleague needs to take it over. Then build one for a lab of your own.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/11-capstone/
Run it from anywhere, e.g. from the series folder: uv run python 11-capstone/code.py
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
import os
import shutil
from pathlib import Path

WORK = Path("work")  # where the lesson writes its files (git-ignored)
shutil.rmtree(WORK, ignore_errors=True)  # start clean, before Prefect keeps its files in work/
(WORK / "prefect").mkdir(parents=True)
os.environ["PREFECT_HOME"] = str((WORK / "prefect").resolve())
os.environ["PREFECT_SERVER_ANALYTICS_ENABLED"] = "false"

import json
import logging

import duckdb
from prefect.client.orchestration import get_client
from streamlit.testing.v1 import AppTest

import labstack
import stack

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


def named(record: logging.LogRecord) -> bool:
    """Start each of Prefect's lines with its run's name, and leave out tracebacks."""
    name = getattr(record, "task_run_name", None) or getattr(record, "flow_run_name", None)
    if name:
        record.msg, record.args = f"{name}: {record.getMessage()}", ()
    record.exc_info = record.exc_text = None
    return True


for name in ("prefect.flow_runs", "prefect.task_runs"):
    logging.getLogger(name).addFilter(named)
    logging.getLogger(name).setLevel(logging.WARNING)  # warnings only: here, the alerts
logging.getLogger("prefect").addFilter(lambda r: "temporary server" not in r.getMessage())
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").addFilter(
    lambda record: "missing ScriptRunContext" not in record.getMessage())  # expected in a test

# ---- 2. The settings ----
settings = stack.Settings(work=str(WORK), seed=2, share_fails_once=(9,))
for name, value in settings.as_dict().items():
    print(f"{name:16} {value}")

# ---- 4. Twelve weeks ----
stack.prepare(settings)
summary = stack.run_weeks(settings, range(1, 13))
print(summary.to_string())
with get_client(sync_client=True) as client:
    runs = sorted(client.read_flow_runs(), key=lambda r: r.expected_start_time)
    retried = [t.name for t in client.read_task_runs() if t.run_count > 1]
print(" ".join(f"{run.name.split()[-1]}:{run.state_name}" for run in runs))
print("needed more than one attempt:", retried)

# ---- 5. What the record holds ----
with duckdb.connect(str(settings.published), read_only=True) as db:
    alerts = db.sql("SELECT * FROM monitoring.alerts ORDER BY week, check_name").df()
    history = db.sql("SELECT compound_id, version, valid_from, valid_to "
                     "FROM marts.dim_compound_history WHERE compound_id IN "
                     "(SELECT compound_id FROM marts.dim_compound_history WHERE version > 1)").df()
    sizes = db.sql("""
        SELECT schema_name || '.' || table_name AS table_name, estimated_size AS rows
        FROM duckdb_tables() WHERE schema_name IN ('raw', 'snapshots', 'marts', 'monitoring')
          AND NOT starts_with(table_name, '_dlt') ORDER BY table_name
    """).df()
print(alerts.to_string(index=False))
print(history.to_string(index=False))
print(sizes.to_string(index=False))

# ---- 6. The dashboard, on the new lab ----
app = AppTest.from_file(str(Path("dashboard.py").resolve()), default_timeout=120).run()
assert not app.exception, app.exception[0].message
print({metric.label: metric.value for metric in app.metric})
app.selectbox[0].set_value("LAB-0042").run()
print([warning.value for warning in app.warning])

# ---- 7. Handing it over ----
docs = labstack.dbt(settings.project, "docs", "generate", log=stack.QUIET)
manifest = json.loads((settings.project / "target" / "manifest.json").read_text(encoding="utf-8"))
models = [node for node in manifest["nodes"].values() if node["resource_type"] == "model"]
print(len(models), "models,", sum(bool(m["description"]) for m in models), "with a description;",
      sum(node["resource_type"] == "test" for node in manifest["nodes"].values()), "tests")
