"""Draw the figures of Module 15 (figures/*.svg): the pipeline, and the funnel of one run.

Usage (from the series folder):
    uv run python 15-capstone/figures.py

The funnel comes from running pipeline.py with the lesson's settings (into work/figures), so it
shows exactly what the lesson's run counts. The pipeline diagram is drawn by hand. The SVGs are
committed, so the course site builds without running anything.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # the series folder, for figurekit
sys.path.insert(0, str(HERE))  # this folder, for pipeline
import pipeline  # noqa: E402

from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

OUT = HERE / "figures"
plt.rcParams.update({"svg.hashsalt": "monstrous-15", "svg.fonttype": "none", "font.size": 10})
FONT = 'font-family="sans-serif"'


def box(x: float, y: float, title: str, line1: str, line2: str, colour: str) -> str:
    """One stage: a rounded box with a title and two short lines.

    Args:
        x: Left edge.
        y: Top edge.
        title: The stage's name.
        line1: First line of detail.
        line2: Second line of detail.
        colour: The outline colour.

    Returns:
        The SVG elements.
    """
    return (
        f'<rect x="{x}" y="{y}" width="150" height="64" rx="9" fill="#ffffff" stroke="{colour}" '
        f'stroke-width="2.2"/>'
        f'<text x="{x + 75}" y="{y + 21}" {FONT} font-size="14" font-weight="600" fill="{INK}" '
        f'text-anchor="middle">{title}</text>'
        f'<text x="{x + 75}" y="{y + 39}" {FONT} font-size="10.5" fill="{INK}" '
        f'text-anchor="middle">{line1}</text>'
        f'<text x="{x + 75}" y="{y + 54}" {FONT} font-size="10.5" fill="{INK}" '
        f'text-anchor="middle">{line2}</text>'
    )


def arrow(x1: float, y1: float, x2: float, y2: float, dashed: bool = False) -> str:
    """A straight arrow.

    Args:
        x1: Start x.
        y1: Start y.
        x2: End x.
        y2: End y.
        dashed: Draw it dashed (a link to a data store).

    Returns:
        The SVG element.
    """
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="1.8"'
        f'{dash} marker-end="url(#arrow)"/>'
    )


def pipeline_overview() -> str:
    """The stages in order, which run in parallel and which in order, and the data stores."""
    w, h = 920, 420
    xs = [25 + k * 180 for k in range(5)]
    row1 = [
        ("Library", "chemlib: a sample, or", "the whole 1.7 million"),
        ("Ingest", "one batch at a time;", "retries (tenacity)"),
        ("Validate", "PARSE, VALENCE", "→ quarantine"),
        ("Standardise", "parent, uncharge;", "ELEMENT → quarantine"),
        ("Describe, flag", "InChIKey, Morgan,", "descriptors, PAINS"),
    ]
    row2 = [
        ("Deduplicate", "first InChIKey wins,", "across all batches"),
        ("Filter", "PAINS, MW, logP", "→ removed, with reason"),
        ("Write", "Parquet, atomic:", "temporary file, rename"),
        ("Checkpoint", "batch + InChIKeys,", "one transaction"),
        ("Finish", "reconcile counts;", "views; manifest"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>'
        "</defs>",
        # the two frames: parallel work, and ordered commits
        f'<rect x="{xs[2] - 12}" y="30" width="{xs[4] - xs[2] + 174}" height="112" rx="12" '
        f'fill="none" stroke="{CYAN}" stroke-width="1.5" stroke-dasharray="7 5"/>',
        f'<text x="{xs[2] - 2}" y="46" {FONT} font-size="11.5" fill="{CYAN}">worker processes: '
        "several batches at once (pure functions)</text>",
        f'<rect x="{xs[0] - 12}" y="176" width="{xs[3] - xs[0] + 174}" height="112" rx="12" '
        f'fill="none" stroke="{VIOLET}" stroke-width="1.5" stroke-dasharray="7 5"/>',
        f'<text x="{xs[0] + 88}" y="192" {FONT} font-size="11.5" fill="{VIOLET}">main process: '
        "one batch at a time, in batch order</text>",
    ]
    for k, (x, stage) in enumerate(zip(xs, row1, strict=True)):
        parts.append(box(x, 56, *stage, MUTED if k < 2 else CYAN))
        if k < 4:
            parts.append(arrow(x + 152, 88, x + 178, 88))
    for k, (x, stage) in enumerate(zip(xs, row2, strict=True)):
        parts.append(box(x, 202, *stage, VIOLET if k < 4 else INK))
        if k < 4:
            parts.append(arrow(x + 152, 234, x + 178, 234))
    # from the end of the parallel work back to the start of the ordered commits
    parts.append(
        f'<path d="M{xs[4] + 75},121 L{xs[4] + 75},158 L{xs[0] + 75},158 L{xs[0] + 75},198" '
        f'fill="none" stroke="{MUTED}" stroke-width="1.8" marker-end="url(#arrow)"/>'
    )
    parts.append(
        f'<text x="{xs[4] + 75}" y="192" {FONT} font-size="10.5" fill="{MUTED}" '
        'text-anchor="middle">after the last batch</text>'
    )
    stores = [
        (xs[0] + 40, "Parquet: compounds,", "quarantine, removed", "(batch=NNNNN partitions)"),
        (xs[1] + 120, "DuckDB: runs, batches,", "seen InChIKeys, and", "views over the Parquet"),
        (xs[3] - 10, "manifest.json: input,", "rules + hash, versions,", "counts, file hashes"),
        (xs[4] + 20, "pipeline.log:", "one JSON event", "per line"),
    ]
    for x, line1, line2, line3 in stores:
        parts.append(
            f'<rect x="{x}" y="330" width="150" height="70" rx="4" fill="#f1f2f6" '
            f'stroke="{MUTED}" stroke-width="1"/>'
            f'<text x="{x + 75}" y="352" {FONT} font-size="11" fill="{INK}" '
            f'text-anchor="middle">{line1}</text>'
            f'<text x="{x + 75}" y="368" {FONT} font-size="11" fill="{INK}" '
            f'text-anchor="middle">{line2}</text>'
            f'<text x="{x + 75}" y="384" {FONT} font-size="11" fill="{INK}" '
            f'text-anchor="middle">{line3}</text>'
        )
    parts.append(arrow(xs[2] + 75, 266, xs[0] + 115, 328, dashed=True))  # write -> Parquet
    parts.append(arrow(xs[3] + 75, 266, xs[1] + 195, 328, dashed=True))  # checkpoint -> DuckDB
    parts.append(arrow(xs[4] + 60, 266, xs[3] + 65, 328, dashed=True))  # finish -> manifest
    parts.append(arrow(xs[4] + 100, 266, xs[4] + 95, 328, dashed=True))  # finish -> log
    return "".join(parts) + "</svg>"


def funnel() -> None:
    """Records at each stage of the lesson's run, with how many left at each step."""
    out = HERE / "work" / "figures"
    shutil.rmtree(out, ignore_errors=True)
    settings = pipeline.Settings(out_dir=out)
    counts = pipeline.run(settings)["counts"]
    stages = [
        ("records read", counts["rows_in"], ""),
        ("readable", counts["rows_in"] - counts["quarantined_validate"],
         f"{counts['quarantined_validate']} quarantined (PARSE, VALENCE)"),
        ("standardised", counts["rows_in"] - counts["quarantined_validate"]
         - counts["quarantined_standardise"],
         f"{counts['quarantined_standardise']} quarantined (ELEMENT)"),
        ("unique", counts["rows_out"] + counts["filtered"],
         f"{counts['duplicates']} duplicates removed"),
        ("passed filters", counts["rows_out"], f"{counts['filtered']} removed (PAINS, MW, logP)"),
    ]  # fmt: skip
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    y = list(range(len(stages)))[::-1]
    values = [n for _, n, _ in stages]
    colours = [MUTED, CYAN, CYAN, VIOLET, VIOLET]
    ax.barh(y, values, color=colours, height=0.62)
    for yy, (_, n, note) in zip(y, stages, strict=True):
        ax.text(n - 120, yy, f"{n:,}", va="center", ha="right", color="#ffffff", fontsize=10,
                fontweight="bold")  # fmt: skip
        if note:
            ax.text(n + 120, yy, note, va="center", ha="left", color=INK, fontsize=9)
    ax.set_yticks(y, [name for name, _, _ in stages])
    ax.set_xlim(0, counts["rows_in"] * 1.55)
    ax.set_xlabel("records (10,000 molecules sampled, faults added at 2%)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "funnel.svg")
    plt.close(fig)


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    (OUT / "pipeline-overview.svg").write_text(pipeline_overview(), encoding="utf-8")
    print("figures/pipeline-overview.svg")
    funnel()
    print("figures/funnel.svg")


if __name__ == "__main__":
    main()
