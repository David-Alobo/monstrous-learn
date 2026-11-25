"""Draw the figure of Module 3 (figures/lab-star.svg): the lab's star schema.

Usage (from the series folder, after running the lesson: the potency chart reads its warehouse):
    uv run python 03-modelling-the-warehouse/figures.py

Three figures: the lab's star schema (lab-star.svg), the grain (grain.svg) and the two averages of
section 6, by series (potency-means.svg).

The tables and columns are the ones the lesson creates (a selection of dim_compound's columns).
The SVG is committed, so the course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("svg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for diagrams
from diagrams import ORANGE, Diagram

# the course's colours (the same as Series 1's figurekit)
INK, VIOLET, CYAN, MUTED = "#1d2130", "#7c5cf0", "#0e9fb5", "#8b91a1"
OUT = Path(__file__).parent / "figures"
FONT = 'font-family="sans-serif"'
ROW, HEAD, WIDTH = 20, 28, 200  # a column's line, a table's title bar, a table's width

# (name, (left, top), colour, [(column, tag)]): tag is "PK", "FK" or ""
TABLES = [
    ("dim_compound", (30, 30), CYAN, [
        ("compound_key", "PK"), ("compound_id", ""), ("parent_smiles", ""), ("series", ""),
        ("chemist", ""), ("vendor", ""), ("registered_on", "FK"), ("mw, clogp, hbd, ...", "")]),
    ("fact_measurement", (350, 110), VIOLET, [
        ("result_id", "PK"), ("compound_key", "FK"), ("target_key", "FK"), ("run_date", "FK"),
        ("plate, replicate", ""), ("relation", ""), ("ic50_nm", ""), ("pic50", ""),
        ("source_file", "")]),
    ("dim_target", (670, 130), CYAN, [
        ("target_key", "PK"), ("target", ""), ("chembl_id", ""), ("role", "")]),
    ("dim_date", (30, 290), CYAN, [
        ("date_key", "PK"), ("project_week", ""), ("weekday", ""), ("month", "")]),
]  # fmt: skip


def _text(x: float, y: float, label: str, size: int = 13, colour: str = INK,
          anchor: str = "start", weight: str = "normal") -> str:  # fmt: skip
    """An SVG text element.

    Args:
        x: Horizontal position.
        y: Baseline position.
        label: The text.
        size: Font size in pixels.
        colour: Fill colour.
        anchor: SVG text-anchor.
        weight: SVG font-weight.

    Returns:
        The element.
    """
    return (f'<text x="{x}" y="{y}" {FONT} font-size="{size}" fill="{colour}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{label}</text>')  # fmt: skip


def _row_y(top: float, k: int) -> float:
    """The vertical centre of a table's k-th column line.

    Args:
        top: The table's top edge.
        k: The column's position, from 0.

    Returns:
        The y coordinate.
    """
    return top + HEAD + ROW * k + 10


def _table(name: str, left: float, top: float, colour: str, columns: list) -> str:
    """A table drawn as a box: its name in a coloured bar, then one line per column.

    Args:
        name: The table's name.
        left: Left edge.
        top: Top edge.
        colour: The colour of the title bar.
        columns: (column, tag) for each column.

    Returns:
        The SVG elements.
    """
    height = HEAD + ROW * len(columns) + 8
    parts = [
        (
            f'<rect x="{left}" y="{top}" width="{WIDTH}" height="{height}" rx="8" '
            f'fill="#ffffff" stroke="{colour}" stroke-width="2"/>'
        ),
        (
            f'<path d="M{left} {top + 8} a8 8 0 0 1 8 -8 h{WIDTH - 16} a8 8 0 0 1 8 8 '
            f'v{HEAD - 8} h-{WIDTH} z" fill="{colour}"/>'
        ),
        _text(left + 12, top + 19, name, 14, "#ffffff", weight="600"),
    ]
    for k, (column, tag) in enumerate(columns):
        y = _row_y(top, k) + 4
        if tag:
            parts.append(
                _text(left + 12, y, tag, 11, VIOLET if tag == "PK" else CYAN, weight="600")
            )
        parts.append(
            _text(left + 40, y, column, 13, INK, weight="600" if tag == "PK" else "normal")
        )
    return "".join(parts)


def _line(x1: float, y1: float, x2: float, y2: float, label: str = "") -> str:
    """A key-to-key line, with an optional label above its middle.

    Args:
        x1: Start, horizontal.
        y1: Start, vertical.
        x2: End, horizontal.
        y2: End, vertical.
        label: Text at the middle (the role a dimension plays).

    Returns:
        The SVG elements.
    """
    out = f'<path d="M{x1} {y1} C{(x1 + x2) / 2} {y1} {(x1 + x2) / 2} {y2} {x2} {y2}" fill="none" '
    out += f'stroke="{MUTED}" stroke-width="2"/>'
    if label:
        out += _text((x1 + x2) / 2, (y1 + y2) / 2 - 8, label, 12, MUTED, "middle")
    return out


def lab_star() -> str:
    """The lab's star: one fact table, three dimensions, and the date dimension in two roles."""
    w, h = 900, 450
    place = {name: (left, top) for name, (left, top), _, _ in TABLES}
    fx, fy = place["fact_measurement"]
    cx, cy = place["dim_compound"]
    tx, ty = place["dim_target"]
    dx, dy = place["dim_date"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        _line(cx + WIDTH, _row_y(cy, 0), fx, _row_y(fy, 1)),  # compound_key
        _line(tx, _row_y(ty, 0), fx + WIDTH, _row_y(fy, 2)),  # target_key
        _line(fx, _row_y(fy, 3), dx + WIDTH, _row_y(dy, 0)),  # run_date
        _text(dx + WIDTH + 14, _row_y(dy, 0) + 24, "run date", 12, MUTED),
        # registered_on: straight down from dim_compound to dim_date
        (
            f'<line x1="{cx + 150}" y1="{cy + HEAD + ROW * 8 + 8}" x2="{cx + 150}" y2="{dy}" '
            f'stroke="{MUTED}" stroke-width="2"/>'
        ),
        _text(cx + 158, (cy + HEAD + ROW * 8 + 8 + dy) / 2 + 4, "registered on", 12, MUTED),
    ]
    parts += [_table(name, left, top, colour, cols) for name, (left, top), colour, cols in TABLES]
    parts.append(_text(w / 2, h - 18, "Measurements in the middle; what was measured, on which "
                       "target and when, around it. dim_date plays two roles.", 12, MUTED,
                       "middle"))  # fmt: skip
    return "".join(parts) + "</svg>"


def grain() -> Diagram:
    """The grain: one row of the fact table for each well, and what a coarser grain loses."""
    d = Diagram(940, 330)
    d.text(20, 30, "The grain: one row per measurement, in one well of one plate", 16, weight="600")
    # a plate: 8 rows x 12 columns of wells; two wells hold LAB-0007 on EGFR (replicates 1 and 2)
    d.box(20, 60, 300, 210, "", [], kind="plain")
    d.text(170, 80, "plate P02-01", 13, anchor="middle", weight="600")
    for r in range(8):
        for c in range(12):
            x, y = 45 + c * 22, 100 + r * 20
            hit = r == 2 and c in (4, 5)
            d.parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{VIOLET if hit else "#ffffff"}" '
                           f'stroke="{VIOLET if hit else MUTED}" stroke-width="1.2"/>')  # fmt: skip
    d.text(170, 290, "LAB-0007 on EGFR, in duplicate: two wells", 12, MUTED, "middle")
    # the fact table's rows
    d.box(370, 60, 330, 120, "fact_measurement", [
        "R-00013 · LAB-0007 · EGFR · P02-01 · rep 1 · 842 nM",
        "R-00014 · LAB-0007 · EGFR · P02-01 · rep 2 · 703 nM",
        "one row per well: plate and replicate kept",
    ], kind="mart", size=13)  # fmt: skip
    d.arrow((320, 150), (370, 150))
    d.text(345, 140, "row", 11, MUTED, "middle")
    # a coarser grain
    d.box(370, 205, 330, 90, "one row per compound and target", [
        "LAB-0007 · EGFR · mean pIC50", "the plates are gone for good",
    ], kind="warn", size=13)  # fmt: skip
    d.arrow((535, 180), (535, 205))
    d.text(545, 197, "average the wells", 11, MUTED)
    d.text(725, 90, "Finest grain first:", 13, weight="600")
    for k, line in enumerate(["averages can always be made", "from the wells; the wells can",
                              "never be made from averages.", "", "Check it: the grain's columns",
                              "must name every row once."]):  # fmt: skip
        d.text(725, 112 + 20 * k, line, 12, MUTED)
    return d


def potency_means() -> None:
    """Section 6's two averages of EGFR potency, by series, from the lesson's warehouse."""
    with duckdb.connect(str(Path(__file__).parent / "work" / "lab.duckdb"), read_only=True) as db:
        rows = db.sql("""
            SELECT c.series, avg(f.ic50_nm) AS plain, 10 ** (9 - avg(f.pic50)) AS geometric
            FROM marts.fact_measurement AS f
            JOIN marts.dim_compound AS c USING (compound_key)
            JOIN marts.dim_target AS t USING (target_key)
            WHERE t.target = 'EGFR' AND f.relation = '=' AND c.series IS NOT NULL
            GROUP BY ALL ORDER BY geometric
        """).fetchall()
    series = [r[0] for r in rows]
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    xs = range(len(series))
    for offset, (k, label, colour) in zip((-0.2, 0.2), [(1, "plain mean of IC50", ORANGE),
                                                        (2, "geometric mean (from mean pIC50)",
                                                         VIOLET)]):  # fmt: skip
        values = [r[k] for r in rows]
        bars = ax.bar([x + offset for x in xs], values, width=0.38, color=colour, label=label)
        ax.bar_label(bars, labels=[f"{v:.0f} nM" for v in values], padding=3, fontsize=9)
    ax.set_xticks(list(xs), series)
    ax.set_ylabel("EGFR IC50 (nM)\nlower = more potent")
    ax.set_title("Two averages, two orders: the plain mean is pulled up by the weakest compounds",
                 fontsize=11, loc="left")  # fmt: skip
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper center", ncol=2)
    ax.set_ylim(0, max(r[1] for r in rows) * 1.35)
    fig.tight_layout()
    fig.savefig(OUT / "potency-means.svg")
    plt.close(fig)


def main() -> None:
    """Write the figures."""
    OUT.mkdir(exist_ok=True)
    (OUT / "lab-star.svg").write_text(lab_star(), encoding="utf-8")
    grain().save(OUT / "grain.svg")
    potency_means()


if __name__ == "__main__":
    main()
