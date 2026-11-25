"""Modelling the warehouse: the code of the lesson, in order.

Shape the lab's clean data as a star schema in DuckDB. Declare the grain, build dimensions for compounds, targets and dates (with properties and chemical series worked out once, with RDKit), a fact table of measurements with keys the database enforces, and answer the chemists' questions from it.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/03-modelling-the-warehouse/
Run it from anywhere, e.g. from the series folder: uv run python 03-modelling-the-warehouse/code.py
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
from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, Lipinski

import labdata
import labstack

RDLogger.DisableLog("rdApp.*")  # RDKit's warnings would clutter the outputs; we check structures
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
WAREHOUSE = WORK / "lab.duckdb"
WEEKS = 6  # the lab is at the end of week 6, as in Modules 1 and 2
# the three chemical series, each as the substructure its compounds share (its core)
SERIES = {
    "aminopyrimidines": "c1ccc(nc1)Nc2ncccn2",
    "pyrimidine piperazines": "c1nccc(n1)N2CCN(CC2)C(=O)c3ccccc3",
    "ureas": "O=C(Nc1ccccc1)Nc2cccnc2",
}

shutil.rmtree(WORK, ignore_errors=True)  # start clean
lab = labdata.Lab()
labstack.load_raw(lab, WEEKS, WORK / "inbox", WAREHOUSE, WORK / "dlt")
db = duckdb.connect(str(WAREHOUSE))
labstack.stage(db)
db.execute("CREATE SCHEMA marts")

# ---- 2. The grain ----
print(db.sql("""
    SELECT count(*)                                                  AS results,
           count(DISTINCT (compound_id, target, plate, replicate))   AS distinct_at_grain
    FROM staging.results
""").df().to_string(index=False))

# ---- 3. The compound dimension ----
CORES = {name: Chem.MolFromSmiles(core) for name, core in SERIES.items()}


def series_of(mol: Chem.Mol) -> str | None:
    """The chemical series whose core the molecule contains (None if no core, or several)."""
    hits = [name for name, core in CORES.items() if mol.HasSubstructMatch(core)]
    return hits[0] if len(hits) == 1 else None


def describe(smiles: str) -> dict:
    """A compound's series and properties, worked out once for the dimension."""
    mol = Chem.MolFromSmiles(smiles)
    return {
        "series": series_of(mol),
        "mw": round(Descriptors.MolWt(mol), 1),
        "clogp": round(Crippen.MolLogP(mol), 2),
        "hbd": Lipinski.NumHDonors(mol),
        "hba": Lipinski.NumHAcceptors(mol),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
    }


compounds = db.sql("SELECT * FROM staging.compounds ORDER BY compound_id").df()
chemistry = pd.DataFrame([describe(s) for s in compounds["parent_smiles"]])
compounds = pd.concat([compounds, chemistry], axis=1)
print(compounds["series"].value_counts(dropna=False).to_string())
print(compounds[compounds["series"].isna()][["compound_id", "parent_smiles"]]
      .to_string(index=False))
db.execute("""
    CREATE TABLE marts.dim_compound (
        compound_key  INTEGER PRIMARY KEY,
        compound_id   VARCHAR NOT NULL,
        parent_smiles VARCHAR NOT NULL,
        salt          VARCHAR,
        series        VARCHAR,
        chemist       VARCHAR,
        vendor        VARCHAR,
        registered_on DATE,
        mw            DOUBLE,
        clogp         DOUBLE,
        hbd           INTEGER,
        hba           INTEGER,
        heavy_atoms   INTEGER
    )
""")
db.execute("""
    INSERT INTO marts.dim_compound
    SELECT row_number() OVER (ORDER BY compound_id), compound_id, parent_smiles, salt, series,
           chemist, vendor, registered_on, mw, clogp, hbd, hba, heavy_atoms
    FROM compounds
""")
print(db.sql("SELECT * FROM marts.dim_compound LIMIT 3").df().to_string(index=False))

# ---- 4. Targets and dates ----
targets = pd.DataFrame(
    [(gene, chembl_id, "primary" if gene == labdata.PRIMARY else "panel")
     for gene, chembl_id in labdata.TARGETS.items()],
    columns=["target", "chembl_id", "role"],
)
db.execute("""
    CREATE TABLE marts.dim_target (
        target_key INTEGER PRIMARY KEY,
        target     VARCHAR NOT NULL UNIQUE,
        chembl_id  VARCHAR NOT NULL,
        role       VARCHAR NOT NULL
    )
""")
db.execute("INSERT INTO marts.dim_target "
           "SELECT row_number() OVER (ORDER BY role DESC, target), * FROM targets")
print(db.sql("SELECT * FROM marts.dim_target ORDER BY target_key").df().to_string(index=False))
db.execute(f"""
    CREATE TABLE marts.dim_date AS
    SELECT day::DATE                                            AS date_key,
           (datediff('day', DATE '{labdata.START}', day) // 7) + 1 AS project_week,
           isodow(day) > 5                                      AS weekend,
           dayname(day)                                         AS weekday,
           monthname(day)                                       AS month
    FROM generate_series(DATE '{labdata.START}',
                         DATE '{labdata.monday(labdata.WEEKS + 1)}', INTERVAL 1 DAY) AS t(day)
""")
db.execute("ALTER TABLE marts.dim_date ADD PRIMARY KEY (date_key)")
print(db.sql("SELECT * FROM marts.dim_date WHERE date_key BETWEEN DATE '2026-09-16' "
             "AND DATE '2026-09-21'").df().to_string(index=False))

# ---- 5. The fact table ----
db.execute("""
    CREATE TABLE marts.fact_measurement (
        result_id    VARCHAR PRIMARY KEY,
        compound_key INTEGER NOT NULL REFERENCES marts.dim_compound (compound_key),
        target_key   INTEGER NOT NULL REFERENCES marts.dim_target (target_key),
        run_date     DATE    NOT NULL REFERENCES marts.dim_date (date_key),
        plate        VARCHAR NOT NULL,
        replicate    INTEGER NOT NULL,
        relation     VARCHAR NOT NULL,
        ic50_nm      DOUBLE,
        pic50        DOUBLE,
        source_file  VARCHAR NOT NULL
    )
""")
db.execute("""
    INSERT INTO marts.fact_measurement
    SELECT r.result_id, c.compound_key, t.target_key, r.run_date, r.plate, r.replicate,
           r.relation, r.ic50_nm, r.pic50, r.source_file
    FROM staging.results AS r
    JOIN marts.dim_compound AS c USING (compound_id)
    JOIN marts.dim_target AS t USING (target)
""")
print(db.sql("SELECT count(*) AS measurements FROM marts.fact_measurement").fetchall()[0][0],
      "measurements in the fact table, of", db.sql("SELECT count(*) FROM staging.results")
      .fetchall()[0][0], "in staging")
try:
    db.execute("""
        INSERT INTO marts.fact_measurement
        VALUES ('R-TEST', 9999, 1, DATE '2026-09-16', 'P02-01', 1, '=', 10.0, 8.0, 'test.csv')
    """)
except duckdb.ConstraintException as error:
    log.error("refused: %s", str(error).splitlines()[0])

# ---- 6. Which numbers can be averaged ----
print(db.sql("""
    SELECT c.series,
           count(*)                                    AS measured,
           round(avg(f.ic50_nm))                       AS mean_ic50_nm,
           round(10 ** (9 - avg(f.pic50)))             AS geometric_mean_nm,
           round(avg(f.pic50), 2)                      AS mean_pic50
    FROM marts.fact_measurement AS f
    JOIN marts.dim_compound AS c USING (compound_key)
    JOIN marts.dim_target AS t USING (target_key)
    WHERE t.target = 'EGFR' AND f.relation = '='
    GROUP BY ALL ORDER BY mean_pic50 DESC
""").df().to_string(index=False))
print(db.sql("""
    SELECT t.target,
           count(*)                                    AS results,
           count(*) FILTER (WHERE f.relation = '>')    AS too_weak_to_measure
    FROM marts.fact_measurement AS f JOIN marts.dim_target AS t USING (target_key)
    GROUP BY ALL ORDER BY results DESC, t.target
""").df().to_string(index=False))

# ---- 7. The questions, answered from the star ----
print(db.sql("""
    SELECT d.project_week AS registered_in_week, c.series,
           count(DISTINCT c.compound_key) AS compounds, round(avg(f.pic50), 2) AS mean_pic50
    FROM marts.fact_measurement AS f
    JOIN marts.dim_compound AS c USING (compound_key)
    JOIN marts.dim_target AS t USING (target_key)
    JOIN marts.dim_date AS d ON d.date_key = c.registered_on
    WHERE t.target = 'EGFR' AND f.relation = '=' AND c.series IS NOT NULL
    GROUP BY ALL ORDER BY c.series, registered_in_week
""").df().pivot(index="registered_in_week", columns="series", values="mean_pic50")
    .to_string())
print(db.sql("""
    WITH per_compound AS (
        SELECT c.compound_key, c.series, c.clogp, avg(f.pic50) AS pic50
        FROM marts.fact_measurement AS f
        JOIN marts.dim_compound AS c USING (compound_key)
        JOIN marts.dim_target AS t USING (target_key)
        WHERE t.target = 'EGFR' AND f.relation = '=' AND c.series IS NOT NULL
        GROUP BY ALL
    )
    SELECT series, count(*) AS compounds,
           round(avg(pic50), 2) AS mean_pic50, round(avg(clogp), 2) AS mean_clogp,
           round(avg(pic50 - clogp), 2) AS mean_lipe,
           round(corr(pic50, clogp), 2) AS potency_vs_clogp
    FROM per_compound GROUP BY ALL ORDER BY mean_lipe DESC
""").df().to_string(index=False))

# ---- 8. A wide table for dashboards ----
db.execute("""
    CREATE VIEW marts.measurements_wide AS
    SELECT f.result_id, f.plate, f.replicate, f.relation, f.ic50_nm, f.pic50,
           c.compound_id, c.parent_smiles, c.series, c.chemist, c.vendor, c.mw, c.clogp,
           t.target, t.role AS target_role,
           d.date_key AS run_date, d.project_week AS run_week
    FROM marts.fact_measurement AS f
    JOIN marts.dim_compound AS c USING (compound_key)
    JOIN marts.dim_target AS t USING (target_key)
    JOIN marts.dim_date AS d ON d.date_key = f.run_date
""")
wide = db.sql("SELECT * FROM marts.measurements_wide").df()
print(len(wide), "rows,", len(wide.columns), "columns")
print(wide.query("relation == '='").groupby(["chemist", "target"])["pic50"].mean().round(2)
      .unstack().to_string())
print(db.sql("""
    SELECT table_name, table_type FROM information_schema.tables
    WHERE table_schema = 'marts' ORDER BY table_type, table_name
""").df().to_string(index=False))
db.close()
