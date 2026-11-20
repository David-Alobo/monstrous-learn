"""Draw the figures of Module 9 (figures/*.svg): chunks going to workers, and a measured speed-up.

Usage (from the series folder):
    uv run python 09-parallel-and-distributed/figures.py

The speed-up chart is measured: it times the lesson's describe step on the lesson's 12,000
molecules with 1, 2, 4 and 8 joblib workers (the fastest of three runs each), and fits Amdahl's
law to the measurements. The numbers depend on the computer, so the caption in the lesson says it
is one measured run.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # the series folder, for figurekit and chemlib
sys.path.insert(0, str(HERE))  # this folder, for workers (the workers import it from here too)
import workers  # noqa: E402

import chemlib  # noqa: E402
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

OUT = HERE / "figures"
N_JOBS = [1, 2, 4, 8]


def _text(x: float, y: float, words: str, size: int = 13, colour: str = INK, anchor: str = "start",
          bold: bool = False) -> str:  # fmt: skip
    """A line of SVG text."""
    weight = ' font-weight="600"' if bold else ""
    return (f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" fill="{colour}" '
            f'text-anchor="{anchor}"{weight}>{words}</text>')  # fmt: skip


def _arrow(x1: float, y1: float, x2: float, y2: float) -> str:
    """A grey arrow."""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="1.6" '
            'marker-end="url(#arrow)"/>')  # fmt: skip


def chunks_to_workers() -> str:
    """A list of SMILES split into chunks, sent to worker processes, results joined in order."""
    w, h = 780, 330
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>'
        "</defs>",
        _text(20, 28, "main process", 14, INK, bold=True),
        _text(330, 28, "worker processes", 14, INK, bold=True),
        _text(610, 28, "main process", 14, INK, bold=True),
    ]
    # the chunks of SMILES, in order
    parts.append(_text(20, 52, "SMILES, in chunks", 12, MUTED))
    for k in range(8):
        y = 64 + k * 30
        parts.append(f'<rect x="20" y="{y}" width="150" height="24" rx="4" fill="{CYAN}"/>')
        parts.append(_text(95, y + 16, f"chunk {k + 1}", 12, "#fff", "middle"))
    # four workers
    for j in range(4):
        y = 64 + j * 62
        parts.append(f'<rect x="330" y="{y}" width="190" height="46" rx="8" fill="{VIOLET}"/>')
        parts.append(_text(425, y + 19, f"worker {j + 1}", 13, "#fff", "middle", True))
        parts.append(_text(425, y + 36, "parse, describe", 11, "#fff", "middle"))
    for k in range(8):
        y_from, y_to = 76 + k * 30, 87 + (k % 4) * 62
        parts.append(_arrow(172, y_from, 326, y_to))
    # results, in the original order
    parts.append(_text(610, 52, "rows, in the original order", 12, MUTED))
    for k in range(8):
        y = 64 + k * 30
        parts.append(f'<rect x="610" y="{y}" width="150" height="24" rx="4" fill="{INK}"/>')
        parts.append(_text(685, y + 16, f"rows of chunk {k + 1}", 12, "#fff", "middle"))
    for k in range(8):  # chunk k went to worker k % 4; its rows come back to place k
        parts.append(_arrow(522, 87 + (k % 4) * 62, 606, 76 + k * 30))
    parts.append(_text(20, 318, "send compact SMILES out; get plain values (text, numbers) back",
                       12, MUTED))  # fmt: skip
    return "".join(parts) + "</svg>"


def _fit_amdahl(n_jobs: list[int], speed_up: list[float]) -> float:
    """The parallel fraction p for which Amdahl's law best fits the measured speed-ups.

    1/S = (1 - p) + p/n, so 1/S - 1 = p (1/n - 1): a straight line through the origin.
    """
    xs = [1 / n - 1 for n in n_jobs]
    ys = [1 / s - 1 for s in speed_up]
    return sum(x * y for x, y in zip(xs, ys, strict=True)) / sum(x * x for x in xs)


def speed_up() -> str:
    """Measured speed-up against workers, beside the ideal and Amdahl's law fitted to it."""
    smiles = list(chemlib.library(12_000, seed=9)["smiles"])
    chunks = [smiles[i : i + 750] for i in range(0, len(smiles), 750)]
    seconds = {}
    for n in N_JOBS:
        Parallel(n_jobs=n)(delayed(workers.describe)(c) for c in chunks[:n])  # start the workers
        runs = []
        for _ in range(3):  # the fastest of three runs: less disturbed by other programs
            start = time.perf_counter()
            Parallel(n_jobs=n)(delayed(workers.describe)(c) for c in chunks)
            runs.append(time.perf_counter() - start)
        seconds[n] = min(runs)
        print(f"  n_jobs={n}: {seconds[n]:.2f} s", file=sys.stderr)
    measured = [seconds[1] / seconds[n] for n in N_JOBS]
    p = _fit_amdahl(N_JOBS, measured)
    print(f"  fitted parallel fraction p = {p:.3f}", file=sys.stderr)
    smooth = [1 + k * 0.1 for k in range(71)]
    plt.rcParams.update({"svg.hashsalt": "module-9", "svg.fonttype": "none", "font.size": 11})
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(smooth, smooth, "--", color=MUTED, label="ideal: n workers, n times faster")
    ax.plot(smooth, [1 / ((1 - p) + p / n) for n in smooth], "-", color=VIOLET,
            label=f"Amdahl's law, fitted: p = {p:.2f}")  # fmt: skip
    ax.plot(N_JOBS, measured, "o", color=CYAN, markersize=8, label="measured")
    ax.set_xlabel("joblib workers (n_jobs)")
    ax.set_ylabel("speed-up (serial time / parallel time)")
    ax.set_xticks(N_JOBS)
    ax.set_xlim(0.5, 8.5)
    ax.set_ylim(0, 8.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("One measured run (12,000 molecules); yours will differ", fontsize=10,
                 color=MUTED, loc="left")  # fmt: skip
    fig.tight_layout()
    path = OUT / "speed-up.svg"
    fig.savefig(path, format="svg", metadata={"Date": None})
    plt.close(fig)
    return path.read_text(encoding="utf-8")


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    figures = {"chunks-to-workers": chunks_to_workers, "speed-up": speed_up}
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
