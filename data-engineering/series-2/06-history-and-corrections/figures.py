"""Draw the figures of Module 6 (figures/*.svg): history types for LAB-0042, and incremental builds.

Usage (from the series folder):
    uv run python 06-history-and-corrections/figures.py

The structures, dates and counts are those of the lesson. The SVGs are committed, so the course
site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for diagrams and labdata
import labdata
from diagrams import GREEN, MUTED, ORANGE, VIOLET, Diagram

OUT = Path(__file__).parent / "figures"
WRONG = "O=C(Cc1ccc(O)cc1)Nc2ccc(C#N)nc2"  # LAB-0042 as registered until week 7
RIGHT = "O=C(Nc1ccc(O)cc1)Nc2ccc(C#N)nc2"  # and from week 7


def history_types() -> Diagram:
    """LAB-0042 in the warehouse over the weeks: overwritten (type 1) or versioned (type 2)."""
    d = Diagram(960, 400)
    d.text(20, 30, "LAB-0042's structure was corrected in week 7: what the warehouse keeps", 16,
           weight="600")  # fmt: skip
    left, col = 190, 62
    for week in range(1, 13):
        x = left + (week - 1) * col
        d.text(x + col / 2, 62, f"wk {week}", 11, MUTED, "middle")
    d.line((left + 6 * col, 70), (left + 6 * col, 272), ORANGE, 2, dashed=True)
    d.text(left + 6 * col + 6, 82, "correction arrives", 11, ORANGE)
    # type 1: one row, overwritten
    d.text(20, 125, "Type 1: overwrite", 14, weight="600")
    d.text(20, 143, "(dim_compound)", 12, MUTED)
    d.box(left + col, 100, 5 * col, 50, "wrong structure", [WRONG], kind="skip", size=12)
    d.box(left + 6 * col, 100, 6 * col, 50, "LAB-0042, now", [RIGHT], kind="mart", size=12)
    d.text(left + col, 172, "the old structure is gone, with no record of it",
           12, MUTED)  # fmt: skip
    # type 2: a row per version, with dates
    d.text(20, 235, "Type 2: add a version", 14, weight="600")
    d.text(20, 253, "(dim_compound_history)", 12, MUTED)
    d.box(left + col, 205, 5 * col, 62, "version 1", ["valid 14 Sep to 19 Oct", WRONG], kind="stage",
          size=12)  # fmt: skip
    d.box(left + 6 * col, 205, 6 * col, 62, "version 2 (current)", ["valid from 19 Oct", RIGHT],
          kind="mart", size=12)  # fmt: skip
    # the measurements, all made under version 1
    for week, target in [(3, "EGFR"), (4, "panel")]:
        x = left + (week - 1) * col + col / 2
        d.dot(x, 300, 9, GREEN)
        d.text(x, 322, target, 11, MUTED, "middle")
    d.text(left + 4 * col, 304, "every measurement of LAB-0042 was made under version 1: only "
           "type 2 can say so", 12, MUTED)  # fmt: skip
    d.text(20, 375, f"Registered in week 2 (exported {labdata.monday(2):%d %b}); measured on EGFR "
           "in week 3 and on the panel in week 4.", 12, MUTED)  # fmt: skip
    return d


def incremental() -> Diagram:
    """A full rebuild reads every load again; an incremental build reads only the new one."""
    d = Diagram(960, 300)
    d.text(20, 30, "Week 9's build of fact_measurement: full rebuild or incremental", 16,
           weight="600")  # fmt: skip
    for row, (name, colour, done) in enumerate([("full rebuild", MUTED, range(1, 10)),
                                                ("incremental", VIOLET, [9])]):  # fmt: skip
        y = 80 + row * 100
        d.text(20, y + 30, name, 14, weight="600")
        for k in range(1, 10):
            x = 170 + (k - 1) * 82
            kind = ("mart" if k in done else "skip") if name == "incremental" else "stage"
            d.box(x, y, 72, 48, f"load {k}", [f"week {k}"], kind=kind, size=12)
        what = ("reads and writes all 1,176 rows again" if name == "full rebuild"
                else "where load_id > max(load_id): reads 144 new rows, merges them")  # fmt: skip
        d.text(170, y + 70, what, 12, MUTED)
    d.text(20, 285, "A change to the model's SQL needs --full-refresh once, or old rows keep the old "
           "logic.", 12, MUTED)  # fmt: skip
    return d


if __name__ == "__main__":
    for name, figure in [("history-types", history_types), ("incremental", incremental)]:
        figure().save(OUT / f"{name}.svg")
        print(f"wrote figures/{name}.svg")
