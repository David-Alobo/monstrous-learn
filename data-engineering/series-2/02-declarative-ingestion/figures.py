"""Draw the figures of Module 2 (figures/*.svg): a dlt load, and evolve or freeze in week 5.

Usage (from the series folder):
    uv run python 02-declarative-ingestion/figures.py

The SVGs are committed, so the course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for diagrams
from diagrams import GREEN, MUTED, RED, VIOLET, Diagram

OUT = Path(__file__).parent / "figures"


def dlt_load() -> Diagram:
    """The parts of a dlt load: resources, the three steps, the destination and the state."""
    d = Diagram(1000, 440)
    d.text(20, 30, "One dlt load: what you declare, and what dlt does", 16, weight="600")
    files = ["registry_…10-12", "assay_…09-14", "assay_…09-21", "assay_…09-21_resent",
             "assay_…09-28", "assay_…10-05", "assay_…10-12"]  # fmt: skip
    d.box(20, 70, 170, 230, "inbox", files, kind="raw")
    d.text(205, 66, "what you declare", 12, VIOLET, weight="600")
    d.box(215, 80, 180, 80, "registry resource", ["write: replace", "(each export is a snapshot)"],
          kind="tool", size=13)  # fmt: skip
    d.box(215, 190, 180, 110, "assay resource",
          ["incremental on file_name:", "only names > last_value", "write: merge on result_id"],
          kind="tool", size=13)  # fmt: skip
    d.arrow((190, 120), (215, 120))
    d.arrow((190, 245), (215, 245))
    d.text(430, 66, "what dlt does, on pipeline.run(...)", 12, VIOLET, weight="600")
    steps = [("extract", "call the resources"), ("normalize", "fit rows to schema"),
             ("load", "write the rows")]  # fmt: skip
    for k, (name, what) in enumerate(steps):
        x = 430 + k * 135
        d.box(x, 150, 115, 70, name, [what], kind="stage", size=13)
        if k:
            d.arrow((x - 20, 185), (x, 185))
    d.arrow((395, 185), (430, 185))
    d.box(510, 250, 190, 60, "schema", ["inferred from the data; evolves", "unless a contract says not"],
          kind="plain", size=13)  # fmt: skip
    d.arrow((620, 250), (620, 220), dashed=True)
    d.box(835, 140, 150, 90, "DuckDB: raw", ["registry, assay,", "_dlt_loads"], kind="mart")
    d.arrow((815, 185), (835, 185))
    d.box(835, 260, 150, 80, "state", ["last_value =", "assay_…10-12.csv"], kind="plain", size=13)
    d.arrow((910, 260), (910, 230), dashed=True)
    d.text(918, 250, "kept in raw too", 11, MUTED)
    # the state tells the next run where to start: an arrow under everything, back to the resource
    d.line((910, 340), (910, 375), MUTED, 2, dashed=True)
    d.line((910, 375), (305, 375), MUTED, 2, dashed=True)
    d.arrow((305, 375), (305, 300), dashed=True)
    d.text(600, 368, "the next run reads only files after last_value", 12, MUTED, "middle")
    d.text(20, 420, "The resent file brings result_ids already in the table: merge keeps one row "
           "for each, so nothing is counted twice.", 12, MUTED)  # fmt: skip
    return d


def contracts() -> Diagram:
    """Week 5's renamed column under the two schema contracts of section 4."""
    d = Diagram(900, 330)
    d.text(20, 30, "Week 5: the plate reader writes 'unit' instead of 'units', and adds 'operator'",
           16, weight="600")  # fmt: skip
    for row, (name, colour) in enumerate([("evolve", GREEN), ("freeze", RED)]):
        y = 70 + row * 130
        d.text(20, y + 40, f"contract: {name}", 14, colour, weight="600")
        for k, week in enumerate(range(2, 7)):
            x = 170 + k * 140
            if name == "evolve" or week < 5:
                kind, lines = "ok", ["loaded"]
            elif week == 5:
                kind, lines = "fail", ["stops at normalize", "'unit' not allowed"]
            else:
                kind, lines = "skip", ["waits for a decision"]
            if name == "evolve" and week == 5:
                lines = ["loaded: 'unit' and", "'operator' added"]
            d.box(x, y, 120, 70, f"week {week}", lines, kind=kind, size=13)
            if k:
                d.arrow((x - 20, y + 35), (x, y + 35))
    d.text(170, 175, "Nothing stops: raw holds 'units' for weeks 1-4 and 'unit' from week 5; staging "
           "joins them (coalesce).", 12, MUTED)  # fmt: skip
    d.text(170, 305, "abort_packages() puts the state back to week 4; a person decides; the next run "
           "allows the new columns once and loads weeks 5 and 6.", 12, MUTED)  # fmt: skip
    return d


if __name__ == "__main__":
    for name, figure in [("dlt-load", dlt_load), ("schema-contracts", contracts)]:
        figure().save(OUT / f"{name}.svg")
        print(f"wrote figures/{name}.svg")
