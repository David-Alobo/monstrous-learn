"""Every lesson in this series: its code runs, prints exactly what the lesson shows, declares the
packages it uses, uses only figures that exist, ends with further reading, and its notebook, script
and README are up to date."""

import ast
import re
import sys
from pathlib import Path

import pytest

import lessonkit

HERE = Path(__file__).parent
LESSONS = sorted(HERE.glob("[0-9][0-9]-*/lesson.md"))
ids = {"ids": lambda p: p.parent.name}
# import names that differ from their pip package names
PIP_NAME = {
    "yaml": "pyyaml",
    "sklearn": "scikit-learn",
    "psycopg": "psycopg[binary]",
    "openbabel": "openbabel-wheel",
    "pydantic_settings": "pydantic-settings",
}
# modules that come with this repository rather than from pip
LOCAL = {p.stem for p in HERE.glob("*.py")}
STDLIB = set(sys.stdlib_module_names)


@pytest.mark.parametrize("lesson", LESSONS, **ids)
def test_every_output_is_what_the_code_prints(lesson):
    results = lessonkit.run(lesson.read_text(encoding="utf-8"), lesson.parent)
    assert results, "a lesson without code"
    for k, (printed, shown, kind) in enumerate(results, start=1):
        if printed is None:
            continue  # needs a service that is not running here; CI runs it
        if kind == "output":
            assert printed == shown, f"python block {k}: rerun lessonkit.py --write"
        if kind == "":
            assert printed == "", f"python block {k} prints, but the lesson shows no output"


@pytest.mark.parametrize("lesson", LESSONS, **ids)
def test_declares_every_package_it_imports(lesson):
    meta, body = lessonkit.front_matter(lesson.read_text(encoding="utf-8"))
    declared = set(lessonkit.listed(meta, "requires"))
    for kind, code, _, _ in lessonkit.blocks(body):
        if kind != "python":
            continue
        for node in ast.walk(ast.parse(code)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module]
            for name in names:
                top = name.split(".")[0]
                own = {f.stem for f in lesson.parent.glob("*.py")}  # the module's own files
                if top not in STDLIB and top not in LOCAL and top not in own:
                    assert PIP_NAME.get(top, top) in declared, (
                        f"{top} is imported but not in requires"
                    )


@pytest.mark.parametrize("lesson", LESSONS, **ids)
def test_figures_exist(lesson):
    for src in re.findall(r"!\[[^\]]+\]\(([^)]+)\)", lesson.read_text(encoding="utf-8")):
        assert (lesson.parent / src).exists(), src


@pytest.mark.parametrize("lesson", LESSONS, **ids)
def test_further_reading(lesson):
    text = lesson.read_text(encoding="utf-8")
    assert "\n## Further reading\n" in text
    items = re.findall(r"^- .+", text.split("\n## Further reading\n", 1)[1], re.M)
    assert len(items) >= 3, "at least three items of further reading"


@pytest.mark.parametrize("lesson", LESSONS, **ids)
def test_homework_exists(lesson):
    assert (lesson.parent / "homework.md").exists()


@pytest.mark.parametrize("lesson", LESSONS, **ids)
def test_notebook_script_and_readme_are_up_to_date(lesson):
    for path, content in lessonkit.export(lesson.parent).items():
        assert path.exists() and path.read_text(encoding="utf-8") == content, (
            f"{path.name} is out of date: run lessonkit.py {lesson.parent.name} --export"
        )
