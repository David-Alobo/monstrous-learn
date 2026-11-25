"""What earlier modules of Series 2 built, so that a later lesson can start from it in one line.

Each lesson of Series 2 runs on its own, from nothing. The later ones need what the earlier ones
built: the raw layer that dlt loads (Module 2) and the staging views (Module 1). Rather than repeat
that code in every lesson, it lives here, written as those modules wrote it:

    import labdata, labstack

    lab = labdata.Lab()
    labstack.load_raw(lab, weeks=6, inbox="work/inbox", warehouse="work/lab.duckdb",
                      pipelines="work/dlt")      # Module 2: the files of weeks 1-6, into raw
    with duckdb.connect("work/lab.duckdb") as db:
        labstack.stage(db)                       # Module 1: the staging views, on that raw layer

From Module 5 on, the dbt project of Modules 4 to 6 comes from here too: `dbt_project` copies
it as a given module left it (from stages/), and `dbt` runs a dbt command on it, as Module 4's
lesson did.

Read it alongside the lessons it comes from; nothing here is new.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

import dlt
import duckdb
import pandas as pd
from dbt.cli.main import dbtRunner
from dlt.pipeline.exceptions import PipelineStepFailed

import labdata

# dlt, quietly: no usage statistics, and only errors on the screen
os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
os.environ.setdefault("RUNTIME__LOG_LEVEL", "ERROR")
os.environ.setdefault("DBT_SEND_ANONYMOUS_USAGE_STATS", "false")  # dbt, likewise


def _read(path: Path) -> list[dict]:
    """One of the lab's files, every value as text, with the file's name added (Module 2).

    Args:
        path: The CSV file.

    Returns:
        Its rows, as dictionaries.
    """
    table = pd.read_csv(path, dtype=str, keep_default_na=False)
    table["file_name"] = path.name
    return table.to_dict("records")


def sources(inbox: str | Path) -> tuple:
    """Module 2's two dlt resources, reading from an inbox.

    Args:
        inbox: The folder the lab's files arrive in.

    Returns:
        (registry, assay): the registry snapshot (replaced on each load) and the assay files
        (loaded once each, merged on result_id).
    """
    inbox = Path(inbox)

    @dlt.resource(name="registry", write_disposition="replace")
    def registry():
        """The latest registry export: every compound registered so far."""
        yield _read(max(inbox.glob("registry_*.csv")))

    @dlt.resource(name="assay", write_disposition="merge", primary_key="result_id")
    def assay(files=dlt.sources.incremental("file_name", initial_value="")):  # noqa: B008
        """Every row of every assay file not loaded before."""
        for path in sorted(inbox.glob("assay_*.csv")):
            if path.name > files.last_value:
                yield _read(path)

    return registry, assay


def load_raw(
    lab: labdata.Lab,
    weeks: int | range,
    inbox: str | Path,
    warehouse: str | Path,
    pipelines: str | Path,
) -> dlt.Pipeline:
    """Load the lab's files into the raw layer with dlt, one run per week (Module 2).

    Args:
        lab: The lab.
        weeks: The number of weeks to load from week 1, or a range of weeks (to carry on).
        inbox: The folder the files arrive in.
        warehouse: The DuckDB database file.
        pipelines: dlt's own folder (what it has loaded, and its schema).

    Returns:
        The pipeline, so a lesson can carry on loading later weeks.
    """
    pipeline = lab_pipeline(warehouse, pipelines)
    for week in range(1, weeks + 1) if isinstance(weeks, int) else weeks:
        lab.write_week(week, inbox)
        load_inbox(inbox, pipeline)
    return pipeline


def lab_pipeline(warehouse: str | Path, pipelines: str | Path) -> dlt.Pipeline:
    """Module 2's dlt pipeline into the raw layer (it carries on from what it loaded before).

    Args:
        warehouse: The DuckDB database file.
        pipelines: dlt's own folder (what it has loaded, and its schema).

    Returns:
        The pipeline.
    """
    return dlt.pipeline(
        pipeline_name="lab",
        destination=dlt.destinations.duckdb(str(warehouse)),
        dataset_name="raw",
        pipelines_dir=str(pipelines),
    )


def load_inbox(inbox: str | Path, pipeline: dlt.Pipeline) -> dict[str, int]:
    """Load whatever is new in the inbox into the raw layer (Module 2's resources).

    Args:
        inbox: The folder the lab's files arrive in.
        pipeline: The pipeline (from lab_pipeline).

    Returns:
        How many rows each of the lab's tables received (empty if nothing was new).
    """
    registry, assay = sources(inbox)
    run_patiently(pipeline, lambda: [registry(), assay()])
    info = pipeline.last_trace.last_normalize_info
    counts = info.row_counts if info else {}
    # sorted by table: dlt's own order can change from run to run
    return {table: n for table, n in sorted(counts.items()) if not table.startswith("_dlt")}


def warehouse_at(
    lab: labdata.Lab,
    week: int,
    work: str | Path,
    project: str | Path | None = None,
    build: bool = True,
) -> Path:
    """The lab's warehouse as Module 6 left it, at the end of a week, built from nothing.

    Each week from 1 is loaded and snapshotted in turn (the snapshot keeps the registry's
    history), then the dbt project is built once. Everything goes in `work`: the inbox, the
    database lab.duckdb, dlt's folder dlt/ and the dbt project lab_dbt/.

    Args:
        lab: The lab.
        week: The last week to load.
        work: The working folder (the dbt profile expects work/lab.duckdb, relative to where
            the code runs, unless the environment variable LAB_WAREHOUSE says otherwise).
        project: A dbt project to build instead of Module 6's (Module 9 builds a changed one);
            its warehouse is then the one its profile names.
        build: Whether to build the project at the end (Module 9 builds it itself).

    Returns:
        The dbt project's folder.
    """
    work = Path(work)
    if project is None:
        project = dbt_project(work / "lab_dbt", after=6)
    project = Path(project)
    warehouse = os.environ.get("LAB_WAREHOUSE", str(work / "lab.duckdb"))
    pipeline = lab_pipeline(warehouse, work / "dlt")
    for each in range(1, week + 1):
        lab.write_week(each, work / "inbox")
        load_inbox(work / "inbox", pipeline)
        dbt(project, "snapshot", log=_SILENT)
    if build:
        dbt(project, "build", log=_SILENT)
    return project


_SILENT = logging.getLogger("labstack.silent")  # catching up is not worth a line per model
_SILENT.propagate = False


def run_patiently(pipeline: dlt.Pipeline, data, attempts: int = 5) -> None:
    """Run a dlt pipeline, trying again if Windows briefly refuses access to one of its files.

    On Windows another program (most often an antivirus scan of a file just written) can hold a
    file for a moment, and dlt's move of it fails with PermissionError. dlt keeps what it had
    extracted as a pending package, so the cure is to finish that package (a run with no data) and
    run again; the incremental cursor stops anything being loaded twice.

    Args:
        pipeline: The pipeline.
        data: A function returning what to run (called again for each attempt).
        attempts: How many times to try.

    Raises:
        PipelineStepFailed: If the run fails for any other reason, or on the last attempt.
    """
    for attempt in range(1, attempts + 1):
        try:
            pipeline.run(data())
            return
        except (PipelineStepFailed, PermissionError) as error:
            if not _windows_lock(error) or attempt == attempts:
                raise
            time.sleep(attempt)
            if pipeline.has_pending_data:
                try:
                    pipeline.run()  # finish the package that was interrupted
                except (PipelineStepFailed, PermissionError) as again:
                    if not _windows_lock(again):
                        raise


def _windows_lock(error: Exception) -> bool:
    """Whether a dlt failure was a file briefly held by another program (see run_patiently).

    Args:
        error: What dlt raised.

    Returns:
        True for a PermissionError, raised directly or as the cause of a failed step.
    """
    return isinstance(error, PermissionError) or isinstance(error.__cause__, PermissionError)


def stage(db: duckdb.DuckDBPyConnection) -> None:
    """Module 1's staging views, on the raw layer dlt loaded: each fix made once.

    staging.compounds is the current registry; staging.results has one row per result, the unit
    columns joined back together, every value in nanomolar and its pIC50.

    Args:
        db: An open connection to the warehouse.
    """
    db.execute("CREATE SCHEMA IF NOT EXISTS staging")
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
    """)
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
                   coalesce(unit, units)       AS unit,      -- 'units' was renamed in week 5
                   run_date::DATE              AS run_date,
                   file_name
            FROM raw.assay
        )
        SELECT typed.* EXCLUDE (file_name),
               value * u.factor                    AS ic50_nm,
               9 - log10(value * u.factor)         AS pic50,
               file_name                           AS source_file
        FROM typed LEFT JOIN staging.unit_to_nm AS u USING (unit)
    """)


# ---------------------------------------------------------------- the dbt project (Modules 4-6)
STAGES = Path(__file__).parent / "stages"  # the project as each module left it


def dbt_project(dest: str | Path, after: int) -> Path:
    """Copy the lab's dbt project as a module left it (stages/after-NN/lab_dbt) into a folder.

    Args:
        dest: Where to put the project (its folders are made if needed).
        after: The module whose finished project to copy (4, 5 or 6).

    Returns:
        The project's folder.
    """
    dest = Path(dest)
    shutil.copytree(STAGES / f"after-{after:02d}" / "lab_dbt", dest, dirs_exist_ok=True)
    return dest


def dbt(project: str | Path, *args: str, log: logging.Logger | None = None):
    """Run a dbt command on a project, like `dbt <args>` in a terminal, and log what it did.

    Args:
        project: The project's folder (its profiles.yml is there too).
        *args: The command and its options, e.g. "build", "--select", "staging".
        log: Where to log one line per thing built or tested (the root logger if None).

    Returns:
        What dbt returned: the results of a build, run, seed, test or snapshot; the names of
        `ls`; the catalogue of `docs generate`.

    Raises:
        BuildError: If anything could not be built (a model's SQL or its contract failed; a
            failing test is logged, not raised), with dbt's reason for each.
    """
    log = log or logging.getLogger()
    # dbt's own console messages carry the time; keep them off the screen (its log file keeps
    # them all), except for `ls`, whose list is its output
    quiet = ["--quiet"] if args[0] == "ls" else ["--log-level", "none"]
    result = dbtRunner().invoke(
        [*args, *quiet, "--project-dir", str(project), "--profiles-dir", str(project)]
    )
    if result.exception:
        raise result.exception
    if args[0] in ("build", "run", "seed", "test", "snapshot"):
        for item in result.result:
            log.info("%s %s: %s", item.node.resource_type, item.node.name, item.status)
        broken = {
            item.node.name: item.message.replace("\\", "/")  # the same paths on every system
            for item in result.result
            if item.status == "error"
        }
        if broken:
            raise BuildError(broken)
    return result.result


class BuildError(RuntimeError):
    """dbt could not build one or more models: their names, with dbt's reason for each."""

    def __init__(self, reasons: dict[str, str]) -> None:
        """Keep dbt's full reasons, and a one-line summary of them.

        Args:
            reasons: dbt's message for each model it could not build.
        """
        self.reasons = reasons
        full = "\n".join(f"{name}: {message}" for name, message in reasons.items())
        super().__init__(f"dbt could not build:\n{full}")

    @property
    def short(self) -> str:
        """One line: each model, with the first line of dbt's reason after its heading."""

        def first(message: str) -> str:
            lines = [line.strip() for line in message.splitlines()[1:] if line.strip()]
            return lines[0] if lines else message.strip()

        return "; ".join(f"{name}: {first(message)}" for name, message in self.reasons.items())
