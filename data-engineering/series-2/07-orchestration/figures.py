"""Draw the figure of Module 7 (figures/weekly-flow.svg): the lab's weekly flow in Prefect.

Usage (from the series folder):
    uv run python 07-orchestration/figures.py

The tasks, retries, cache and failure are those of the lesson. The SVG is committed, so the
course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for diagrams
from diagrams import CYAN, RED, VIOLET, Diagram

OUT = Path(__file__).parent / "figures"


def weekly_flow() -> Diagram:
    """The flow's tasks in order, with what Prefect adds around them."""
    d = Diagram(1000, 400)
    d.text(20, 30, "The weekly flow: tasks in order, and what Prefect adds", 16, weight="600")
    tasks = [("receive", ["the week's files", "retries=2"]), ("load", ["dlt: what is new"]),
             ("snapshot", ["dbt: registry", "history"]), ("build", ["dbt: build", "and test"]),
             ("check", ["pandera-chem:", "warns only"]), ("draw", ["new compounds", "cached"]),
             ("publish", ["Parquet for", "the dashboards"])]  # fmt: skip
    w, gap, y = 118, 22, 150
    for k, (name, lines) in enumerate(tasks):
        x = 20 + k * (w + gap)
        kind = {"receive": "tool", "draw": "tool", "publish": "mart"}.get(name, "stage")
        d.box(x, y, w, 70, name, lines, kind=kind, size=13)
        if k:
            d.arrow((x - gap, y + 35), (x, y + 35))
    # retry loop over receive
    d.arrow((50, 150), (108, 150), "", colour=CYAN, bend=-38)
    d.text(79, 108, "failed? wait 1 s, try again", 11, CYAN, "middle")
    d.text(79, 122, "(the share, week 9)", 11, CYAN, "middle")
    # cache on draw
    x_draw = 20 + 5 * (w + gap)
    d.text(x_draw + w / 2, 118, "same inputs as before?", 11, CYAN, "middle")
    d.text(x_draw + w / 2, 132, "return the cached result", 11, CYAN, "middle")
    # failure at build
    x_build = 20 + 3 * (w + gap)
    d.line((x_build + w / 2, y + 70), (x_build + w / 2, 268), RED, 2)
    d.dot(x_build + w / 2, 276, 9, RED, "!")
    d.text(
        x_build + w / 2 + 16, 272, "a test fails or a model breaks: the flow stops here,", 12, RED
    )
    d.text(x_build + w / 2 + 16, 289, "so check, draw and publish do not run, and the", 12, RED)
    d.text(x_build + w / 2 + 16, 306, "dashboards keep last week's good data", 12, RED)
    # the record
    d.box(20, 330, 960, 50, "Prefect's record", [("every flow run and task run: its state, attempts, "
          "logs and times (week 9, week 10, ... week 12 failed, week 12 rerun)")], kind="plain",
          size=13)  # fmt: skip
    d.text(20, 70, "started on a schedule (cron 0 7 * * 1: 07:00 every Monday), or when files arrive",
           12, VIOLET)  # fmt: skip
    return d


if __name__ == "__main__":
    weekly_flow().save(OUT / "weekly-flow.svg")
    print("wrote figures/weekly-flow.svg")
