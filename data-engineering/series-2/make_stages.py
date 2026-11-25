"""Save the lab's dbt project as each of Modules 4 to 6 leaves it, for the modules after it.

Modules 4, 5 and 6 build the dbt project step by step in their lessons (in work/lab_dbt). Each
later lesson starts from where the one before finished: labstack.dbt_project copies
stages/after-NN/lab_dbt. This script runs a module's code.py and copies its finished project
there (without dbt's own output: target/ and logs/). test_stages.py checks that the saved copies
still match what the lessons build.

Usage (from the series folder):
    uv run python make_stages.py 4 5 6
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SERIES = Path(__file__).parent
MODULES = {
    4: "04-transformations-with-lineage",
    5: "05-tests-and-contracts",
    6: "06-history-and-corrections",
}
SKIP = {"target", "logs", "dbt_packages", "__pycache__"}  # made by dbt or Python, not by us


def project_files(project: Path) -> dict[str, str]:
    """A dbt project's own files (not dbt's output), by path relative to the project.

    Args:
        project: The project's folder.

    Returns:
        Each file's text.
    """
    return {
        path.relative_to(project).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(project.rglob("*"))
        if path.is_file() and not SKIP & set(path.relative_to(project).parts)
    }


def build(module: int) -> Path:
    """Run a module's code.py, as a learner would, and return the project it built.

    Args:
        module: The module's number.

    Returns:
        The folder of the project it left in work/.
    """
    folder = SERIES / MODULES[module]
    subprocess.run([sys.executable, str(folder / "code.py")], check=True, capture_output=True)
    return folder / "work" / "lab_dbt"


def save(module: int) -> None:
    """Build a module's project and save it as stages/after-NN/lab_dbt.

    Args:
        module: The module's number.
    """
    dest = SERIES / "stages" / f"after-{module:02d}" / "lab_dbt"
    shutil.rmtree(dest, ignore_errors=True)
    for name, text in project_files(build(module)).items():
        (dest / name).parent.mkdir(parents=True, exist_ok=True)
        (dest / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"saved {dest.relative_to(SERIES)}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        save(int(arg))
