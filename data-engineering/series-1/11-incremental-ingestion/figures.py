"""Draw the figures of Module 11 (figures/*.svg) from the lesson's recorded responses.

Usage (from the series folder):
    uv run python 11-incremental-ingestion/figures.py

The high-water-mark chart reads the recorded ChEMBL pages in recorded/, so it shows exactly the
records the lesson loads; the pagination diagram uses the page sizes of the lesson's first run.
The SVGs are committed, so the course site builds without running anything.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for figurekit
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "figures"
RECORDED = HERE / "recorded"
FONT = 'font-family="sans-serif"'
ORANGE = "#d6336c"


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


def _box(x: float, y: float, w: float, h: float, fill: str, label: str = "",
         colour: str = "#ffffff") -> str:  # fmt: skip
    """A rounded box with a centred label.

    Args:
        x: Left edge.
        y: Top edge.
        w: Width.
        h: Height.
        fill: Fill colour.
        label: Text in the middle.
        colour: The label's colour.

    Returns:
        The elements.
    """
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}"/>'
            + _text(x + w / 2, y + h / 2 + 5, label, 13, colour, "middle"))  # fmt: skip


def _recorded_runs() -> dict[str, list[int]]:
    """The activity ids each kind of request in the recordings returned.

    Returns:
        Activity ids for "run 1", "run 2", "run 3" and "backfill".
    """
    runs: dict[str, list[int]] = {"run 1": [], "run 2": [], "run 3": [], "backfill": []}
    lower_bounds = []
    for path in sorted(RECORDED.glob("chembl-*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        query = dict(parse_qsl(urlsplit(entry["url"]).query))
        ids = [a["activity_id"] for a in entry["body"]["activities"]]
        if "activity_id__gte" in query:
            runs["backfill"] += ids
        elif "activity_id__lte" in query:
            runs["run 1"] += ids
        else:
            lower_bounds.append((int(query["activity_id__gt"]), ids))
    first, last = min(b for b, _ in lower_bounds), max(b for b, _ in lower_bounds)
    for bound, ids in lower_bounds:
        runs["run 2" if bound == first else "run 3"] += ids
    assert first != last, "expected two incremental runs above the first run's mark"
    return runs


def high_water_mark() -> str:
    """Each run's records along the activity-id line, with the high-water mark after each run."""
    plt.rcParams["svg.hashsalt"] = "module-11"
    plt.rcParams["svg.fonttype"] = "none"
    runs = _recorded_runs()
    mark1, mark2 = max(runs["run 1"]), max(runs["run 2"])
    rows = ["run 1", "run 2", "run 3", "backfill"]
    colours = {"run 1": VIOLET, "run 2": CYAN, "run 3": MUTED, "backfill": ORANGE}
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    for y, name in enumerate(rows):
        ids = [i / 1e6 for i in runs[name]]
        ax.scatter(ids, [y] * len(ids), marker="|", s=180, color=colours[name], linewidths=1.2)
        label = f"{len(ids)} records" if ids else "0 records"
        ax.text(29.6, y, label, va="center", fontsize=10, color=INK)
    if runs["backfill"]:
        lo, hi = min(runs["backfill"]) / 1e6, max(runs["backfill"]) / 1e6
        ax.axvspan(lo, hi, color=ORANGE, alpha=0.12, linewidth=0)
    for mark, text in ((mark1, "mark after run 1"), (mark2, "mark after runs 2 and 3")):
        ax.axvline(mark / 1e6, color=INK, linestyle="--", linewidth=1)
        ax.text(
            mark / 1e6,
            -0.75,
            text,
            ha="center",
            fontsize=9,
            color=INK,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
        )
    ax.set_yticks(range(len(rows)), rows, fontsize=10)
    ax.set_ylim(len(rows) - 0.5, -1.0)
    ax.set_xlim(0, 29.4)
    ax.set_xlabel("ChEMBL activity_id (millions)", fontsize=11, color=INK)
    ax.tick_params(colors=INK, labelsize=10)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_title("IKK-epsilon IC50 records fetched by each run (recorded responses)",
                 fontsize=11, color=INK, loc="left")  # fmt: skip
    fig.tight_layout()
    fig.subplots_adjust(right=0.78)
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None})
    plt.close(fig)
    return buffer.getvalue()


def pagination() -> str:
    """Pages of the first run via page_meta.next, and offset paging against keyset paging."""
    runs = _recorded_runs()
    total, limit = len(runs["run 1"]), 100
    w, h = 820, 400
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        _text(
            16,
            28,
            f"Following page_meta.next: {total} records, limit={limit}",
            15,
            INK,
            weight="600",
        ),  # fmt: skip
    ]
    x, scale = 16, 640 / total
    for offset in range(0, total, limit):
        n = min(limit, total - offset)
        nxt = f"next: offset={offset + limit}" if offset + limit < total else "next: none"
        parts.append(_box(x, 44, n * scale - 6, 40, VIOLET, f"offset={offset}: {n} records"))
        parts.append(_text(x + 4, 104, nxt, 12, MUTED))
        x += n * scale
    # offset paging when a record is inserted between two requests
    parts.append(_text(16, 160, "When the data change between requests (page size 3)", 15, INK,
                       weight="600"))  # fmt: skip
    cell = 46

    def row(y: float, label: str, ids: list[str], fills: list[str]) -> None:
        parts.append(_text(16, y + 27, label, 12, INK))
        for k, (i, fill) in enumerate(zip(ids, fills, strict=True)):
            parts.append(_box(330 + k * (cell + 6), y, cell, 40, fill, i,
                              "#ffffff" if fill != "#f1f2f6" else MUTED))  # fmt: skip

    grey = "#f1f2f6"
    row(176, "request 1, offset 0: gets 10 20 30", ["10", "20", "30", "40", "50", "60"],
        [VIOLET, VIOLET, VIOLET, grey, grey, grey])  # fmt: skip
    after = ["10", "15", "20", "30", "40", "50", "60"]
    row(226, "record 15 is added; request 2, offset 3:", after,
        [grey, CYAN, grey, ORANGE, VIOLET, VIOLET, grey])  # fmt: skip
    parts.append(_text(330 + 7 * (cell + 6) + 8, 252, "30 arrives twice", 12, ORANGE))
    row(276, "keyset instead: activity_id &gt; 30", after,
        [grey, grey, grey, grey, VIOLET, VIOLET, VIOLET])  # fmt: skip
    parts.append(_text(330 + 7 * (cell + 6) + 8, 302, "no repeat", 12, INK))
    parts.append(_text(16, 352, "Offset counts positions, so an insertion before the offset "
                       "repeats a record and a deletion skips one.", 13, INK))  # fmt: skip
    parts.append(_text(16, 374, "Asking for keys above the last one seen does not depend on "
                       "positions; the high-water mark uses the same idea between runs.", 13,
                       INK))  # fmt: skip
    return "".join(parts) + "</svg>"


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    figures = {"high-water-mark": high_water_mark, "pagination": pagination}
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
