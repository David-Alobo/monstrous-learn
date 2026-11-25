"""The checks every lesson in every series must pass, shared by the series' test files.

A series' test_lessons.py makes them for its own folder:

    globals().update(lessontests.tests_for(Path(__file__).parent))

Each lesson's code runs and prints exactly what the lesson shows, declares the packages it uses,
imports only in its Setup block, uses only figures that exist, ends with further reading, has
homework, and its notebook, script and README are up to date.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

# import names that differ from their pip package names (a series can add its own)
PIP_NAME = {
    "yaml": "pyyaml",
    "sklearn": "scikit-learn",
    "psycopg": "psycopg[binary]",
    "dotenv": "python-dotenv",
    "openbabel": "openbabel-wheel",
    "pydantic_settings": "pydantic-settings",
    "pandera_chem": "pandera-chem",
}
STDLIB = set(sys.stdlib_module_names)


def tests_for(series: Path, pip_name: dict[str, str] | None = None) -> dict[str, Callable]:
    """The lesson tests for one series, ready to put in its test module's namespace.

    Args:
        series: The series' folder (it holds the NN-… module folders and its lessonkit.py).
        pip_name: Extra import names that differ from their pip package names.

    Returns:
        Each test function by name, parametrised over the series' lessons.
    """
    import lessonkit  # the series' entry point, which loads shared/lessonkit.py

    lessons = sorted(series.glob("[0-9][0-9]-*/lesson.md"))
    ids = {"ids": lambda p: p.parent.name}
    local = {p.stem for p in series.glob("*.py")}  # the series' own helpers (e.g. chemlib)
    names = {**PIP_NAME, **(pip_name or {})}

    def run_fresh(lesson: Path) -> list:
        """Run a lesson in a fresh Python process, as a learner would, and return the results.

        Args:
            lesson: The lesson file.

        Returns:
            lessonkit's results for each python block.
        """
        code = "\n".join(
            [
                "import json, pathlib, lessonkit",
                f"p = pathlib.Path({str(lesson)!r})",
                "r = lessonkit.run(p.read_text(encoding='utf-8'), p.parent)",
                "pathlib.Path(p.parent, 'work').mkdir(exist_ok=True)",
                "out = pathlib.Path(p.parent, 'work', 'lessonkit-results.json')",
                "out.write_text(json.dumps(r))",
            ]
        )
        done = subprocess.run(
            [sys.executable, "-c", code], cwd=series, capture_output=True, text=True,
            encoding="utf-8",
        )  # fmt: skip
        assert done.returncode == 0, done.stderr[-3000:]
        results = lesson.parent / "work" / "lessonkit-results.json"
        return json.loads(results.read_text(encoding="utf-8"))

    @pytest.mark.parametrize("lesson", lessons, **ids)
    def test_every_output_is_what_the_code_prints(lesson):
        results = run_fresh(lesson)
        assert results, "a lesson without code"
        for k, (printed, shown, kind) in enumerate(results, start=1):
            if printed is None:
                continue  # needs a service that is not running here; CI runs it
            if kind == "output":
                assert printed == shown, f"python block {k}: rerun lessonkit.py --write"
            if kind == "":
                assert printed == "", f"python block {k} prints, but the lesson shows no output"

    @pytest.mark.parametrize("lesson", lessons, **ids)
    def test_declares_every_package_it_imports(lesson):
        meta, body = lessonkit.front_matter(lesson.read_text(encoding="utf-8"))
        declared = set(lessonkit.listed(meta, "requires"))
        own = {f.stem for f in lesson.parent.glob("*.py")}  # the module's own files
        for kind, code, _, _ in lessonkit.blocks(body):
            if kind != "python":
                continue
            for node in ast.walk(ast.parse(code)):
                found = []
                if isinstance(node, ast.Import):
                    found = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    found = [node.module]
                for name in found:
                    top = name.split(".")[0]
                    if top not in STDLIB and top not in local and top not in own:
                        assert names.get(top, top) in declared, (
                            f"{top} is imported but not in requires"
                        )

    @pytest.mark.parametrize("lesson", lessons, **ids)
    def test_figures_exist(lesson):
        for src in re.findall(r"!\[[^\]]+\]\(([^)]+)\)", lesson.read_text(encoding="utf-8")):
            assert (lesson.parent / src).exists(), src

    @pytest.mark.parametrize("lesson", lessons, **ids)
    def test_further_reading(lesson):
        text = lesson.read_text(encoding="utf-8")
        assert "\n## Further reading\n" in text
        items = re.findall(r"^- .+", text.split("\n## Further reading\n", 1)[1], re.M)
        assert len(items) >= 3, "at least three items of further reading"

    @pytest.mark.parametrize("lesson", lessons, **ids)
    def test_homework_exists(lesson):
        assert (lesson.parent / "homework.md").exists()

    @pytest.mark.parametrize("lesson", lessons, **ids)
    def test_notebook_script_and_readme_are_up_to_date(lesson):
        for path, content in lessonkit.export(lesson.parent).items():
            assert path.exists() and path.read_text(encoding="utf-8") == content, (
                f"{path.name} is out of date: run lessonkit.py {lesson.parent.name} --export"
            )

    @pytest.mark.parametrize("lesson", lessons, **ids)
    def test_imports_only_in_the_setup_block(lesson):
        """Every import sits in the Setup block, so the lesson's dependencies are in one place."""
        _, body = lessonkit.front_matter(lesson.read_text(encoding="utf-8"))
        assert "\n## Setup\n" in body, "a lesson starts with a Setup section"
        code = [c for kind, c, _, _ in lessonkit.blocks(body) if kind == "python"]
        for k, block in enumerate(code[1:], start=2):
            for node in ast.walk(ast.parse(block)):
                assert not isinstance(node, ast.Import | ast.ImportFrom), (
                    f"python block {k} imports {ast.unparse(node)!r}: move it to the Setup block"
                )

    return {name: f for name, f in locals().items() if name.startswith("test_")}
