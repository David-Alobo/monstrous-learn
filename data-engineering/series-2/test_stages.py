"""The saved dbt projects (stages/) must match what Modules 4 to 6 build in their lessons."""

from __future__ import annotations

import pytest

import make_stages


@pytest.mark.parametrize("module", sorted(make_stages.MODULES))
def test_saved_project_matches_the_lesson(module: int) -> None:
    """A module's finished project, rebuilt now, is the one later modules start from."""
    folder = make_stages.SERIES / make_stages.MODULES[module]
    if not (folder / "code.py").exists():
        pytest.skip(f"Module {module} is not written yet")
    saved = make_stages.SERIES / "stages" / f"after-{module:02d}" / "lab_dbt"
    built = make_stages.project_files(make_stages.build(module))
    assert make_stages.project_files(saved) == built, (
        f"stages/after-{module:02d} is out of date: run `uv run python make_stages.py {module}`"
    )
