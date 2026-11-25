"""Continuous integration for data: the code of the lesson, in order.

Check every change to the warehouse's code before it reaches the warehouse. A CI script builds the project as it is on main and as it is on the branch, on the same test data, in warehouses of their own; runs every test; lists what the change touches; compares the two builds table by table; and writes a report. Run it on two pull requests, then hand it to GitHub Actions.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/09-continuous-integration/
Run it from anywhere, e.g. from the series folder: uv run python 09-continuous-integration/code.py
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
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

import labstack

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
REPO = WORK / "lab-repo"  # the lab's repository: the dbt project, ci.py and the workflow
BRANCHES = WORK / "branches"  # each pull request's version of the dbt project

shutil.rmtree(WORK, ignore_errors=True)  # start clean
labstack.dbt_project(REPO / "lab_dbt", after=6)


def write(path: Path, text: str) -> None:
    """Save a file (made, with its folders, if it is new)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8", newline="\n")

# ---- 2. The CI script ----
write(REPO / "ci.py", '''
"""Continuous integration for the lab's warehouse: build main and a branch, test, compare.

Usage: python ci.py --base MAIN_PROJECT --head BRANCH_PROJECT --out FOLDER
"""

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

import duckdb

import labdata
import labstack

WEEKS = 8  # how many weeks of the lab's synthetic test data to build on
QUIET = logging.getLogger("ci.dbt")  # one line per model: in dbt's own log, not the report
QUIET.propagate = False
RUN_SPECIFIC = {"load_id"}  # columns that differ between any two builds: left out of the diff


def build(project: Path, folder: Path) -> tuple[Path, list]:
    """Build a copy of a dbt project on the test data, in a warehouse of its own."""
    copy = shutil.copytree(project, folder / "lab_dbt",
                           ignore=shutil.ignore_patterns("target", "logs"))
    os.environ["LAB_WAREHOUSE"] = str((folder / "lab.duckdb").resolve())
    labstack.warehouse_at(labdata.Lab(), WEEKS, folder, project=copy, build=False)
    return copy, labstack.dbt(copy, "build", log=QUIET)


def changed(head: Path, base: Path) -> list[str]:
    """The models the head changes, and every model downstream of them."""
    state = str((base / "target").resolve())
    return sorted(labstack.dbt(head, "ls", "--select", "state:modified+", "--state", state,
                               "--resource-type", "model", "--output", "name"))


def diff(db: duckdb.DuckDBPyConnection, model: str) -> dict | None:
    """How a model differs between the base (attached as `base`) and the head.

    None if the model was not built on the branch (dbt skips models after a failed test).
    """
    def columns(database: str) -> list[str]:
        return [row[0] for row in db.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_catalog = ? AND table_name = ? ORDER BY ordinal_position",
            [database, model]).fetchall()]

    head_cols, base_cols = columns("lab"), columns("base")
    if not head_cols:
        return None
    schema = db.execute("SELECT table_schema FROM information_schema.tables "
                        "WHERE table_catalog = 'lab' AND table_name = ?", [model]).fetchall()[0][0]
    common = ", ".join(f'"{c}"' for c in head_cols
                       if c in base_cols and c not in RUN_SPECIFIC)
    head_table, base_table = f"lab.{schema}.{model}", f"base.{schema}.{model}"

    def count(sql: str) -> int:
        return db.execute(f"SELECT count(*) FROM ({sql})").fetchall()[0][0]

    return {
        "rows on main": count(f"SELECT * FROM {base_table}"),
        "rows on branch": count(f"SELECT * FROM {head_table}"),
        "rows that differ": count(f"SELECT {common} FROM {head_table} EXCEPT ALL "
                                  f"SELECT {common} FROM {base_table}"),
        "columns added": [c for c in head_cols if c not in base_cols],
        "columns removed": [c for c in base_cols if c not in head_cols],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--head", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    shutil.rmtree(args.out, ignore_errors=True)
    base, _ = build(args.base, args.out / "base")
    head, results = build(args.head, args.out / "head")

    failed = sorted(r.node.name for r in results if str(r.status) in ("fail", "error"))
    passed = sum(str(r.status) == "pass" for r in results)
    lines = ["## Warehouse CI", "",
             f"**{'FAILED' if failed else 'Passed'}**: {passed} tests passed, "
             f"{len(failed)} failed.", ""]
    lines += [f"- failed: `{name}`" for name in failed]
    touched = changed(head, base)
    lines += ["", "### Models this change touches", ""]
    lines += [f"- `{model}`" for model in touched] or ["- none"]
    with duckdb.connect(os.environ["LAB_WAREHOUSE"]) as db:
        db.execute(f"ATTACH '{(args.out / 'base' / 'lab.duckdb').resolve()}' AS base (READ_ONLY)")
        lines += ["", "### How their contents differ from main", "",
                  "| model | rows on main | rows on branch | rows that differ | columns added "
                  "| columns removed |", "|---|---|---|---|---|---|"]
        for model in touched:
            d = diff(db, model)
            if d is None:
                lines.append(f"| `{model}` | not built on the branch (skipped) | | | | |")
                continue
            lines.append(f"| `{model}` | {d['rows on main']} | {d['rows on branch']} | "
                         f"{d['rows that differ']} | {', '.join(d['columns added']) or '-'} | "
                         f"{', '.join(d['columns removed']) or '-'} |")
    report = "\\n".join(lines) + "\\n"
    (args.out / "report.md").write_text(report, encoding="utf-8")
    print(report)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
''')

# ---- 3. Two pull requests ----
def pull_request(name: str, model: str, old: str, new: str) -> Path:
    """A branch: a copy of main's dbt project with one passage of one model changed."""
    project = shutil.copytree(REPO / "lab_dbt", BRANCHES / name / "lab_dbt")
    path = project / model
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{model}: the passage to change is not there exactly once"
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    return project


def run_ci(head: Path, name: str) -> int:
    """Run ci.py on a branch, as a CI service would, and show its report."""
    folders = [os.getcwd(), *(p for p in sys.path if p)]  # here, and where Python looks
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(folders)}
    done = subprocess.run(
        [sys.executable, str(REPO / "ci.py"), "--base", str(REPO / "lab_dbt"),
         "--head", str(head), "--out", str(WORK / "ci" / name)],
        env=env, capture_output=True, text=True, encoding="utf-8",
    )
    print(done.stdout)
    log.info("ci.py ended with exit code %d", done.returncode)
    return done.returncode
tpsa = pull_request(
    "add-tpsa", "models/marts/dim_compound.py",
    '    compounds["heavy_atoms"] = [m.GetNumHeavyAtoms() for m in mols]\n',
    '    compounds["heavy_atoms"] = [m.GetNumHeavyAtoms() for m in mols]\n'
    '    compounds["tpsa"] = [round(Descriptors.TPSA(m), 1) for m in mols]\n',
)
exit_code = run_ci(tpsa, "add-tpsa")

# ---- How their contents differ from main ----
rounded = pull_request(
    "round-pic50", "models/staging/stg_results.sql",
    "       9 - log10(value * u.factor)   as pic50,\n",
    "       round(9 - log10(value * u.factor), 2) as pic50,\n",
)
exit_code = run_ci(rounded, "round-pic50")

# ---- 4. In GitHub Actions ----
write(REPO / ".github" / "workflows" / "warehouse-ci.yml", """
name: warehouse-ci
on:
  pull_request:
    paths: ["lab_dbt/**", "ci.py"]  # only changes to the warehouse's code
jobs:
  build-and-compare:
    runs-on: ubuntu-latest
    steps:
      - name: Fetch the branch, and main's history
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Put main's version of the code next to the branch's
        run: git worktree add ../main origin/main
      - name: Install uv
        uses: astral-sh/setup-uv@v6
      - name: Install the lab's packages, as locked
        run: uv sync --locked
      - name: Build main and the branch on the test data, test and compare
        run: uv run python ci.py --base ../main/lab_dbt --head lab_dbt --out ci-out
      - name: Show the report on the run's page
        if: always()
        run: cat ci-out/report.md >> "$GITHUB_STEP_SUMMARY"
      - name: Keep the report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: warehouse-ci-report
          path: ci-out/report.md
""")
workflow = yaml.safe_load((REPO / ".github" / "workflows" / "warehouse-ci.yml")
                          .read_text(encoding="utf-8"))
print("keys:", list(workflow))
for step in workflow["jobs"]["build-and-compare"]["steps"]:
    print("-", step["name"])
