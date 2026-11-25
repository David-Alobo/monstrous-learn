"""Draw the figure of Module 5 (figures/build-week8.svg): a build in which a test fails.

Usage (from the series folder):
    uv run python 05-tests-and-contracts/figures.py

The models, tests and outcomes are those of section 5 of the lesson. The SVG is committed, so the
course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for diagrams
from diagrams import GREEN, MUTED, RED, Diagram

OUT = Path(__file__).parent / "figures"


def build_week8() -> Diagram:
    """Week 8's dbt build: every model is followed by its tests; a failed test skips what follows."""
    d = Diagram(980, 440)
    d.text(20, 30, "dbt build after weeks 7 and 8: a test fails, and dbt skips what is built from it",
           16, weight="600")  # fmt: skip
    w, h = 150, 52
    place = {
        "stg_compounds": (20, 80, "ok"), "stg_results": (20, 250, "ok"),
        "dim_compound": (280, 80, "ok"), "dim_target": (280, 180, "ok"), "dim_date": (540, 80, "ok"),
        "fact_measurement": (540, 250, "skip"), "measurements_wide": (800, 165, "skip"),
    }  # fmt: skip
    for name, (x, y, kind) in place.items():
        lines = ["built" if kind == "ok" else "skipped: not built"]
        d.box(x, y, w, h, name, lines, kind=kind, size=13)
    edges = [("stg_compounds", "dim_compound"), ("stg_results", "fact_measurement"),
             ("dim_compound", "fact_measurement"), ("dim_target", "fact_measurement"),
             ("fact_measurement", "measurements_wide"), ("dim_date", "measurements_wide")]  # fmt: skip
    for a, b in edges:
        (xa, ya, _), (xb, yb, _) = place[a], place[b]
        d.arrow((xa + w, ya + h / 2), (xb, yb + h / 2), colour=MUTED)
    # the tests that ran after each model: a row of badges under it
    tests = {
        "stg_compounds": [("unique", GREEN), ("not null", GREEN)],
        "stg_results": [("grain", RED), ("unique", GREEN), ("units", GREEN)],
        "dim_compound": [("keys", GREEN)],
        "fact_measurement": [("relationships", MUTED), ("pIC50", MUTED)],
    }
    for name, badges in tests.items():
        x, y, _ = place[name]
        bx = x
        for label, colour in badges:
            bw = 14 + 6.2 * len(label)  # wide enough for its label
            d.parts.append(f'<rect x="{bx}" y="{y + h + 6}" width="{bw}" height="18" rx="9" '
                           f'fill="{colour}"/>')  # fmt: skip
            d.text(bx + bw / 2, y + h + 19, label, 10, "#ffffff", "middle", "600")
            bx += bw + 5
    d.text(20, 350, "the grain test failed: plate P08-01", 12, RED, weight="600")
    d.text(20, 367, "was read twice, so 40 wells have two rows", 12, RED)
    d.text(540, 350, "Not built this week, so the marts keep", 12, MUTED)
    d.text(540, 367, "weeks 1-6: a week behind, but right.", 12, MUTED)
    for k, (colour, caption) in enumerate(
        [
            (GREEN, "test passed"),
            (RED, "test failed"),
            (MUTED, "test not run (its model was skipped)"),
        ]
    ):
        x = 20 + k * 160
        d.parts.append(f'<rect x="{x}" y="411" width="24" height="12" rx="6" fill="{colour}"/>')
        d.text(x + 32, 422, caption, 12, MUTED)
    return d


if __name__ == "__main__":
    build_week8().save(OUT / "build-week8.svg")
    print("wrote figures/build-week8.svg")
