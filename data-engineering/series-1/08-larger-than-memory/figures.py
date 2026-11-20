"""Draw the figures of Module 8 (figures/*.svg): streaming against loading, and measured memory.

Usage (from the series folder):
    uv run python 08-larger-than-memory/figures.py

The memory chart is measured: each point runs the lesson's two jobs (stream in batches, or load
everything) in a fresh Python process and records the most memory that process held. The numbers
depend on the computer, so the caption in the lesson says it is one measured run.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES = Path(__file__).parents[1]
sys.path.insert(0, str(SERIES))  # the series folder, for figurekit and chemlib
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

OUT = Path(__file__).parent / "figures"
SIZES = [100_000, 250_000, 500_000, 750_000, 1_000_000]
BATCH = 25_000
ATOM = r"\[[^\]]+\]|Br|Cl|[BCNOPSFI]|[bcnops]"


def _box(x: float, y: float, w: float, h: float, fill: str, label: str = "") -> str:
    """One rounded box with an optional centred label, as SVG."""
    text = ""
    if label:
        text = (f'<text x="{x + w / 2}" y="{y + h / 2 + 5}" font-family="sans-serif" '
                f'font-size="13" fill="#fff" text-anchor="middle">{label}</text>')  # fmt: skip
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}"/>{text}'


def _text(x: float, y: float, words: str, size: int = 14, colour: str = INK, bold: bool = False):
    """A line of SVG text."""
    weight = ' font-weight="600"' if bold else ""
    return (f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" '
            f'fill="{colour}"{weight}>{words}</text>')  # fmt: skip


def stream_vs_load() -> str:
    """Loading everything (all batches in memory at once) beside streaming (one batch at a time)."""
    w, h = 760, 330
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>'
        "</defs>",
        _text(20, 30, "Load everything", 16, INK, True),
        _text(400, 30, "Stream in batches", 16, INK, True),
    ]
    # left: every batch sits in memory together, then one big write
    parts.append(_text(20, 58, "memory holds every batch at once", 13, MUTED))
    parts.append(f'<rect x="20" y="70" width="170" height="220" rx="8" fill="none" '
                 f'stroke="{VIOLET}" stroke-width="2" stroke-dasharray="6 4"/>')  # fmt: skip
    for k in range(6):
        parts.append(_box(35, 82 + k * 34, 140, 26, VIOLET, f"batch {k + 1}"))
    parts.append(f'<line x1="195" y1="180" x2="265" y2="180" stroke="{MUTED}" stroke-width="2" '
                 'marker-end="url(#arrow)"/>')  # fmt: skip
    parts.append(_box(270, 150, 100, 60, INK, "file"))
    parts.append(_text(20, 312, "memory grows with the library", 13, VIOLET, True))
    # right: one batch in memory, processed, written, forgotten
    parts.append(_text(400, 58, "memory holds one batch", 13, MUTED))
    parts.append(f'<rect x="400" y="150" width="130" height="60" rx="8" fill="none" '
                 f'stroke="{CYAN}" stroke-width="2" stroke-dasharray="6 4"/>')  # fmt: skip
    parts.append(_box(412, 167, 106, 26, CYAN, "batch k"))
    for k in range(4):
        parts.append(_box(420 + k * 26, 80, 20, 26, "#d5eef2"))
    parts.append(_text(530, 92, "batches still to come", 12, MUTED))
    parts.append(_text(530, 108, "(not made yet)", 12, MUTED))
    parts.append(f'<line x1="465" y1="110" x2="465" y2="146" stroke="{MUTED}" stroke-width="2" '
                 'marker-end="url(#arrow)"/>')  # fmt: skip
    parts.append(f'<line x1="535" y1="180" x2="605" y2="180" stroke="{MUTED}" stroke-width="2" '
                 'marker-end="url(#arrow)"/>')  # fmt: skip
    parts.append(_text(540, 170, "process,", 12, MUTED))
    parts.append(_text(540, 200, "write", 12, MUTED))
    parts.append(_box(610, 130, 100, 100, INK))
    for k in range(5):
        parts.append(f'<rect x="620" y="{138 + k * 18}" width="80" height="12" rx="2" '
                     f'fill="{CYAN if k < 3 else "#3a3f52"}"/>')  # fmt: skip
    parts.append(_text(610, 250, "file: one row", 12, MUTED))
    parts.append(_text(610, 266, "group per batch", 12, MUTED))
    parts.append(_text(400, 312, "memory stays flat, whatever the total", 13, CYAN, True))
    return "".join(parts) + "</svg>"


def _measure(mode: str, n: int) -> None:
    """Run one job in this (fresh) process and print the most memory it held above the start.

    Args:
        mode: "stream" or "load".
        n: How many molecules.
    """
    import pandas as pd
    import psutil
    import pyarrow as pa
    import pyarrow.parquet as pq

    import chemlib

    def add_columns(batch: pd.DataFrame) -> pd.DataFrame:
        out = batch.copy()
        out["heavy_atoms"] = out["smiles"].str.count(ATOM).astype("int16")
        out["halogens"] = out["smiles"].str.count(r"Br|Cl|F|I").astype("int16")
        return out

    def stream(path: str, count: int) -> None:
        writer = None
        for batch in chemlib.stream(count, batch=BATCH):
            table = pa.Table.from_pandas(add_columns(batch), preserve_index=False)
            writer = writer or pq.ParquetWriter(path, table.schema, compression="zstd")
            writer.write_table(table)
        writer.close()

    def load(path: str, count: int) -> None:
        everything = pd.concat(list(chemlib.stream(count, batch=BATCH)), ignore_index=True)
        table = pa.Table.from_pandas(add_columns(everything), preserve_index=False)
        pq.write_table(table, path, compression="zstd")

    with tempfile.TemporaryDirectory() as folder:
        stream(f"{folder}/warm-up.parquet", BATCH)  # start-up costs are not counted
        process = psutil.Process()
        start = peak = process.memory_info().rss
        done = threading.Event()

        def watch() -> None:
            nonlocal peak
            while not done.is_set():
                peak = max(peak, process.memory_info().rss)
                time.sleep(0.005)

        watcher = threading.Thread(target=watch)
        watcher.start()
        {"stream": stream, "load": load}[mode](f"{folder}/out.parquet", n)
        done.set()
        watcher.join()
        peak = max(peak, process.memory_info().rss)
    print((peak - start) / 1e6)


def memory_use() -> str:
    """Measured peak memory against library size, for streaming and for loading everything."""
    results: dict[str, list[float]] = {"stream": [], "load": []}
    for n in SIZES:
        for mode in results:
            out = subprocess.run(
                [sys.executable, __file__, "--measure", mode, str(n)],
                capture_output=True, text=True, check=True, cwd=SERIES,
            )  # fmt: skip
            results[mode].append(float(out.stdout.strip().splitlines()[-1]))
            print(f"  {mode:6} {n:>9,} molecules: {results[mode][-1]:6.0f} MB", file=sys.stderr)
    plt.rcParams.update({"svg.hashsalt": "module-8", "svg.fonttype": "none", "font.size": 11})
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    thousands = [n / 1000 for n in SIZES]
    ax.plot(thousands, results["load"], "o-", color=VIOLET, label="load everything, then write")
    ax.plot(thousands, results["stream"], "s-", color=CYAN,
            label=f"stream in batches of {BATCH:,}")  # fmt: skip
    ax.set_xlabel("molecules processed (thousands)")
    ax.set_ylabel("peak memory above start (MB)")
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    ax.set_title("One measured run; yours will differ", fontsize=10, color=MUTED, loc="left")
    fig.tight_layout()
    path = OUT / "memory-use.svg"
    fig.savefig(path, format="svg", metadata={"Date": None})
    plt.close(fig)
    return path.read_text(encoding="utf-8")


def main() -> None:
    """Write every figure (or, with --measure, take one measurement for the memory chart)."""
    if "--measure" in sys.argv:
        _measure(sys.argv[2], int(sys.argv[3]))
        return
    OUT.mkdir(exist_ok=True)
    figures = {"stream-vs-load": stream_vs_load, "memory-use": memory_use}
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
