"""Draw the figure of Module 1 (figures/three-layers.svg): the lab's data flow through three layers.

Usage (from the series folder):
    uv run python 01-lab-data-architecture/figures.py

The boxes are the stages the lesson builds (inbox, raw, staging, marts, then the people and
programs that read the marts); under each arrow is the module of this series, and the tool, that
takes it over. The SVG is committed, so the course site builds without running anything.
"""

from __future__ import annotations

from pathlib import Path

# the course's colours (the same as Series 1's figurekit)
INK, VIOLET, CYAN, MUTED = "#1d2130", "#7c5cf0", "#0e9fb5", "#8b91a1"
OUT = Path(__file__).parent / "figures"
FONT = 'font-family="sans-serif"'

# the stages, left to right: (title, lines under the title, colour)
STAGES = [
    ("Inbox", ["the lab's files,", "as they arrive"], MUTED),
    ("Raw", ["every file, unchanged,", "with where it came from"], VIOLET),
    ("Staging", ["typed, one name per", "column, no duplicates"], VIOLET),
    ("Marts", ["shaped for the", "chemists' questions"], VIOLET),
    ("Readers", ["dashboards, models,", "reports"], CYAN),
]
# what moves data along each arrow, and the module of this series that takes it over
ARROWS = [("load", "dlt, M2"), ("clean", "dbt, M4-6"), ("shape", "dbt, M3-4"), ("serve", "M10")]
BOX_W, BOX_H, GAP, LEFT, TOP = 150, 92, 84, 20, 30


def _text(x: float, y: float, label: str, size: int = 13, colour: str = INK,
          anchor: str = "middle", weight: str = "normal") -> str:  # fmt: skip
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


def figure() -> str:
    """The three-layer diagram as an SVG document.

    Returns:
        The SVG text.
    """
    width = LEFT * 2 + len(STAGES) * BOX_W + (len(STAGES) - 1) * GAP
    height = TOP + BOX_H + 84
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ),
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        (
            '<defs><marker id="head" markerWidth="10" markerHeight="8" refX="9" refY="4" '
            f'orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="{INK}"/></marker></defs>'
        ),
    ]
    for k, (title, lines, colour) in enumerate(STAGES):
        x = LEFT + k * (BOX_W + GAP)
        parts.append(f'<rect x="{x}" y="{TOP}" width="{BOX_W}" height="{BOX_H}" rx="12" '
                     f'fill="#ffffff" stroke="{colour}" stroke-width="2.5"/>')  # fmt: skip
        parts.append(_text(x + BOX_W / 2, TOP + 30, title, 16, colour, weight="bold"))
        for j, line in enumerate(lines):
            parts.append(_text(x + BOX_W / 2, TOP + 54 + j * 17, line, 12, INK))
        if k < len(ARROWS):
            x0, x1, y = x + BOX_W + 4, x + BOX_W + GAP - 4, TOP + BOX_H / 2
            parts.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{INK}" '
                         'stroke-width="2" marker-end="url(#head)"/>')  # fmt: skip
            action, tool = ARROWS[k]
            parts.append(_text(x0 + (x1 - x0) / 2, y - 9, action, 12, INK))
            parts.append(_text(x0 + (x1 - x0) / 2, y + 20, tool, 11, MUTED))
    # the two jobs that span every stage
    y = TOP + BOX_H + 30
    span = LEFT + len(STAGES) * BOX_W + (len(STAGES) - 1) * GAP
    for row, (label, colour) in enumerate(
        [("run every week, with retries: Prefect (M7)", CYAN),
         ("tests, history, observability and CI at every step (M5, M6, M8, M9)", VIOLET)]
    ):  # fmt: skip
        yy = y + row * 24
        parts.append(f'<rect x="{LEFT}" y="{yy}" width="{span - LEFT}" height="18" rx="9" '
                     f'fill="{colour}" fill-opacity="0.12"/>')  # fmt: skip
        parts.append(_text(LEFT + (span - LEFT) / 2, yy + 13, label, 12, colour))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    (OUT / "three-layers.svg").write_text(figure(), encoding="utf-8", newline="\n")
    print(f"wrote {OUT / 'three-layers.svg'}")
