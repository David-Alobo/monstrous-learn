---
title: Versioning everything
summary: Version code, environments, database schemas, standardisation rules, data and results, so any number in a report can be traced back to what made it and rebuilt exactly.
requires: pandas, duckdb, dvc
---

A report says the median pIC50 of a series against EGFR is 7.2. A year later a reviewer asks how
that number was made, or a colleague gets 7.0 from what they believe is the same data. To answer,
you need five things exactly as they were on the day: the **code** that computed it, the
**environment** it ran in (Python, RDKit, pandas and their versions), the **database schema** it
read from, the **rules** that standardised the molecules, and the **data** itself. If any one of
them has changed since and nobody recorded which version was used, the number cannot be checked,
and an argument about whether 7.2 or 7.0 is right has nothing to stand on.

Data engineers solve this by versioning all five and writing, next to every result, a small
record of which versions made it. This module does each in turn, by hand first, then with the
tool industry uses for it.

By the end of this module you will be able to:

- tag a version of your code with git and read back which version produced a result;
- lock an environment with uv, record package versions at run time, and pin a container image;
- change a database schema with numbered migrations that apply once and in order;
- give standardisation rules a version and a hash that catches unrecorded changes;
- hash data files, keep a manifest, and version large data with DVC;
- write a provenance record next to every result, and check it later.

Everything here runs on any laptop and in a browser notebook: you need Python, pandas, DuckDB, DVC
and git (installed with most systems and in Colab).

![What gets versioned and how the pieces connect: a git commit pins the code and, because they are files in the repository, the lock file, the migrations, the rules and the small .dvc files that point at the data by hash; the image digest pins the operating system; a provenance record next to each result names all of them](figures/what-gets-versioned.svg)

## 1. Code: commits and tags

Git records every version of a project as a **commit**, named by a hash of its contents and
history, so a commit can never be changed without getting a new name. A **tag** is a readable
name for one commit, such as `v1.0.0`, used for versions that matter: a release, the code behind
a paper.

We run git from Python, in a small repository under `work/`, so the lesson runs the same way on
every computer. The helper gives git a name and e-mail for the commits, so it does not depend on
how git is set up on your machine:

```python
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
```
```output
version: v1.0.0
```

`git describe` names the code a result was made with. It gives the tag when the code is exactly
the tagged commit; when the code has been changed and not committed, it adds `-dirty`:

```python
version_2 = version_1.replace('"uM": 1_000', '"µM": 1_000, "mM": 1_000_000')
(repo / "convert.py").write_text(version_2, encoding="utf-8", newline="\n")
print("after an edit:", git(repo, "describe", "--tags", "--always", "--dirty"))
```
```output
after an edit: v1.0.0-dirty
```

A result made by "dirty" code cannot be rebuilt: the code that made it exists only until the next
edit. A careful pipeline refuses to write results from dirty code, or at least says so loudly in
every result it writes. Commit the change, and the name says how far the code is from the tag:

```python
import re

git(repo, "commit", "--quiet", "-am", "Accept µM and mM")
described = git(repo, "describe", "--tags", "--always", "--dirty")
commit = git(repo, "rev-parse", "HEAD")
print("after a commit:", re.sub(r"g[0-9a-f]+$", "g<commit>", described))
print("a commit's full name is", len(commit), "hexadecimal characters")
print("v1.0.0 is still there:", git(repo, "show", "v1.0.0:convert.py") + "\n" == version_1)
```
```output
after a commit: v1.0.0-1-g<commit>
a commit's full name is 40 hexadecimal characters
v1.0.0 is still there: True
```

`v1.0.0-1-g<commit>` reads "one commit after v1.0.0, at commit …" (the hash differs on every
computer, because it includes the time of the commit). `git show v1.0.0:convert.py` brings back
the code exactly as it was at the tag: if a result says it was made with `v1.0.0`, that is the
code to read.

## 2. Environments: lock files, recorded versions and images

The same code gives different answers in different environments. A new RDKit release can change
a canonical SMILES, an aromaticity model or a descriptor; a new pandas can give the same column
a different type (pandas 3 reads text columns as a new string type). So the environment is
versioned too, in three layers.

### Lock files

`pyproject.toml` says what a project needs, usually as ranges (`rdkit>=2024.9`). A **lock file**
says exactly what was installed: every package, including the ones nobody asked for directly, at
one version, with the hash of every file that may be downloaded. This course's own environment is
locked in `uv.lock`; here is part of its entry for RDKit:

```toml
[[package]]
name = "rdkit"
version = "2026.9.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "numpy", ... },
    { name = "pillow" },
]
wheels = [
    { url = ".../rdkit-2026.9.2-cp311-cp311-win_amd64.whl", hash = "sha256:020a72efc524e872..." },
    ... one line per operating system and Python version
]
```

`uv lock` writes the lock file from `pyproject.toml`; `uv sync --locked` installs exactly what it
says, and fails if the lock file no longer matches the project, instead of quietly installing
something newer. The lock file is committed with the code, so a commit pins the environment too.
With pip, the nearest equivalent is a requirements file with every version pinned and
`--require-hashes`.

```bash
uv lock            # resolve pyproject.toml into uv.lock
uv sync --locked   # install exactly uv.lock, or fail if it is out of date
```

### Recording versions at run time

A lock file says what *should* be installed. What *was* installed when a result was made is
another question (someone ran `pip install --upgrade` in the environment last week), so a
pipeline records it while it runs, with `importlib.metadata` from the standard library:

```python
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
```
```output varies
{
  "python": "3.11.17",
  "pandas": "3.1.1",
  "numpy": "2.4.6",
  "duckdb": "2.0.0",
  "dvc": "3.67.1"
}
140 packages installed in all, written to work/installed.txt
```

Your versions will differ from these, which is the point: without the record nobody can tell.

### Container images: tags and digests

The lock file pins Python packages, but not Python itself, nor the operating system libraries
under it. A container image pins all of it. A `Dockerfile` describes the image:

```dockerfile
FROM python:3.12-slim@sha256:<the digest of the exact image>
RUN pip install --no-cache-dir uv==0.13.4
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY src/ ./src/
CMD ["uv", "run", "python", "-m", "src.pipeline"]
```

The first line is the one that matters here. `python:3.12-slim` is a **tag**: a name that the
image's publisher moves to a new image whenever Python 3.12 gets a patch release or Debian a
security fix. Building the same Dockerfile next month can give a different image. The **digest**
after `@sha256:` is a hash of the image's contents, like a commit hash: it can only ever mean one
image. `docker images --digests` shows the digest of an image you have, and `docker pull
python@sha256:…` fetches exactly that image again. Pin by digest for anything a result depends
on, and update the digest on purpose, in a commit, like any other version. (The databases this
course runs in Docker are pinned to exact release tags; a digest would pin them further.)

## 3. Database schemas: numbered migrations

A database's schema (its tables, columns and constraints) changes as a project grows: a column for
pChEMBL is added, an index is built, a table is split. If those changes are made by hand at a
database prompt, nobody knows which version of the schema a database has, and a new copy of the
database cannot be made the same way.

**Migrations** fix this. Each change is a numbered SQL file, committed with the code, applied in
order, and recorded in a table in the database itself. Applying them is then idempotent (Module
10): running it again applies only what is new. Tools such as Alembic, Flyway and Liquibase do
this for large projects; the idea fits in one function.

```python
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
```
```output
first run applied:  ['0001_create_compounds.sql', '0002_create_measurements.sql', '0003_add_pchembl.sql']
second run applied: []
schema version: 3
```

The second run changes nothing, so the same command is safe to run every time the pipeline
starts. A new change is a new file with the next number; it is the only one applied:

```python
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
```
```output
applied: ['0004_index_measurements_by_compound.sql']
measurements: ['measurement_id', 'compound_id', 'target_id', 'value_nm', 'pchembl']
```

An applied migration is never edited: other copies of the database (a colleague's, the
production server's) have already run the old text, and editing it would leave them different
with no record of how. The hash in `schema_migrations` catches it:

```python
first = migrations / "0001_create_compounds.sql"
first.write_text(FIRST_MIGRATIONS["0001_create_compounds.sql"].replace(
    "inchikey TEXT NOT NULL", "inchikey TEXT"), encoding="utf-8", newline="\n")
try:
    migrate(db, migrations)
except RuntimeError as error:
    print("refused:", error)
first.write_text(FIRST_MIGRATIONS["0001_create_compounds.sql"], encoding="utf-8", newline="\n")
```
```output
refused: 0001_create_compounds.sql was changed after it was applied
```

To change a column that already exists, write a new migration that changes it.

## 4. Standardisation rules: a version and a hash

Module 7 wrote standardisation as a function driven by rules: which fragments to strip, whether
to neutralise, which tautomer to choose. Change a rule and the same input gives different
molecules, so the rules are versioned like code. A version string is for people; a **hash** of
the rules is for machines, and catches the change someone made without raising the version.

The hash must not depend on how the rules happen to be written down, so it is taken over a
canonical form: JSON with sorted keys and no spaces.

```python
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
```
```output
rules 2.1.0 hash ee10b28747d2965b
same rules written in another order, same hash: True
```

A pipeline keeps a register of the versions it has released and their hashes, and checks the
rules against it before it runs:

```python
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
```
```output
ok
rules changed but the version is still 2.1.0
version 2.2.0 was never released
```

## 5. Data: content hashes and a manifest

The same idea names data. A file's SHA-256 hash changes if any byte of the file changes, and two
files with the same hash have, for any practical purpose, the same contents. So "the data" in a
report becomes a list of files and their hashes: a **manifest**.

We write two data files from `chemlib`. Large files are hashed in chunks, so the whole file is
never in memory at once:

```python
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
```
```output
compounds.csv   402,818 bytes  sha256 6201fe7ddc7ec6b1...
prices.csv       18,772 bytes  sha256 f5dbfd2d533fab04...
```

The files are written with `\n` line endings on every system, so the bytes, and therefore the
hashes, are the same on Windows, macOS and Linux; the hashes you get should match these. (Write
a CSV with the system's own line endings and Windows gives different bytes and a different hash
for the same table.)

Checking data against its manifest finds any file that changed, went missing or appeared. Here
one price is corrected, the kind of edit nobody remembers making:

```python
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
```
```output
before: []
after:  ['changed: prices.csv']
old hash f5dbfd2d533fab04 new hash 59487a5df85bd55c
```

One cent in one row out of a thousand gives a completely different hash, which is what makes
hashes useful as names: there is no "nearly the same" hash to be fooled by. The manifest is small
and is committed with the code, so a commit says exactly which data the code expected.

### Large data: DVC

A manifest says what the data should be, but git cannot hold the data itself once it runs to
gigabytes, and plain hashes do not say where to fetch a file with a given hash. **DVC** (Data
Version Control) does both: it keeps the data in a cache and a shared store, outside git, and
commits to git only a small `.dvc` file holding the data's hash and size. Git then versions the
pointer, and DVC fetches the data the pointer names.

DVC is a command-line tool and works the same on Windows, macOS and Linux. We call it from Python
in a fresh git repository, in the same way as git:

```python
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
```
```output
outs:
- md5: 0a2710734954cb22e937671f0a9dad4d
  size: 402818
  hash: md5
  path: compounds.csv

git ignores the data itself: /compounds.csv
the md5 is the file's own: True
```

The `.dvc` file is all git sees: an MD5 hash (DVC's choice of hash) and a size. For the same
bytes it is the same on every computer. Now the data is pushed to a **remote**, the shared store
that the team (or the paper's readers) fetch from. Here the remote is a folder, so the lesson
needs no account anywhere:

```python
dvc(project, "remote", "add", "--default", "store", str((WORK / "dvc-store").resolve()))
dvc(project, "push")
(project / "data" / "compounds.csv").unlink()
remove_tree(project / ".dvc" / "cache")
dvc(project, "pull")
restored = file_sha256(project / "data" / "compounds.csv")
print("restored from the remote, same bytes:", restored == file_sha256(data / "compounds.csv"))
```
```output
restored from the remote, same bytes: True
```

In a real project the remote is cloud storage (Amazon S3, Google Cloud Storage, Azure), a server
over SSH, or a shared drive, set once with `dvc remote add` and committed in `.dvc/config`. For
publishing, the usual route is to archive the exact files of a release, with their manifest, in
a repository such as Zenodo, which gives them a DOI that the paper cites.

When the data changes, `dvc add` again gives a new hash, and the commit records it. Every earlier
version can come back: check out the old `.dvc` file with git, and `dvc checkout` puts the
matching data in place.

```python
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
```
```output
now:  c118af6987c871d874c832a0068486ab 4000 rows
back: 0a2710734954cb22e937671f0a9dad4d 5000 rows
```

## 6. Results: a provenance record next to every output

Everything so far gives each ingredient a version. The last step ties them to the result: every
output is written together with a small **provenance record** that names the code version, the
environment, the schema version, the rules and their hash, the hash of every input file, and the
parameters of the run. With it, a result can be traced to exactly what made it, and checked.

![A provenance record links one result file to everything that made it: the result's own hash, the code version from git, the Python and package versions, the schema version, the rules version and hash, the hash of each input file and the run's parameters; checking the record recomputes the hashes and compares](figures/provenance-record.svg)

The result here is a small one: the median price per vendor of the compounds with at least a
given amount in stock. The function that writes it writes the record beside it, with the same
name and `.provenance.json` on the end:

```python
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
```
```output
  vendor  median  count
Vendor A 269.930   1351
Vendor B 264.250   1373
Vendor C 247.425   1370
written: ['median-price.csv', 'median-price.csv.provenance.json']
```

The record is plain JSON, readable by people and by code. Its environment, code version and
time are those of your run, so yours will differ from this one:

```python
print(json.dumps(record, indent=2))
```
```output varies
{
  "result": {
    "file": "median-price.csv",
    "sha256": "d078fc3080aeffd7f35220c8d32b0a251cdfe40385646db73d89b50a3dd76e7c"
  },
  "code_version": "v1.0.0-1-g51a03c3",
  "environment": {
    "python": "3.11.17",
    "pandas": "3.1.1",
    "numpy": "2.4.6",
    "duckdb": "2.0.0",
    "dvc": "3.67.1"
  },
  "schema_version": 4,
  "rules": {
    "version": "2.1.0",
    "sha256": "ee10b28747d2965b882d3241b52e67b7fbfc3ae51d5d72e778320b3135064fa2"
  },
  "inputs": {
    "work/data/compounds.csv": "6201fe7ddc7ec6b125d068e53521102f30e1849c8245dd7727e5279c9cd253f2"
  },
  "parameters": {
    "min_stock_mg": 100
  },
  "created_utc": "2026-11-20T06:27:01+00:00"
}
```

The parts that come from the data, the rules and the parameters are the same on every computer:

```python
print("schema_version:", record["schema_version"])
print("rules:", record["rules"]["version"], record["rules"]["sha256"][:16] + "...")
for name, digest in record["inputs"].items():
    print("input:", name, digest[:16] + "...")
print("parameters:", record["parameters"])
print("result:", record["result"]["file"], record["result"]["sha256"][:16] + "...")
```
```output
schema_version: 4
rules: 2.1.0 ee10b28747d2965b...
input: work/data/compounds.csv 6201fe7ddc7ec6b1...
parameters: {'min_stock_mg': 100}
result: median-price.csv d078fc3080aeffd7...
```

Checking a result means reading its record, hashing the inputs and the rules as they are now,
and comparing. Rebuilding it means running the same code on the same inputs with the same
parameters, and comparing the result's hash:

```python
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
```
```output
check: []
rebuilt, same bytes: True
```

And when an input changes after the fact, the check says which:

```python
stock = pd.read_csv(data / "compounds.csv")
stock.loc[stock.index[:50], "stock_mg"] = 0  # 50 compounds sold out
stock.to_csv(data / "compounds.csv", index=False, lineterminator="\n")
print("check:", check_provenance(record_path))
db.close()
```
```output
check: ['input changed: work/data/compounds.csv']
```

The median price in `median-price.csv` is still right for the data it was made from, and the
record says which data that was; it is simply not the answer for today's data. Without the record
the two would look the same.

In practice the pipeline writes the record for every output, never a person by hand. Workflow
tools keep similar records: DVC's own pipelines, for one, write a `dvc.lock` file with the hash
of every stage's inputs and outputs. A run history (Module 14) can keep these records for every
run, and the capstone (Module 15) versions its output in the same way.

## Try it yourself

The homework for this module is in `homework.md`: a few questions answered by running code like the
code above. Answers are published after the cohort's deadline.

## Further reading

- Chacon, S. & Straub, B. *Pro Git*, 2nd edition. Apress. The free online book, in particular the
  chapters on tagging and on Git internals. <https://git-scm.com/book/en/v2>
- The uv documentation. *Structure and files*, the section on the lockfile.
  <https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile>
- The Docker documentation. *docker image pull*, including pulling an image by digest.
  <https://docs.docker.com/reference/cli/docker/image/pull/>
- The DVC documentation. *Get Started with DVC*: data versioning.
  <https://dvc.org/doc/start/data-management/data-versioning>
- Sandve, G. K., Nekrutenko, A., Taylor, J. & Hovig, E. (2013). Ten Simple Rules for Reproducible
  Computational Research. *PLoS Computational Biology*, 9(10), e1003285.
  <https://doi.org/10.1371/journal.pcbi.1003285>
- Wilkinson, M. D. et al. (2016). The FAIR Guiding Principles for scientific data management and
  stewardship. *Scientific Data*, 3(1), 160018. <https://doi.org/10.1038/sdata.2016.18>
