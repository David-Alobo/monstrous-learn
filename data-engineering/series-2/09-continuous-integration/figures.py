"""Draw the figure of Module 9 (figures/ci-flow.svg): what CI does with a pull request.

Usage (from the series folder):
    uv run python 09-continuous-integration/figures.py

The steps are those of the lesson's ci.py and workflow. The SVG is committed, so the course site
builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for diagrams
from diagrams import GREEN, MUTED, RED, Diagram

OUT = Path(__file__).parent / "figures"


def ci_flow() -> Diagram:
    """A pull request, the two builds on test data, the three answers and the merge gate."""
    d = Diagram(1000, 390)
    d.text(20, 30, "Continuous integration for the warehouse: every pull request, before merging",
           16, weight="600")  # fmt: skip
    d.box(20, 140, 150, 80, "pull request", ["a branch: the dbt", "project, changed"], kind="raw")
    d.box(230, 70, 190, 80, "build main (base)", ["on 8 weeks of test data,", "its own warehouse"],
          kind="stage", size=13)  # fmt: skip
    d.box(230, 210, 190, 80, "build the branch (head)", ["same test data,", "another warehouse"],
          kind="stage", size=13)  # fmt: skip
    d.arrow((170, 165), (230, 110))
    d.arrow((170, 195), (230, 250))
    answers = [("1. tests", ["do they all pass?"]),
               ("2. what it touches", ["state:modified+ against", "main's manifest"]),
               ("3. data diff", ["rows that differ,", "columns added/removed"])]  # fmt: skip
    for k, (name, lines) in enumerate(answers):
        y = 40 + k * 95
        d.box(490, y, 200, 75, name, lines, kind="tool", size=13)
        d.arrow((420, 180), (490, y + 37))
    d.box(760, 120, 220, 110, "report.md", ["on the run's page;", "exit code 1 if", "anything failed"],
          kind="mart", size=13)  # fmt: skip
    for k in range(3):
        d.arrow((690, 77 + k * 95), (760, 175))
    d.dot(775, 262, 9, GREEN)
    d.text(792, 267, "passed: a person reviews,", 12, GREEN)
    d.text(792, 283, "then merges", 12, GREEN)
    d.dot(775, 310, 9, RED)
    d.text(792, 315, "failed: branch protection", 12, RED)
    d.text(792, 331, "blocks the merge until fixed", 12, RED)
    d.text(20, 370, "Test data, not production: the two builds differ only by the change, and CI "
           "never needs the lab's real data or passwords.", 12, MUTED)  # fmt: skip
    return d


if __name__ == "__main__":
    ci_flow().save(OUT / "ci-flow.svg")
    print("wrote figures/ci-flow.svg")
