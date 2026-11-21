"""Draw the figures of Module 4 (figures/*.svg): the lesson's data model and its star schema.

Usage (from the series folder):
    uv run python 04-databases-and-schemas/figures.py

Both diagrams show the tables the lesson creates, with the same names and columns. The SVGs are
committed, so the course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for figurekit
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

OUT = Path(__file__).parent / "figures"
FONT = 'font-family="sans-serif"'
ROW = 20  # height of one column's line in a table box
HEAD = 28  # height of a table box's title bar
WIDTH = 190  # width of a table box

# the lesson's normalised tables: (name, [(column, is_primary_key, is_foreign_key)])
MODEL = {
    "supplier": [("supplier_id", True, False), ("name", False, False), ("country", False, False)],
    "compound": [("compound_id", True, False), ("inchikey", False, False), ("smiles", False, False),
                 ("mw", False, False), ("source", False, False), ("loaded_on", False, False)],
    "batch": [("batch_id", True, False), ("compound_id", False, True), ("supplier_id", False, True),
              ("price_usd", False, False), ("amount_mg", False, False)],
    "target": [("target_id", True, False), ("name", False, False), ("organism", False, False)],
    "measurement": [("measurement_id", True, False), ("batch_id", False, True),
                    ("target_id", False, True), ("ic50_nm", False, False),
                    ("measured_on", False, False)],
}  # fmt: skip


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


def _table(x: float, y: float, name: str, columns: list[tuple[str, bool, bool]],
           colour: str = VIOLET) -> tuple[str, float]:  # fmt: skip
    """A table drawn as a box: its name in a coloured bar, then one line per column.

    Args:
        x: Left edge.
        y: Top edge.
        name: The table's name.
        columns: (column, primary key?, foreign key?) for each column.
        colour: The colour of the title bar.

    Returns:
        The SVG elements, and the box's height.
    """
    height = HEAD + ROW * len(columns) + 8
    parts = [
        f'<rect x="{x}" y="{y}" width="{WIDTH}" height="{height}" rx="8" fill="#ffffff" '
        f'stroke="{colour}" stroke-width="2"/>',
        f'<path d="M{x} {y + 8} a8 8 0 0 1 8 -8 h{WIDTH - 16} a8 8 0 0 1 8 8 v{HEAD - 8} '
        f'h-{WIDTH} z" fill="{colour}"/>',
        _text(x + 12, y + 19, name, 14, "#ffffff", weight="600"),
    ]
    for k, (column, primary, foreign) in enumerate(columns):
        cy = y + HEAD + ROW * (k + 1) - 4
        tag = "PK" if primary else ("FK" if foreign else "")
        if tag:
            parts.append(_text(x + 12, cy, tag, 11, colour if primary else CYAN, weight="600"))
        parts.append(_text(x + 40, cy, column, 13, INK, weight="600" if primary else "normal"))
    return "".join(parts), height


def _link(x1: float, y1: float, x2: float, y2: float, one_label: str, many_label: str) -> str:
    """A relationship line from the "one" side (x1, y1) to the "many" side (x2, y2), labelled.

    Args:
        x1: Horizontal position of the "one" end.
        y1: Vertical position of the "one" end.
        x2: Horizontal position of the "many" end.
        y2: Vertical position of the "many" end.
        one_label: Text at the "one" end.
        many_label: Text at the "many" end.

    Returns:
        The SVG elements.
    """
    dx = 1 if x2 > x1 else -1
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="2"/>'
        + _text(x1 + 6 * dx, y1 - 6, one_label, 12, MUTED, "start" if dx > 0 else "end")
        + _text(x2 - 6 * dx, y2 - 6, many_label, 12, MUTED, "end" if dx > 0 else "start")
    )


def er_diagram() -> str:
    """The lesson's normalised model: five tables, their keys and how they link."""
    w, h = 900, 440
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" '
             f'height="{h}">', f'<rect width="{w}" height="{h}" fill="#ffffff"/>']  # fmt: skip
    place = {"compound": (20, 40), "supplier": (20, 300), "batch": (355, 150),
             "target": (690, 300), "measurement": (690, 40)}  # fmt: skip
    for name, (x, y) in place.items():
        svg, _ = _table(x, y, name, MODEL[name])
        parts.append(svg)
    # compound_id and supplier_id in batch; batch_id and target_id in measurement (row centres)
    row_y = lambda name, k: place[name][1] + HEAD + ROW * k + 6  # noqa: E731
    parts.append(_link(20 + WIDTH, row_y("compound", 0), 355, row_y("batch", 1), "1", "many"))
    parts.append(_link(20 + WIDTH, row_y("supplier", 0), 355, row_y("batch", 2), "1", "many"))
    parts.append(_link(355 + WIDTH, row_y("batch", 0), 690, row_y("measurement", 1), "1", "many"))
    # target to measurement: straight up from the target box to the measurement box
    tx = 690 + WIDTH / 2
    target_top = place["target"][1]
    measurement_bottom = place["measurement"][1] + HEAD + ROW * len(MODEL["measurement"]) + 8
    parts.append(f'<line x1="{tx}" y1="{target_top}" x2="{tx}" y2="{measurement_bottom}" '
                 f'stroke="{MUTED}" stroke-width="2"/>')  # fmt: skip
    parts.append(_text(tx + 8, target_top - 8, "1", 12, MUTED))
    parts.append(_text(tx + 8, measurement_bottom + 18, "many", 12, MUTED))
    # the key, in three pieces (SVG collapses runs of spaces)
    for x, label in [(20, "PK  primary key: identifies the row"),
                     (300, "FK  foreign key: points to another table's row"),
                     (640, "1 ... many: one row here, many there")]:  # fmt: skip
        parts.append(_text(x, h - 22, label, 12, MUTED))
    return "".join(parts) + "</svg>"


def star_schema() -> str:
    """The star schema of section 6: one fact table and four dimension tables around it."""
    w, h = 900, 520
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" '
             f'height="{h}">', f'<rect width="{w}" height="{h}" fill="#ffffff"/>']  # fmt: skip
    fact = [("measurement_id", True, False), ("compound_id", False, True),
            ("supplier_id", False, True), ("target_id", False, True), ("date_key", False, True),
            ("pic50", False, False), ("price_usd", False, False)]  # fmt: skip
    dims = {
        "dim_compound": ((40, 30), [("compound_id", True, False), ("inchikey", False, False),
                                    ("smiles", False, False), ("mw", False, False),
                                    ("mw_band", False, False)]),
        "dim_supplier": ((670, 30), [("supplier_id", True, False), ("supplier", False, False),
                                     ("country", False, False)]),
        "dim_target": ((40, 330), [("target_id", True, False), ("target", False, False),
                                   ("organism", False, False)]),
        "dim_date": ((670, 330), [("date_key", True, False), ("year", False, False),
                                  ("quarter", False, False)]),
    }  # fmt: skip
    fx, fy = 355, 160
    for (x, y), _ in dims.values():
        cx = x + WIDTH / 2
        cy = y + 60
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{fx + WIDTH / 2}" y2="{fy + 90}" '
                     f'stroke="{MUTED}" stroke-width="2"/>')  # fmt: skip
    for name, ((x, y), columns) in dims.items():
        svg, _ = _table(x, y, name, columns, CYAN)
        parts.append(svg)
    svg, _ = _table(fx, fy, "fact_measurement", fact, VIOLET)
    parts.append(svg)
    parts.append(_text(w / 2, h - 22, "The fact table holds the numbers and a key to each "
                       "dimension; each dimension describes one who, what or when.", 12, MUTED,
                       "middle"))  # fmt: skip
    return "".join(parts) + "</svg>"


def main() -> None:
    """Write both figures."""
    OUT.mkdir(exist_ok=True)
    (OUT / "er-diagram.svg").write_text(er_diagram(), encoding="utf-8")
    (OUT / "star-schema.svg").write_text(star_schema(), encoding="utf-8")


if __name__ == "__main__":
    main()
