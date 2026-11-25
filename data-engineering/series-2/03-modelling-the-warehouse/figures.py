"""Draw the figure of Module 3 (figures/lab-star.svg): the lab's star schema.

Usage (from the series folder):
    uv run python 03-modelling-the-warehouse/figures.py

The tables and columns are the ones the lesson creates (a selection of dim_compound's columns).
The SVG is committed, so the course site builds without running anything.
"""

from __future__ import annotations

from pathlib import Path

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


def main() -> None:
    """Write the figure."""
    OUT.mkdir(exist_ok=True)
    (OUT / "lab-star.svg").write_text(lab_star(), encoding="utf-8")


if __name__ == "__main__":
    main()
