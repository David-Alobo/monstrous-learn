"""Draw the figure of Module 4 (figures/lineage.svg): the lineage of the lab's dbt project.

Usage (from the series folder):
    uv run python 04-transformations-with-lineage/figures.py

The nodes and edges are the ones the lesson's manifest lists (section 5): sources and seeds on the
left, then staging, the dimensions, the fact table and the wide view. The SVG is committed, so the
course site builds without running anything.
"""

from __future__ import annotations

from pathlib import Path

# the course's colours (the same as Series 1's figurekit)
INK, VIOLET, CYAN, MUTED = "#1d2130", "#7c5cf0", "#0e9fb5", "#8b91a1"
OUT = Path(__file__).parent / "figures"
FONT = 'font-family="sans-serif"'
BOX_W, BOX_H = 150, 36

# each node: (column, row, kind); kinds: source, seed, staging, mart
NODES = {
    "registry": (0, 0, "source"), "assay": (0, 1, "source"),
    "unit_to_nm": (0, 2, "seed"), "targets": (0, 3, "seed"),
    "stg_compounds": (1, 0, "staging"), "stg_results": (1, 1.5, "staging"),
    "dim_compound": (2, 0, "mart"), "dim_target": (2, 3, "mart"), "dim_date": (2, 4.2, "mart"),
    "fact_measurement": (3, 1.5, "mart"), "measurements_wide": (4, 2.6, "mart"),
}  # fmt: skip
# parent -> child, as in the manifest
EDGES = [
    ("registry", "stg_compounds"), ("assay", "stg_results"), ("unit_to_nm", "stg_results"),
    ("stg_compounds", "dim_compound"), ("targets", "dim_target"),
    ("stg_results", "fact_measurement"), ("dim_compound", "fact_measurement"),
    ("dim_target", "fact_measurement"), ("fact_measurement", "measurements_wide"),
    ("dim_compound", "measurements_wide"), ("dim_target", "measurements_wide"),
    ("dim_date", "measurements_wide"),
]  # fmt: skip
STYLE = {  # kind: (fill, stroke, text colour, caption)
    "source": ("#ffffff", MUTED, INK, "source (loaded by dlt)"),
    "seed": ("#ffffff", CYAN, INK, "seed (a CSV in the project)"),
    "staging": ("#efeafd", VIOLET, INK, "staging model (view)"),
    "mart": (VIOLET, VIOLET, "#ffffff", "mart model"),
}
LEFT, TOP, COL, ROW = 20, 30, 182, 62


def _xy(name: str) -> tuple[float, float]:
    """The top-left corner of a node's box.

    Args:
        name: The node.

    Returns:
        (x, y).
    """
    col, row, _ = NODES[name]
    return LEFT + col * COL, TOP + row * ROW


def lineage() -> str:
    """The lineage graph, left to right."""
    w, h = LEFT * 2 + 4 * COL + BOX_W, TOP + 5.2 * ROW + 60
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]
    for parent, child in EDGES:
        (x1, y1), (x2, y2) = _xy(parent), _xy(child)
        x1, y1, y2 = x1 + BOX_W, y1 + BOX_H / 2, y2 + BOX_H / 2  # right edge to left edge
        mid = (x1 + x2) / 2
        parts.append(
            f'<path d="M{x1} {y1} C{mid} {y1} {mid} {y2} {x2 - 6} {y2}" fill="none" '
            f'stroke="{MUTED}" stroke-width="1.6"/>'
            f'<path d="M{x2 - 7} {y2 - 4} L{x2} {y2} L{x2 - 7} {y2 + 4} z" fill="{MUTED}"/>'
        )
    for name, (_, _, kind) in NODES.items():
        x, y = _xy(name)
        fill, stroke, text, _ = STYLE[kind]
        dash = ' stroke-dasharray="5 3"' if kind == "source" else ""
        parts.append(
            f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="8" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="2"{dash}/>'
            f'<text x="{x + BOX_W / 2}" y="{y + 23}" {FONT} font-size="13" fill="{text}" '
            f'text-anchor="middle">{name}</text>'
        )
    # the key, along the bottom
    for k, kind in enumerate(STYLE):
        fill, stroke, _, caption = STYLE[kind]
        x, y = LEFT + k * 225, h - 26
        dash = ' stroke-dasharray="4 2"' if kind == "source" else ""
        parts.append(
            f'<rect x="{x}" y="{y - 12}" width="22" height="14" rx="3" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="2"{dash}/>'
            f'<text x="{x + 30}" y="{y}" {FONT} font-size="12" fill="{MUTED}">{caption}</text>'
        )
    return "".join(parts) + "</svg>"


def main() -> None:
    """Write the figure."""
    OUT.mkdir(exist_ok=True)
    (OUT / "lineage.svg").write_text(lineage(), encoding="utf-8")


if __name__ == "__main__":
    main()
