"""Draw the figure of Module 11 (figures/stack.svg): the whole data stack, and where each part comes from.

Usage (from the series folder):
    uv run python 11-capstone/figures.py

The parts are those of stack.py, dashboard.py and Module 9's CI. The SVG is committed, so the
course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for diagrams
from diagrams import CYAN, MUTED, ORANGE, Diagram

OUT = Path(__file__).parent / "figures"


def stack() -> Diagram:
    """The stack: the weekly flow from files to dashboard, with CI and the record around it."""
    d = Diagram(1040, 520)
    d.text(20, 30, "The lab's data stack, and the module each part comes from", 16, weight="600")
    # the weekly flow, inside a Prefect frame
    d.parts.append(f'<rect x="150" y="60" width="700" height="250" rx="14" fill="none" '
                   f'stroke="{CYAN}" stroke-width="2" stroke-dasharray="7 4"/>')  # fmt: skip
    d.text(165, 82, "Prefect: the weekly flow, retries, the record of every run (M7)", 12, CYAN,
           weight="600")  # fmt: skip
    d.box(20, 140, 110, 80, "lab's files", ["registry,", "assay results"], kind="raw", size=13)
    d.box(170, 140, 120, 80, "dlt (M2)", ["incremental", "load"], kind="tool", size=13)
    d.box(320, 100, 230, 170, "DuckDB warehouse (M1, M3)", [
        "raw: as loaded", "snapshots: history (M6)", "staging and marts:",
        "dbt models (M4)", "tests, contracts (M5)", "monitoring: metrics,", "alerts (M8)",
    ], kind="stage", size=13)  # fmt: skip
    d.box(580, 100, 120, 80, "checks (M8)", ["freshness, volume,", "schema, drift"], kind="tool",
          size=13)  # fmt: skip
    d.box(580, 200, 120, 80, "chemistry (M5)", ["pandera-chem"], kind="tool", size=13)
    d.box(730, 140, 105, 80, "publish (M10)", ["a read-only", "copy"], kind="tool", size=13)
    d.arrow((130, 180), (170, 180))
    d.arrow((290, 180), (320, 180))
    d.arrow((550, 140), (580, 140))
    d.arrow((550, 240), (580, 240))
    d.arrow((700, 180), (730, 180))
    # readers and alerts
    d.box(890, 120, 130, 70, "dashboard (M10)", ["Streamlit"], kind="mart", size=13)
    d.box(890, 220, 130, 70, "chemists", ["their questions,", "answered"], kind="plain", size=13)
    d.arrow((835, 170), (890, 155))
    d.arrow((955, 190), (955, 220))
    d.box(560, 330, 160, 60, "alerts", ["kept, and sent to a chat"], kind="warn", size=13)
    d.arrow((640, 280), (640, 330), colour=ORANGE)
    d.text(650, 298, "from the checks", 11, ORANGE)
    # around the flow: CI and hand-over
    d.box(150, 350, 360, 70, "CI on every pull request (M9)", [
        "builds main and the branch on test data, tests, diffs"], kind="tool", size=13)  # fmt: skip
    d.arrow((330, 350), (400, 270), dashed=True)
    d.text(372, 340, "checks the dbt project", 11, MUTED)
    d.box(800, 330, 220, 90, "hand-over (M11)", ["dbt docs, a runbook,", "back up the snapshots"],
          kind="plain", size=13)  # fmt: skip
    d.text(20, 470, "Each week: files arrive, are loaded, snapshotted, built and tested, checked, "
           "and published; a failure at any step stops", 12, MUTED)  # fmt: skip
    d.text(20, 488, "the week before publishing, so the dashboard keeps the last good data. "
           "Code changes go through CI first.", 12, MUTED)  # fmt: skip
    return d


if __name__ == "__main__":
    stack().save(OUT / "stack.svg")
    print("wrote figures/stack.svg")
