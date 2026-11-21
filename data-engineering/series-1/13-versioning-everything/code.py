"""Versioning everything: the code of the lesson, in order.

Version code, environments, database schemas, standardisation rules, data and results, so any number in a report can be traced back to what made it and rebuilt exactly.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/13-versioning-everything/
Run it from anywhere, e.g. from the series folder: uv run python 13-versioning-everything/code.py
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
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import duckdb
import pandas as pd

import chemlib

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
REPO = WORK / "pipeline-code"  # the small git repository of section 1
MIGRATIONS = WORK / "migrations"  # the numbered SQL files of section 3
DB_PATH = WORK / "chem.duckdb"  # the database they are applied to
DATA = WORK / "data"  # the data files of section 5
DVC_PROJECT = WORK / "dvc-project"  # the git + DVC repository of section 5
DVC_STORE = WORK / "dvc-store"  # the folder that stands in for a DVC remote
RESULTS = WORK / "results"  # results and their provenance records (section 6)
# the name and e-mail git writes on the lesson's commits, whatever your own git settings are
GIT_NAME = "Course"
GIT_EMAIL = "course@example.org"
# the packages whose versions every provenance record names
PACKAGES = ["pandas", "numpy", "duckdb", "dvc"]
# the data: how many compounds, the seed that makes them, and how many have a price file row
LIBRARY_SIZE = 5_000
LIBRARY_SEED = 21
N_PRICES = 1_000
# files are hashed this many bytes at a time (1 MiB), so a large file is never all in memory
HASH_CHUNK_BYTES = 1 << 20
# the run parameter of section 6: the smallest stock, in mg, for a compound to count
MIN_STOCK_MG = 100

WORK.mkdir(exist_ok=True)

# ---- 1. Code: commits and tags ----
def remove_tree(path: Path) -> None:
    """Delete a folder if it exists, including the read-only files git leaves on Windows."""

    def make_writable_and_retry(func: Callable[[str], object], failed_path: str,
                                _error: object) -> None:
        """Make a file that could not be deleted writable, and delete it again."""
        os.chmod(failed_path, stat.S_IWRITE)
        func(failed_path)

    if path.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=make_writable_and_retry)
        else:
            shutil.rmtree(path, onerror=make_writable_and_retry)


def git(repo: Path, *args: str) -> str:
    """Run a git command in repo and return what it prints."""
    identity = ["-c", f"user.name={GIT_NAME}", "-c", f"user.email={GIT_EMAIL}"]
    result = subprocess.run(
        ["git", *identity, "-c", "core.autocrlf=false", *args],  # keep files byte for byte
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


remove_tree(REPO)
REPO.mkdir()
git(REPO, "init", "--quiet", "--initial-branch=main")
version_1 = 'def to_nm(value, units):\n    return value * {"nM": 1, "uM": 1_000}[units]\n'
(REPO / "convert.py").write_text(version_1, encoding="utf-8", newline="\n")
git(REPO, "add", "convert.py")
git(REPO, "commit", "--quiet", "-m", "Convert activities to nM")
git(REPO, "tag", "v1.0.0")
print("version:", git(REPO, "describe", "--tags", "--always", "--dirty"))
version_2 = version_1.replace('"uM": 1_000', '"µM": 1_000, "mM": 1_000_000')
(REPO / "convert.py").write_text(version_2, encoding="utf-8", newline="\n")
print("after an edit:", git(REPO, "describe", "--tags", "--always", "--dirty"))
git(REPO, "commit", "--quiet", "-am", "Accept µM and mM")
described = git(REPO, "describe", "--tags", "--always", "--dirty")
commit = git(REPO, "rev-parse", "HEAD")
print("after a commit:", re.sub(r"g[0-9a-f]+$", "g<commit>", described))
print("a commit's full name is", len(commit), "hexadecimal characters")
print("v1.0.0 is still there:", git(REPO, "show", "v1.0.0:convert.py") + "\n" == version_1)

# ---- Recording versions at run time ----
def environment(packages: list[str]) -> dict[str, str]:
    """The Python version and the installed version of each package, as they are right now."""
    return {"python": platform.python_version(), **{p: metadata.version(p) for p in packages}}


print(json.dumps(environment(PACKAGES), indent=2))
everything = sorted(f"{d.metadata['Name']}=={d.version}" for d in metadata.distributions())
installed = WORK / "installed.txt"
installed.write_text("\n".join(everything) + "\n", encoding="utf-8")
log.info("wrote %d installed packages to %s", len(everything), installed.as_posix())

# ---- 3. Database schemas: numbered migrations ----
def sha256_text(text: str) -> str:
    """The SHA-256 hash of a text, as 64 hexadecimal characters."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


remove_tree(MIGRATIONS)
MIGRATIONS.mkdir()
FIRST_MIGRATIONS = {
    "0001_create_compounds.sql": (
        "CREATE TABLE compounds (\n"
        "    compound_id TEXT PRIMARY KEY,\n"
        "    smiles TEXT NOT NULL,\n"
        "    inchikey TEXT NOT NULL\n"
        ");\n"
    ),
    "0002_create_measurements.sql": (
        "CREATE TABLE measurements (\n"
        "    measurement_id TEXT PRIMARY KEY,\n"
        "    compound_id TEXT NOT NULL REFERENCES compounds (compound_id),\n"
        "    target_id TEXT NOT NULL,\n"
        "    value_nm DOUBLE NOT NULL CHECK (value_nm > 0)\n"
        ");\n"
    ),
    "0003_add_pchembl.sql": "ALTER TABLE measurements ADD COLUMN pchembl DOUBLE;\n",
}
for name, sql in FIRST_MIGRATIONS.items():
    (MIGRATIONS / name).write_text(sql, encoding="utf-8", newline="\n")


def migrate(db: duckdb.DuckDBPyConnection, folder: Path) -> list[str]:
    """Apply, in order, every migration in folder that the database has not had yet.

    Each one runs in a transaction with its record in schema_migrations, so it is applied
    completely or not at all. A migration that was changed after it was applied is refused.
    """
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL)"
    )
    applied = dict(db.execute("SELECT version, sha256 FROM schema_migrations").fetchall())
    done = []
    for path in sorted(folder.glob("*.sql")):
        version = int(path.name.split("_")[0])
        sql = path.read_text(encoding="utf-8")
        if version in applied:
            if applied[version] != sha256_text(sql):
                raise RuntimeError(f"{path.name} was changed after it was applied")
            continue
        db.execute("BEGIN TRANSACTION")
        try:
            db.execute(sql)
            db.execute("INSERT INTO schema_migrations VALUES (?, ?, ?)",
                       [version, path.name, sha256_text(sql)])
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
        log.info("applied %s", path.name)
        done.append(path.name)
    return done


def schema_version(db: duckdb.DuckDBPyConnection) -> int:
    """The number of the last migration the database has had."""
    return db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]


DB_PATH.unlink(missing_ok=True)
with duckdb.connect(str(DB_PATH)) as db:
    migrate(db, MIGRATIONS)
    print("second run applied:", migrate(db, MIGRATIONS))
    print("schema version:", schema_version(db))
(MIGRATIONS / "0004_index_measurements_by_compound.sql").write_text(
    "CREATE INDEX measurements_by_compound ON measurements (compound_id);\n",
    encoding="utf-8", newline="\n",
)
with duckdb.connect(str(DB_PATH)) as db:
    migrate(db, MIGRATIONS)
    columns = db.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'measurements' ORDER BY ordinal_position"
    ).fetchall()
print("measurements:", [c[0] for c in columns])
first = MIGRATIONS / "0001_create_compounds.sql"
first.write_text(FIRST_MIGRATIONS["0001_create_compounds.sql"].replace(
    "inchikey TEXT NOT NULL", "inchikey TEXT"), encoding="utf-8", newline="\n")
with duckdb.connect(str(DB_PATH)) as db:
    try:
        migrate(db, MIGRATIONS)
    except RuntimeError as error:
        log.error("refused: %s", error)
first.write_text(FIRST_MIGRATIONS["0001_create_compounds.sql"], encoding="utf-8", newline="\n")

# ---- 4. Standardisation rules: a version and a hash ----
RULES = {
    "version": "2.1.0",
    "keep_largest_fragment": True,
    "neutralise": True,
    "canonical_tautomer": False,
    "allowed_elements": ["C", "N", "O", "S", "F", "Cl", "Br", "H"],
}


def rules_hash(rules: dict) -> str:
    """The SHA-256 of the rules in a canonical form: sorted keys, no spaces."""
    return sha256_text(json.dumps(rules, sort_keys=True, separators=(",", ":")))


print("rules", RULES["version"], "hash", rules_hash(RULES)[:16])
reordered = dict(reversed(list(RULES.items())))
print("same rules written in another order, same hash:", rules_hash(reordered) == rules_hash(RULES))
RELEASED_RULES = {"2.1.0": rules_hash(RULES)}


def check_rules(rules: dict) -> str:
    """'ok' if these rules are the released ones for their version, otherwise why not."""
    known = RELEASED_RULES.get(rules["version"])
    if known is None:
        return f"version {rules['version']} was never released"
    if known != rules_hash(rules):
        return f"rules changed but the version is still {rules['version']}"
    return "ok"


print(check_rules(RULES))
print(check_rules({**RULES, "canonical_tautomer": True}))
print(check_rules({**RULES, "version": "2.2.0", "canonical_tautomer": True}))

# ---- 5. Data: content hashes and a manifest ----
remove_tree(DATA)
DATA.mkdir()
library = chemlib.library(LIBRARY_SIZE, seed=LIBRARY_SEED)
library.to_csv(DATA / "compounds.csv", index=False, lineterminator="\n")
library[["id", "price_usd"]].head(N_PRICES).to_csv(DATA / "prices.csv", index=False,
                                                    lineterminator="\n")


def file_sha256(path: Path, chunk: int = HASH_CHUNK_BYTES) -> str:
    """The SHA-256 of a file, read one chunk at a time."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(folder: Path) -> list[dict]:
    """Every file under folder with its path, size in bytes and SHA-256, in path order."""
    return [
        {"path": p.relative_to(folder).as_posix(), "bytes": p.stat().st_size,
         "sha256": file_sha256(p)}
        for p in sorted(folder.rglob("*")) if p.is_file()
    ]


manifest = build_manifest(DATA)
(WORK / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
for entry in manifest:
    print(f"{entry['path']:14} {entry['bytes']:>8,} bytes  sha256 {entry['sha256'][:16]}...")
def check_manifest(folder: Path, manifest: list[dict]) -> list[str]:
    """What differs between the files under folder and the manifest (empty if nothing)."""
    expected = {e["path"]: e["sha256"] for e in manifest}
    found = {e["path"]: e["sha256"] for e in build_manifest(folder)}
    problems = [f"missing: {p}" for p in expected if p not in found]
    problems += [f"new: {p}" for p in found if p not in expected]
    problems += [f"changed: {p}" for p in expected if p in found and found[p] != expected[p]]
    return problems


print("before:", check_manifest(DATA, manifest))
prices = pd.read_csv(DATA / "prices.csv")
prices.loc[0, "price_usd"] = prices.loc[0, "price_usd"] + 0.01
prices.to_csv(DATA / "prices.csv", index=False, lineterminator="\n")
print("after: ", check_manifest(DATA, manifest))
new_hash = file_sha256(DATA / "prices.csv")
old_hash = next(e["sha256"] for e in manifest if e["path"] == "prices.csv")
print("old hash", old_hash[:16], "new hash", new_hash[:16])

# ---- Large data: DVC ----
def dvc(repo: Path, *args: str) -> str:
    """Run a DVC command in repo and return what it prints."""
    result = subprocess.run(
        [sys.executable, "-m", "dvc", *args],
        cwd=repo, capture_output=True, text=True, check=True,
        env={**os.environ, "DVC_NO_ANALYTICS": "1"},
    )
    return result.stdout.strip()


remove_tree(DVC_PROJECT)
remove_tree(DVC_STORE)
(DVC_PROJECT / "data").mkdir(parents=True)
git(DVC_PROJECT, "init", "--quiet", "--initial-branch=main")
dvc(DVC_PROJECT, "init", "--quiet")
shutil.copy(DATA / "compounds.csv", DVC_PROJECT / "data" / "compounds.csv")
dvc(DVC_PROJECT, "add", "data/compounds.csv")
pointer = (DVC_PROJECT / "data" / "compounds.csv.dvc").read_text(encoding="utf-8")
ignored = (DVC_PROJECT / "data" / ".gitignore").read_text(encoding="utf-8").strip()
print(pointer)
print("git ignores the data itself:", ignored)
print("the md5 is the file's own:",
      hashlib.md5((DATA / "compounds.csv").read_bytes()).hexdigest() in pointer)
git(DVC_PROJECT, "add", ".")
git(DVC_PROJECT, "commit", "--quiet", "-m", "Track compounds.csv with DVC")
dvc(DVC_PROJECT, "remote", "add", "--default", "store", str(DVC_STORE.resolve()))
dvc(DVC_PROJECT, "push")
(DVC_PROJECT / "data" / "compounds.csv").unlink()
remove_tree(DVC_PROJECT / ".dvc" / "cache")
dvc(DVC_PROJECT, "pull")
restored = file_sha256(DVC_PROJECT / "data" / "compounds.csv")
print("restored from the remote, same bytes:", restored == file_sha256(DATA / "compounds.csv"))
changed = pd.read_csv(DVC_PROJECT / "data" / "compounds.csv").head(4_000)  # 1,000 withdrawn
changed.to_csv(DVC_PROJECT / "data" / "compounds.csv", index=False, lineterminator="\n")
dvc(DVC_PROJECT, "add", "data/compounds.csv")
git(DVC_PROJECT, "commit", "--quiet", "-am", "Withdraw 1,000 compounds")


def tracked_md5(project: Path) -> str:
    """The md5 that the .dvc pointer of compounds.csv names."""
    text = (project / "data" / "compounds.csv.dvc").read_text(encoding="utf-8")
    return re.search(r"md5: ([0-9a-f]+)", text).group(1)


def rows(project: Path) -> int:
    """How many compounds the data file in the project holds."""
    return len(pd.read_csv(project / "data" / "compounds.csv"))


print("now: ", tracked_md5(DVC_PROJECT), rows(DVC_PROJECT), "rows")
git(DVC_PROJECT, "checkout", "--quiet", "HEAD~1", "--", "data/compounds.csv.dvc")
dvc(DVC_PROJECT, "checkout")
print("back:", tracked_md5(DVC_PROJECT), rows(DVC_PROJECT), "rows")
git(DVC_PROJECT, "checkout", "--quiet", "HEAD", "--", "data/compounds.csv.dvc")
dvc(DVC_PROJECT, "checkout")

# ---- 6. Results: a provenance record next to every output ----
def median_price_by_vendor(compounds: Path, min_stock_mg: int) -> pd.DataFrame:
    """The median price and the number of compounds per vendor, for compounds in stock."""
    table = pd.read_csv(compounds)
    in_stock = table[table["stock_mg"] >= min_stock_mg]
    summary = in_stock.groupby("vendor")["price_usd"].agg(["median", "count"])
    return summary.reset_index()


def write_with_provenance(result: pd.DataFrame, path: Path, inputs: list[Path],
                          parameters: dict) -> dict:
    """Write a result as CSV and, next to it, a record of everything that made it."""
    result.to_csv(path, index=False, lineterminator="\n")
    with duckdb.connect(str(DB_PATH), read_only=True) as db:
        version = schema_version(db)
    record = {
        "result": {"file": path.name, "sha256": file_sha256(path)},
        "code_version": git(REPO, "describe", "--tags", "--always", "--dirty"),
        "environment": environment(PACKAGES),
        "schema_version": version,
        "rules": {"version": RULES["version"], "sha256": rules_hash(RULES)},
        "inputs": {p.as_posix(): file_sha256(p) for p in inputs},
        "parameters": parameters,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    record_path = path.with_name(path.name + ".provenance.json")
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    log.info("wrote %s and %s", path.name, record_path.name)
    return record


remove_tree(RESULTS)
RESULTS.mkdir()
params = {"min_stock_mg": MIN_STOCK_MG}
summary = median_price_by_vendor(DATA / "compounds.csv", **params)
record = write_with_provenance(summary, RESULTS / "median-price.csv", [DATA / "compounds.csv"],
                               params)
print(summary.to_string(index=False))
print(json.dumps(record, indent=2))
print("schema_version:", record["schema_version"])
print("rules:", record["rules"]["version"], record["rules"]["sha256"][:16] + "...")
for name, digest in record["inputs"].items():
    print("input:", name, digest[:16] + "...")
print("parameters:", record["parameters"])
print("result:", record["result"]["file"], record["result"]["sha256"][:16] + "...")
def check_provenance(record_path: Path) -> list[str]:
    """What has changed since the result was made (empty if nothing)."""
    record = json.loads(record_path.read_text(encoding="utf-8"))
    problems = []
    for name, digest in record["inputs"].items():
        if not Path(name).exists():
            problems.append(f"input missing: {name}")
        elif file_sha256(Path(name)) != digest:
            problems.append(f"input changed: {name}")
    if rules_hash(RULES) != record["rules"]["sha256"]:
        problems.append("standardisation rules changed")
    if record["code_version"].endswith("-dirty"):
        problems.append("made with uncommitted code")
    return problems


record_path = RESULTS / "median-price.csv.provenance.json"
print("check:", check_provenance(record_path))
rebuilt = median_price_by_vendor(DATA / "compounds.csv", **record["parameters"])
rebuilt.to_csv(WORK / "rebuilt.csv", index=False, lineterminator="\n")
print("rebuilt, same bytes:", file_sha256(WORK / "rebuilt.csv") == record["result"]["sha256"])
stock = pd.read_csv(DATA / "compounds.csv")
stock.loc[stock.index[:50], "stock_mg"] = 0  # 50 compounds sold out
stock.to_csv(DATA / "compounds.csv", index=False, lineterminator="\n")
print("check:", check_provenance(record_path))
