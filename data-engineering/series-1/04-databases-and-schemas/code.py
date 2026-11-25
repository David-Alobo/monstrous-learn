"""Databases, schemas and a chemical database: the code of the lesson, in order.

The kinds of database and what each is for, how to plan tables for chemical data before storing anything, how to describe them, and a chemical database in PostgreSQL with the RDKit cartridge, searched by substructure and similarity.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/04-databases-and-schemas/
Run it from anywhere, e.g. from the series folder: uv run python 04-databases-and-schemas/code.py
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
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psycopg
from dotenv import find_dotenv, load_dotenv
from psycopg import sql
from psycopg.conninfo import make_conninfo
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

from chemlib import library

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# the lesson's data: a library from chemlib, offered by three suppliers and tested on two targets.
# The compounds are realistic; the prices and assay results are made up for the lesson.
N_COMPOUNDS = 1_500  # compounds drawn from chemlib
LIBRARY_SEED = 4  # which compounds
N_MEASUREMENTS = 4_000  # assay results
DATA_SEED = 44  # seed for the made-up batches and results
SUPPLIERS = [("Vendor A", "United Kingdom"), ("Vendor B", "Germany"), ("Vendor C", "India")]
TARGETS = [("CHEMBL203", "EGFR", "Homo sapiens"), ("CHEMBL205", "Carbonic anhydrase II", "Homo sapiens")]  # fmt: skip
LOADED_ON = "2026-11-24"  # the load date recorded with every row; fixed, so outputs never change
SOURCE = "chemlib library, seed 4"  # where the rows came from, recorded with every row

# where the lesson writes its files (git-ignored)
WORK = Path("work")
DUCKDB_FILE = WORK / "chem.duckdb"

# passwords and addresses: from the environment, or from the course's .env file (copied from
# .env.example at the repository's root); find_dotenv looks for it in this folder and the ones
# above, and settings already in the environment are kept
load_dotenv(find_dotenv(usecwd=True))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PG_SCHEMA = "module4"  # the lesson's own area inside the database, emptied at the start of section 7
ANALYST = "analyst"  # the read-only colleague of section 8
ANALYST_PASSWORD = os.environ.get("ANALYST_PASSWORD", "")
ACID_SMARTS = "[CX3](=O)[OX2H1]"  # a carboxylic acid: C=O and an O carrying one H (Module 2)

RDLogger.DisableLog("rdApp.*")  # chemlib's molecules all parse; RDKit has nothing to tell us
WORK.mkdir(exist_ok=True)
DUCKDB_FILE.unlink(missing_ok=True)  # start the lesson with an empty database file

# ---- 2. Plan the tables before storing anything ----
compounds = library(N_COMPOUNDS, seed=LIBRARY_SEED)[["smiles"]].reset_index(drop=True)
mols = [Chem.MolFromSmiles(s) for s in compounds["smiles"]]
compounds["smiles"] = [Chem.MolToSmiles(m) for m in mols]  # canonical SMILES (Module 2)
compounds["inchikey"] = [Chem.MolToInchiKey(m) for m in mols]  # the compound's identity
compounds["mw"] = [round(Descriptors.MolWt(m), 2) for m in mols]
compounds.insert(0, "compound_id", range(1, len(compounds) + 1))

rng = np.random.default_rng(DATA_SEED)
batch_rows = []
for cid in compounds["compound_id"]:
    # each compound is sold by one, two or three of the suppliers, each at its own price
    for supplier_id in sorted(rng.choice([1, 2, 3], size=rng.integers(1, 4), replace=False)):
        batch_rows.append((cid, int(supplier_id), round(float(rng.uniform(15, 400)), 2),
                           int(rng.choice([5, 10, 25, 50, 100]))))  # fmt: skip
batches = pd.DataFrame(batch_rows, columns=["compound_id", "supplier_id", "price_usd", "amount_mg"])
batches.insert(0, "batch_id", range(1, len(batches) + 1))

# made-up assay results: pIC50 values, a little lower on Vendor C's batches (a purity problem)
pick = rng.integers(0, len(batches), size=N_MEASUREMENTS)
target = rng.integers(0, len(TARGETS), size=N_MEASUREMENTS)
pic50 = rng.normal(np.where(target == 0, 6.3, 5.5), 0.7) - 0.4 * (batches["supplier_id"].to_numpy()[pick] == 3)  # fmt: skip
measurements = pd.DataFrame({
    "measurement_id": range(1, N_MEASUREMENTS + 1),
    "batch_id": batches["batch_id"].to_numpy()[pick],
    "target_id": [TARGETS[t][0] for t in target],
    "ic50_nm": np.round(10 ** (9 - pic50), 1),
    "measured_on": pd.Timestamp("2026-01-05") + pd.to_timedelta(rng.integers(0, 300, N_MEASUREMENTS), unit="D"),
})  # fmt: skip
print(f"{len(compounds):,} compounds, {len(batches):,} batches, {len(measurements):,} measurements")
suppliers = pd.DataFrame([(i + 1, n, c) for i, (n, c) in enumerate(SUPPLIERS)],
                         columns=["supplier_id", "name", "country"])  # fmt: skip
targets = pd.DataFrame(TARGETS, columns=["target_id", "name", "organism"])
sheet = (
    measurements.merge(batches, on="batch_id")
    .merge(compounds, on="compound_id")
    .merge(suppliers.rename(columns={"name": "supplier"}), on="supplier_id")
    .merge(targets.rename(columns={"name": "target"}), on="target_id")
    [["measurement_id", "smiles", "inchikey", "mw", "supplier", "country", "price_usd",
      "target", "organism", "ic50_nm", "measured_on"]]
)  # fmt: skip
print(sheet.shape[0], "rows,", sheet.shape[1], "columns")
print(sheet["supplier"].value_counts().to_string())
messy = sheet.copy()
messy.loc[messy.index[::50], "supplier"] = "Vendor B "  # a stray space, typed by hand
moved = messy["supplier"].eq("Vendor A")
messy.loc[moved & (messy.index < 2000), "country"] = "Ireland"  # only half the rows updated
print("suppliers:", messy["supplier"].nunique())
print(messy[messy["supplier"] == "Vendor A"]["country"].value_counts().to_string())

# ---- 3. Build the tables, with rules ----
db = duckdb.connect(DUCKDB_FILE)
db.execute("""
CREATE TABLE supplier (
    supplier_id INTEGER PRIMARY KEY,
    name        VARCHAR NOT NULL UNIQUE,
    country     VARCHAR NOT NULL
);
CREATE TABLE compound (
    compound_id INTEGER PRIMARY KEY,
    inchikey    VARCHAR NOT NULL UNIQUE CHECK (length(inchikey) = 27),
    smiles      VARCHAR NOT NULL,
    mw          DECIMAL(7, 2) NOT NULL CHECK (mw > 0),
    source      VARCHAR NOT NULL,
    loaded_on   DATE NOT NULL
);
CREATE TABLE batch (
    batch_id    INTEGER PRIMARY KEY,
    compound_id INTEGER NOT NULL REFERENCES compound (compound_id),
    supplier_id INTEGER NOT NULL REFERENCES supplier (supplier_id),
    price_usd   DECIMAL(8, 2) NOT NULL CHECK (price_usd >= 0),
    amount_mg   INTEGER NOT NULL CHECK (amount_mg > 0)
);
CREATE TABLE target (
    target_id   VARCHAR PRIMARY KEY,
    name        VARCHAR NOT NULL,
    organism    VARCHAR NOT NULL
);
CREATE TABLE measurement (
    measurement_id INTEGER PRIMARY KEY,
    batch_id    INTEGER NOT NULL REFERENCES batch (batch_id),
    target_id   VARCHAR NOT NULL REFERENCES target (target_id),
    ic50_nm     DOUBLE NOT NULL CHECK (ic50_nm > 0),
    measured_on DATE NOT NULL
);
""")
print([row[0] for row in db.sql("SHOW TABLES").fetchall()])
compounds["source"] = SOURCE
compounds["loaded_on"] = pd.Timestamp(LOADED_ON)
for name, frame in [("supplier", suppliers), ("compound", compounds), ("batch", batches),
                    ("target", targets), ("measurement", measurements)]:  # fmt: skip
    db.register("incoming", frame)
    columns = ", ".join(c[0] for c in db.sql(f"DESCRIBE {name}").fetchall())
    db.execute(f"INSERT INTO {name} SELECT {columns} FROM incoming")
    db.unregister("incoming")
    count = db.execute(f"SELECT count(*) FROM {name}").fetchall()[0][0]
    log.info("loaded %s rows into %s", f"{count:,}", name)
bad_rows = {
    "a negative price": "INSERT INTO batch VALUES (99001, 1, 1, -5.00, 10)",
    "a batch of a compound that does not exist": "INSERT INTO batch VALUES (99002, 99999, 1, 20.00, 10)",
    "the same compound registered twice": f"INSERT INTO compound VALUES (99003, '{compounds.inchikey[0]}', 'C', 16.04, 'typed by hand', DATE '2026-11-24')",
    "a measurement with no IC50": "INSERT INTO measurement VALUES (99004, 1, 'CHEMBL203', NULL, DATE '2026-11-24')",
    "a fourth supplier called Vendor B": "INSERT INTO supplier VALUES (4, 'Vendor B', 'Germany')",
}  # fmt: skip
for problem, statement in bad_rows.items():
    try:
        db.execute(statement)
        print(f"{problem}: stored (no rule stopped it)")
    except duckdb.Error as error:
        print(f"{problem}: refused, {type(error).__name__}")

# ---- 4. Asking questions in SQL ----
print(db.sql("""
    SELECT batch_id, compound_id, supplier_id, price_usd
    FROM batch
    WHERE amount_mg >= 25
    ORDER BY price_usd
    LIMIT 5
""").df().to_string(index=False))
print(db.sql("""
    SELECT supplier.name AS supplier, count(*) AS batches, round(avg(price_usd), 2) AS mean_price_usd
    FROM batch
    JOIN supplier USING (supplier_id)
    GROUP BY supplier.name
    ORDER BY supplier.name
""").df().to_string(index=False))
print(db.sql("""
    SELECT compound.inchikey, compound.mw, supplier.name AS supplier,
           round(9 - log10(measurement.ic50_nm), 2) AS pic50
    FROM measurement
    JOIN batch    USING (batch_id)
    JOIN compound USING (compound_id)
    JOIN supplier USING (supplier_id)
    JOIN target   USING (target_id)
    WHERE target.name = 'EGFR' AND compound.mw < 300 AND 9 - log10(measurement.ic50_nm) >= 7
    ORDER BY pic50 DESC
    LIMIT 5
""").df().to_string(index=False))
db.execute("UPDATE supplier SET country = 'Ireland' WHERE name = 'Vendor A'")
print(db.sql("SELECT name, country FROM supplier ORDER BY supplier_id").fetchall())
db.execute("UPDATE supplier SET country = 'United Kingdom' WHERE name = 'Vendor A'")  # put it back

# ---- 5. Describing the database: metadata ----
db.execute("""
COMMENT ON TABLE measurement IS 'One assay result: one batch tested on one target.';
COMMENT ON COLUMN measurement.ic50_nm IS 'Half-maximal inhibitory concentration, nanomolar.';
COMMENT ON COLUMN measurement.measured_on IS 'Date the assay was run (not the date it was loaded).';
COMMENT ON TABLE compound IS 'One row per distinct structure, identified by its standard InChIKey.';
COMMENT ON COLUMN compound.smiles IS 'Canonical SMILES from RDKit.';
COMMENT ON COLUMN compound.mw IS 'Average molecular weight, g/mol, from RDKit.';
COMMENT ON COLUMN compound.source IS 'Where the row came from.';
COMMENT ON COLUMN compound.loaded_on IS 'Date the row was loaded.';
COMMENT ON COLUMN batch.price_usd IS 'Catalogue price of the batch, US dollars.';
""")
dictionary = db.sql("""
    SELECT table_name AS "table", column_name AS "column", data_type AS type,
           CASE WHEN is_nullable THEN '' ELSE 'required' END AS rule,
           coalesce(comment, '(not described yet)') AS comment
    FROM duckdb_columns()
    WHERE table_name IN ('compound', 'measurement')
    ORDER BY table_name, column_index
""").df()
print(dictionary.to_string(index=False))

# ---- 6. Recording versus analysing: a star schema ----
db.execute("""
CREATE VIEW fact_measurement AS
    SELECT m.measurement_id, b.compound_id, b.supplier_id, m.target_id, m.measured_on AS date_key,
           round(9 - log10(m.ic50_nm), 2) AS pic50, b.price_usd
    FROM measurement m JOIN batch b USING (batch_id);
CREATE VIEW dim_compound AS
    SELECT compound_id, inchikey, smiles, mw,
           CASE WHEN mw < 300 THEN 'under 300' WHEN mw < 400 THEN '300-400' ELSE '400 and over' END AS mw_band
    FROM compound;
CREATE VIEW dim_supplier AS SELECT supplier_id, name AS supplier, country FROM supplier;
CREATE VIEW dim_target AS SELECT target_id, name AS target, organism FROM target;
CREATE VIEW dim_date AS
    SELECT DISTINCT measured_on AS date_key, year(measured_on) AS year, quarter(measured_on) AS quarter
    FROM measurement;
""")
print(db.sql("""
    SELECT t.target, s.supplier, count(*) AS results, round(avg(f.pic50), 2) AS mean_pic50
    FROM fact_measurement f
    JOIN dim_target t USING (target_id)
    JOIN dim_supplier s USING (supplier_id)
    GROUP BY t.target, s.supplier
    ORDER BY t.target, s.supplier
""").df().to_string(index=False))
db.close()

# ---- 7. A chemical database: PostgreSQL with the RDKit cartridge ----
# needs: postgres
pg = psycopg.connect(DATABASE_URL, autocommit=True)
schema, analyst = sql.Identifier(PG_SCHEMA), sql.Identifier(ANALYST)
pg.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(schema))  # empty the lesson's area
pg.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(analyst))  # and remove section 8's account
pg.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
pg.execute(sql.SQL("SET search_path TO {}, public").format(schema))
pg.execute("""
CREATE TABLE compound (
    compound_id integer PRIMARY KEY,
    inchikey    text NOT NULL UNIQUE CHECK (length(inchikey) = 27),
    smiles      text NOT NULL,
    mw          numeric(7, 2) NOT NULL CHECK (mw > 0),
    mol         mol
)""")
with pg.cursor() as cur, cur.copy("COPY compound (compound_id, inchikey, smiles, mw) FROM STDIN") as copy:
    for row in compounds.itertuples(index=False):
        copy.write_row((int(row.compound_id), row.inchikey, row.smiles, float(row.mw)))
pg.execute("UPDATE compound SET mol = mol_from_smiles(smiles::cstring)")
pg.execute("ALTER TABLE compound ALTER COLUMN mol SET NOT NULL")
pg.execute("ANALYZE compound")  # let PostgreSQL count what is in the table, for planning (below)
total, with_mol = pg.execute("SELECT count(*), count(mol) FROM compound").fetchone()
log.info("loaded %s compounds into PostgreSQL, %s with a molecule", f"{total:,}", f"{with_mol:,}")

# ---- Substructure search, and the ester trap ----
# needs: postgres
examples = {
    "acetic acid": "CC(=O)O",
    "methyl salicylate": "COC(=O)c1ccccc1O",
    "ibuprofen": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
}
for name, smiles in examples.items():
    as_molecule, as_smarts = pg.execute(
        "SELECT %s::mol @> 'C(=O)O'::mol, %s::mol @> %s::qmol", (smiles, smiles, ACID_SMARTS)
    ).fetchone()
    print(f"{name:18} C(=O)O as a molecule: {as_molecule}   acid SMARTS: {as_smarts}")
plain, acids = pg.execute(
    "SELECT count(*) FILTER (WHERE mol @> 'C(=O)O'::mol), count(*) FILTER (WHERE mol @> %s::qmol)"
    " FROM compound", (ACID_SMARTS,)
).fetchone()  # fmt: skip
print(f"in the library: {plain} compounds contain C(=O)O as a molecule; {acids} are acids")

# ---- Similarity search ----
# needs: postgres
query = compounds.smiles[0]
print("query:", query)
for compound_id, smiles, similarity in pg.execute("""
    SELECT compound_id, smiles,
           round(tanimoto_sml(morganbv_fp(mol), morganbv_fp(%s::mol))::numeric, 3) AS similarity
    FROM compound
    ORDER BY similarity DESC, compound_id
    LIMIT 5""", (query,)).fetchall():  # fmt: skip
    print(f"{compound_id:5}  {similarity}  {smiles}")

# ---- Indexes, and how to see one at work ----
# needs: postgres
search = sql.SQL("SELECT compound_id FROM compound WHERE mol @> {}::qmol").format(sql.Literal(ACID_SMARTS))


def plan(query: sql.Composable) -> str:
    """The first line of PostgreSQL's plan for a query: how it will find the rows."""
    return pg.execute(sql.SQL("EXPLAIN ") + query).fetchall()[0][0].split("  (")[0]


print("without an index:", plan(search))
pg.execute("CREATE INDEX compound_mol ON compound USING gist (mol)")
pg.execute("ANALYZE compound")
print("with the index:  ", plan(search))

# ---- 8. Safe access: accounts, rights and passwords ----
# needs: postgres
pg.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(analyst, sql.Literal(ANALYST_PASSWORD)))
pg.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, analyst))
pg.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(schema, analyst))

analyst_url = make_conninfo(DATABASE_URL, user=ANALYST, password=ANALYST_PASSWORD)
with psycopg.connect(analyst_url, autocommit=True) as colleague:
    colleague.execute(sql.SQL("SET search_path TO {}, public").format(schema))
    count = colleague.execute("SELECT count(*) FROM compound").fetchone()[0]
    print(f"the analyst can read: {count:,} compounds")
    try:
        colleague.execute("DELETE FROM compound")
    except psycopg.errors.InsufficientPrivilege as error:
        print("the analyst cannot delete:", str(error).strip())
pg.close()

# ---- Values from outside: SQL injection ----
shop = duckdb.connect(DUCKDB_FILE, read_only=True)  # the search page's connection: reading only


def find_supplier_unsafe(name: str) -> list:
    """A search written the WRONG way: the user's text is pasted into the SQL."""
    return shop.execute(f"SELECT name, country FROM supplier WHERE name = '{name}'").fetchall()


print(find_supplier_unsafe("Vendor A"))
print(find_supplier_unsafe("nobody' OR '1'='1"))
print(find_supplier_unsafe("nobody' UNION SELECT inchikey, smiles FROM compound ORDER BY 1 LIMIT 2 --"))
try:
    find_supplier_unsafe("nobody'; DROP TABLE measurement; --")
except duckdb.Error as error:
    print("refused:", str(error).splitlines()[0])
def find_supplier(name: str) -> list:
    """The same search, written safely: the name is passed as a parameter, never as SQL."""
    return shop.execute("SELECT name, country FROM supplier WHERE name = ?", [name]).fetchall()


for attempt in ["Vendor A", "nobody' OR '1'='1", "nobody'; DROP TABLE measurement; --"]:
    print(f"{attempt!r:40} -> {find_supplier(attempt)}")
SORTABLE = {"name", "country"}  # the columns the search page may sort by


def suppliers_sorted_by(column: str) -> list:
    """Suppliers sorted by a column the user chose, checked against the allowed names first."""
    if column not in SORTABLE:
        raise ValueError(f"cannot sort by {column!r}")
    return [row[0] for row in shop.execute(f"SELECT name FROM supplier ORDER BY {column}").fetchall()]


print(suppliers_sorted_by("country"))
try:
    suppliers_sorted_by("name; DROP TABLE measurement")
except ValueError as error:
    print("refused:", error)
shop.close()
