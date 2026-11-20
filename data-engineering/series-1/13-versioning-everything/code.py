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

# ---- 1. Code: commits and tags ----
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

WORK = Path("work")
WORK.mkdir(exist_ok=True)


def remove_tree(path: Path) -> None:
    """Delete a folder if it exists, including the read-only files git leaves on Windows."""

    def make_writable_and_retry(func, failed_path, _error):
        os.chmod(failed_path, stat.S_IWRITE)
        func(failed_path)

    if path.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=make_writable_and_retry)
        else:
            shutil.rmtree(path, onerror=make_writable_and_retry)


def git(repo: Path, *args: str) -> str:
    """Run a git command in repo and return what it prints."""
    identity = ["-c", "user.name=Course", "-c", "user.email=course@example.org"]
    result = subprocess.run(
        ["git", *identity, "-c", "core.autocrlf=false", *args],  # keep files byte for byte
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


repo = WORK / "pipeline-code"
remove_tree(repo)
repo.mkdir()
git(repo, "init", "--quiet", "--initial-branch=main")
version_1 = 'def to_nm(value, units):\n    return value * {"nM": 1, "uM": 1_000}[units]\n'
(repo / "convert.py").write_text(version_1, encoding="utf-8", newline="\n")
git(repo, "add", "convert.py")
git(repo, "commit", "--quiet", "-m", "Convert activities to nM")
git(repo, "tag", "v1.0.0")
print("version:", git(repo, "describe", "--tags", "--always", "--dirty"))
version_2 = version_1.replace('"uM": 1_000', '"µM": 1_000, "mM": 1_000_000')
(repo / "convert.py").write_text(version_2, encoding="utf-8", newline="\n")
print("after an edit:", git(repo, "describe", "--tags", "--always", "--dirty"))
import re

git(repo, "commit", "--quiet", "-am", "Accept µM and mM")
described = git(repo, "describe", "--tags", "--always", "--dirty")
commit = git(repo, "rev-parse", "HEAD")
print("after a commit:", re.sub(r"g[0-9a-f]+$", "g<commit>", described))
print("a commit's full name is", len(commit), "hexadecimal characters")
print("v1.0.0 is still there:", git(repo, "show", "v1.0.0:convert.py") + "\n" == version_1)

# ---- Recording versions at run time ----
import json
import platform
from importlib import metadata

PACKAGES = ["pandas", "numpy", "duckdb", "dvc"]


def environment(packages: list[str]) -> dict[str, str]:
    """The Python version and the installed version of each package, as they are right now."""
    return {"python": platform.python_version(), **{p: metadata.version(p) for p in packages}}


print(json.dumps(environment(PACKAGES), indent=2))
everything = sorted(f"{d.metadata['Name']}=={d.version}" for d in metadata.distributions())
(WORK / "installed.txt").write_text("\n".join(everything) + "\n", encoding="utf-8")
print(len(everything), "packages installed in all, written to work/installed.txt")

# ---- 3. Database schemas: numbered migrations ----
import hashlib

import duckdb


def sha256_text(text: str) -> str:
    """The SHA-256 hash of a text, as 64 hexadecimal characters."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


migrations = WORK / "migrations"
remove_tree(migrations)
migrations.mkdir()
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
    (migrations / name).write_text(sql, encoding="utf-8", newline="\n")


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
        done.append(path.name)
    return done


db_path = WORK / "chem.duckdb"
db_path.unlink(missing_ok=True)
db = duckdb.connect(str(db_path))
print("first run applied: ", migrate(db, migrations))
print("second run applied:", migrate(db, migrations))
print("schema version:", db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0])
(migrations / "0004_index_measurements_by_compound.sql").write_text(
    "CREATE INDEX measurements_by_compound ON measurements (compound_id);\n",
    encoding="utf-8", newline="\n",
)
print("applied:", migrate(db, migrations))
columns = db.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name = 'measurements' ORDER BY ordinal_position"
).fetchall()
print("measurements:", [c[0] for c in columns])
first = migrations / "0001_create_compounds.sql"
first.write_text(FIRST_MIGRATIONS["0001_create_compounds.sql"].replace(
    "inchikey TEXT NOT NULL", "inchikey TEXT"), encoding="utf-8", newline="\n")
try:
    migrate(db, migrations)
except RuntimeError as error:
    print("refused:", error)
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
import pandas as pd

import chemlib

data = WORK / "data"
remove_tree(data)
data.mkdir()
library = chemlib.library(5_000, seed=21)
library.to_csv(data / "compounds.csv", index=False, lineterminator="\n")
library[["id", "price_usd"]].head(1_000).to_csv(data / "prices.csv", index=False,
                                                 lineterminator="\n")


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    """The SHA-256 of a file, read one chunk (1 MiB) at a time."""
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


manifest = build_manifest(data)
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


print("before:", check_manifest(data, manifest))
prices = pd.read_csv(data / "prices.csv")
prices.loc[0, "price_usd"] = prices.loc[0, "price_usd"] + 0.01
prices.to_csv(data / "prices.csv", index=False, lineterminator="\n")
print("after: ", check_manifest(data, manifest))
new_hash = file_sha256(data / "prices.csv")
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


project = WORK / "dvc-project"
remove_tree(project)
remove_tree(WORK / "dvc-store")
(project / "data").mkdir(parents=True)
git(project, "init", "--quiet", "--initial-branch=main")
dvc(project, "init", "--quiet")
shutil.copy(data / "compounds.csv", project / "data" / "compounds.csv")
dvc(project, "add", "data/compounds.csv")
pointer = project / "data" / "compounds.csv.dvc"
print(pointer.read_text(encoding="utf-8"))
print("git ignores the data itself:", (project / "data" / ".gitignore").read_text().strip())
print("the md5 is the file's own:",
      hashlib.md5((data / "compounds.csv").read_bytes()).hexdigest() in pointer.read_text())
git(project, "add", ".")
git(project, "commit", "--quiet", "-m", "Track compounds.csv with DVC")
dvc(project, "remote", "add", "--default", "store", str((WORK / "dvc-store").resolve()))
dvc(project, "push")
(project / "data" / "compounds.csv").unlink()
remove_tree(project / ".dvc" / "cache")
dvc(project, "pull")
restored = file_sha256(project / "data" / "compounds.csv")
print("restored from the remote, same bytes:", restored == file_sha256(data / "compounds.csv"))
changed = pd.read_csv(project / "data" / "compounds.csv").head(4_000)  # 1,000 rows withdrawn
changed.to_csv(project / "data" / "compounds.csv", index=False, lineterminator="\n")
dvc(project, "add", "data/compounds.csv")
git(project, "commit", "--quiet", "-am", "Withdraw 1,000 compounds")


def tracked_md5(project: Path) -> str:
    """The md5 that the .dvc pointer of compounds.csv names."""
    text = (project / "data" / "compounds.csv.dvc").read_text(encoding="utf-8")
    return re.search(r"md5: ([0-9a-f]+)", text).group(1)


def rows(project: Path) -> int:
    """How many compounds the data file in the project holds."""
    return len(pd.read_csv(project / "data" / "compounds.csv"))


print("now: ", tracked_md5(project), rows(project), "rows")
git(project, "checkout", "--quiet", "HEAD~1", "--", "data/compounds.csv.dvc")
dvc(project, "checkout")
print("back:", tracked_md5(project), rows(project), "rows")
git(project, "checkout", "--quiet", "HEAD", "--", "data/compounds.csv.dvc")
dvc(project, "checkout")

# ---- 6. Results: a provenance record next to every output ----
from datetime import datetime, timezone


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
    record = {
        "result": {"file": path.name, "sha256": file_sha256(path)},
        "code_version": git(repo, "describe", "--tags", "--always", "--dirty"),
        "environment": environment(PACKAGES),
        "schema_version": db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0],
        "rules": {"version": RULES["version"], "sha256": rules_hash(RULES)},
        "inputs": {p.as_posix(): file_sha256(p) for p in inputs},
        "parameters": parameters,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    record_path = path.with_name(path.name + ".provenance.json")
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


results = WORK / "results"
remove_tree(results)
results.mkdir()
params = {"min_stock_mg": 100}
summary = median_price_by_vendor(data / "compounds.csv", **params)
record = write_with_provenance(summary, results / "median-price.csv", [data / "compounds.csv"],
                               params)
print(summary.to_string(index=False))
print("written:", sorted(p.name for p in results.iterdir()))
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


record_path = results / "median-price.csv.provenance.json"
print("check:", check_provenance(record_path))
rebuilt = median_price_by_vendor(data / "compounds.csv", **record["parameters"])
rebuilt.to_csv(WORK / "rebuilt.csv", index=False, lineterminator="\n")
print("rebuilt, same bytes:", file_sha256(WORK / "rebuilt.csv") == record["result"]["sha256"])
stock = pd.read_csv(data / "compounds.csv")
stock.loc[stock.index[:50], "stock_mg"] = 0  # 50 compounds sold out
stock.to_csv(data / "compounds.csv", index=False, lineterminator="\n")
print("check:", check_provenance(record_path))
db.close()
