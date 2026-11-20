"""Draw the figures of Module 12 (figures/*.svg): where each check sits, and what it found.

Usage (from the series folder):
    uv run python 12-validating-data/figures.py

The chart of failures is drawn from the lesson's own results: the script runs the lesson's code
(as lessonkit does) and counts the failing rows by check, so the picture shows exactly what the
code finds. The SVGs are committed, so the course site builds without running anything.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for figurekit, lessonkit
import lessonkit  # noqa: E402
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "figures"
FONT = 'font-family="sans-serif"'


def lesson_namespace() -> dict:
    """Run every code block of the lesson, in order, and return the variables it made.

    Returns:
        The lesson's namespace after its last block.
    """
    text = (HERE / "lesson.md").read_text(encoding="utf-8")
    namespace: dict = {"__name__": "__lesson__"}
    here = os.getcwd()
    os.chdir(HERE)
    try:
        for kind, body, _, _ in lessonkit.blocks(text):
            if kind == "python":
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(body, "lesson.md", "exec", dont_inherit=True), namespace)
    finally:
        os.chdir(here)
    return namespace


def box(x: float, y: float, w: float, h: float, lines: list[str], fill: str, ink: str) -> str:
    """A rounded box with centred lines of text.

    Args:
        x: Left edge.
        y: Top edge.
        w: Width.
        h: Height.
        lines: The text, one entry per line (the first in bold).
        fill: The box colour.
        ink: The text colour.

    Returns:
        The SVG elements.
    """
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}"/>']
    top = y + h / 2 - (len(lines) - 1) * 9
    for k, line in enumerate(lines):
        weight = "600" if k == 0 else "400"
        parts.append(
            f'<text x="{x + w / 2}" y="{top + 18 * k + 5}" {FONT} font-size="13" '
            f'font-weight="{weight}" fill="{ink}" text-anchor="middle">{line}</text>'
        )
    return "".join(parts)


def arrow(x1: float, y1: float, x2: float, y2: float) -> str:
    """A grey arrow from (x1, y1) to (x2, y2).

    Args:
        x1: Start, x.
        y1: Start, y.
        x2: End, x.
        y2: End, y.

    Returns:
        The SVG element.
    """
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="2" '
        f'marker-end="url(#head)"/>'
    )


def pipeline_checks() -> str:
    """Records checked one by one at the edge (Pydantic), tables in the middle (Pandera)."""
    w, h = 900, 360
    pale_violet, pale_cyan, pale = "#ece7fd", "#e0f4f7", "#f1f2f6"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>'
        f"</defs>",
        f'<text x="20" y="30" {FONT} font-size="14" font-weight="600" fill="{VIOLET}">'
        f"At the edges: one record at a time</text>",
        f'<text x="470" y="30" {FONT} font-size="14" font-weight="600" fill="{CYAN}">'
        f"In the middle: whole tables</text>",
        f'<line x1="445" y1="16" x2="445" y2="{h - 16}" stroke="#d9dbe3" stroke-dasharray="5,5"/>',
    ]
    sources = [["API response", "(Module 11)"], ["form entry"], ["instrument file"]]
    for k, lines in enumerate(sources):
        y = 60 + k * 90
        parts.append(box(20, y, 130, 60, lines, pale, INK))
        parts.append(arrow(150, y + 30, 208, 150 + 30 * k))
    pydantic_lines = ["Pydantic model", "checks each record:", "a typed object, or",
                      "an error per field"]  # fmt: skip
    parts.append(box(210, 120, 200, 120, pydantic_lines, pale_violet, INK))
    parts.append(arrow(410, 180, 466, 180))
    parts.append(box(468, 130, 150, 100, ["Pandera schema", "whole batch, lazy:", "every failure",
                                          "in one report"], pale_cyan, INK))  # fmt: skip
    parts.append(arrow(618, 160, 688, 95))
    parts.append(arrow(618, 180, 688, 180))
    parts.append(arrow(618, 200, 688, 265))
    parts.append(box(690, 60, 190, 64, ["kept rows", "loaded into the database"], pale, INK))
    parts.append(box(690, 148, 190, 64, ["failing rows + reasons", "quarantine table"], pale, INK))
    parts.append(box(690, 236, 190, 64, ["batch decision", "load, or stop if too many fail"],
                     pale, INK))  # fmt: skip
    parts.append(
        f'<text x="20" y="{h - 14}" {FONT} font-size="12" fill="{MUTED}">Both check the same '
        f"written contract (measurements 1.0.0).</text>"
    )
    return "".join(parts) + "</svg>"


def failures_by_check(ns: dict) -> str:
    """A bar chart of the rows each check failed, from the lesson's own validation run.

    Args:
        ns: The lesson's namespace (it holds `by_check`).

    Returns:
        The SVG text.
    """
    by_check = ns["by_check"].sort_values()
    plt.rcParams.update({"svg.hashsalt": "monstrous-12", "svg.fonttype": "none",
                         "font.family": "sans-serif", "font.size": 10})  # fmt: skip
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    bars = ax.barh(by_check.index, by_check.values, color=VIOLET, height=0.6)
    ax.bar_label(bars, padding=3, color=INK, fontsize=9)
    ax.set_xlabel(f"rows failing the check (of {len(ns['batch']):,})", color=INK)
    ax.set_ylabel("check (column: check, or table-level check)", color=INK)
    ax.set_xlim(0, by_check.max() * 1.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=INK)
    ax.set_title("Lazy validation of one batch: failing rows per check", color=INK, fontsize=11)
    fig.text(0.01, 0.01, "Data: the lesson's synthetic batch (chemlib structures, seeds 12-14).",
             fontsize=8, color=MUTED)  # fmt: skip
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = io.StringIO()
    fig.savefig(out, format="svg", metadata={"Date": None})
    plt.close(fig)
    return out.getvalue()


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    ns = lesson_namespace()
    figures = {
        "pipeline-checks": pipeline_checks(),
        "failures-by-check": failures_by_check(ns),
    }
    for name, svg in figures.items():
        (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
