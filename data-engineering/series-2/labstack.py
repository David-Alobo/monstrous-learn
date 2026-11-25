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

Read it alongside the lessons it comes from; nothing here is new.
"""

from __future__ import annotations

import os
from pathlib import Path

import dlt
import duckdb
import pandas as pd

import labdata

# dlt, quietly: no usage statistics, and only errors on the screen
os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
os.environ.setdefault("RUNTIME__LOG_LEVEL", "ERROR")


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
    pipeline = dlt.pipeline(
        pipeline_name="lab",
        destination=dlt.destinations.duckdb(str(warehouse)),
        dataset_name="raw",
        pipelines_dir=str(pipelines),
    )
    registry, assay = sources(inbox)
    for week in range(1, weeks + 1) if isinstance(weeks, int) else weeks:
        lab.write_week(week, inbox)
        pipeline.run([registry(), assay()])
    return pipeline


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
