"""Every lesson in this series: its code runs, prints exactly what the lesson shows, uses only
figures that exist, and ends with further reading."""

import re
from pathlib import Path

import pytest

import lessonkit

HERE = Path(__file__).parent
LESSONS = sorted(HERE.glob("[0-9][0-9]-*/lesson.md"))


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda p: p.parent.name)
def test_every_output_is_what_the_code_prints(lesson):
    results = lessonkit.run(lesson.read_text(encoding="utf-8"), lesson.parent)
    assert results, "a lesson without code"
    for k, (printed, shown) in enumerate(results, start=1):
        if shown is not None:
            assert printed == shown, f"python block {k}: rerun lessonkit.py --write"


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda p: p.parent.name)
def test_figures_exist(lesson):
    for src in re.findall(r"!\[[^\]]+\]\(([^)]+)\)", lesson.read_text(encoding="utf-8")):
        assert (lesson.parent / src).exists(), src


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda p: p.parent.name)
def test_further_reading(lesson):
    text = lesson.read_text(encoding="utf-8")
    assert "\n## Further reading\n" in text
    items = re.findall(r"^- .+", text.split("\n## Further reading\n", 1)[1], re.M)
    assert len(items) >= 3, "at least three items of further reading"
    assert all("<https://" in i or "https://" in text for i in items)


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda p: p.parent.name)
def test_homework_exists(lesson):
    assert (lesson.parent / "homework.md").exists()
