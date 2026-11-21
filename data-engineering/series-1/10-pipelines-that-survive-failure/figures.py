"""Draw the figures of Module 10 (figures/*.svg) from the same settings as the lesson.

Usage (from the series folder):
    uv run python 10-pipelines-that-survive-failure/figures.py

The crash-and-resume diagram uses the lesson's thirteen batches and its crash at batch 7; the
back-off chart uses the lesson's retry settings (first ceiling 0.5 s, doubling, at most 30 s) and
full jitter. The SVGs are committed, so the course site builds without running anything.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for figurekit
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

OUT = Path(__file__).parent / "figures"
N_BATCHES, CRASH_AT_BATCH = 13, 7  # as in the lesson: 12,060 records in batches of 1,000
FIRST_DELAY_S, MAX_DELAY_S = 0.5, 30.0  # the lesson's Setup constants
FONT = 'font-family="sans-serif"'


def _text(
    x: float,
    y: float,
    label: str,
    size: int = 13,
    colour: str = INK,
    anchor: str = "start",
    weight: str = "normal",
) -> str:
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


def crash_resume() -> str:
    """Two runs over the lesson's batches: the first crashes at batch 7, the second resumes."""
    w, h, left, cell, gap = 820, 330, 150, 44, 6
    done, saved, skipped, empty = VIOLET, CYAN, "#dcdfe7", "#f4f5f8"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]

    def box(k: int, y: float, fill: str, label_colour: str = "#ffffff") -> str:
        x = left + k * (cell + gap)
        return (
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="5" fill="{fill}"/>'
            + _text(x + cell / 2, y + cell / 2 + 5, str(k), 14, label_colour, "middle")
        )

    parts.append(_text(left, 34, "batch", 12, MUTED))
    # run 1: checkpointed up to the crash, the crashed batch saved without a checkpoint
    y1 = 54
    parts.append(_text(16, y1 + 20, "Run 1", 15, INK, weight="600"))
    parts.append(_text(16, y1 + 38, "crashes", 12, MUTED))
    for k in range(N_BATCHES):
        if k < CRASH_AT_BATCH:
            parts.append(box(k, y1, done))
        elif k == CRASH_AT_BATCH:
            parts.append(box(k, y1, saved))
        else:
            parts.append(box(k, y1, empty, MUTED))
    cx = left + CRASH_AT_BATCH * (cell + gap) + cell + gap / 2
    parts.append(f'<line x1="{cx}" y1="{y1 - 8}" x2="{cx}" y2="{y1 + cell + 8}" '
                 f'stroke="#d6336c" stroke-width="3"/>')  # fmt: skip
    crash_label = f"crash: rows of batch {CRASH_AT_BATCH} saved, checkpoint not"
    crash_x = left + CRASH_AT_BATCH * (cell + gap)
    parts.append(_text(crash_x, y1 + cell + 22, crash_label, 12, "#d6336c"))
    # run 2: skips the checkpointed batches, repeats the crashed one, finishes the rest
    y2 = 150
    parts.append(_text(16, y2 + 20, "Run 2", 15, INK, weight="600"))
    parts.append(_text(16, y2 + 38, "resumes", 12, MUTED))
    for k in range(N_BATCHES):
        parts.append(box(k, y2, skipped if k < CRASH_AT_BATCH else done,
                         MUTED if k < CRASH_AT_BATCH else "#ffffff"))  # fmt: skip
    rx = left + CRASH_AT_BATCH * (cell + gap)
    parts.append(_text(rx, y2 + cell + 22, "batch 7 runs again; the upsert keeps one copy",
                       12, INK))  # fmt: skip
    # key
    key = [
        (done, "processed and checkpointed"),
        (saved, "rows saved, no checkpoint"),
        (skipped, "skipped: checkpoint found"),
        (empty, "not reached"),
    ]
    ky = 262
    for i, (fill, label) in enumerate(key):
        x = 16 + i * 200
        parts.append(f'<rect x="{x}" y="{ky}" width="16" height="16" rx="3" fill="{fill}"/>')
        parts.append(_text(x + 22, ky + 13, label, 12))
    parts.append(_text(16, ky + 50, "Result: every table equals that of a run that never "
                       "crashed.", 13, INK, weight="600"))  # fmt: skip
    return "".join(parts) + "</svg>"


def backoff() -> str:
    """The back-off ceiling per attempt and twenty clients' jittered waits below it."""
    plt.rcParams["svg.hashsalt"] = "module-10"
    plt.rcParams["svg.fonttype"] = "none"
    attempts = np.arange(1, 9)
    ceiling = np.minimum(MAX_DELAY_S, FIRST_DELAY_S * 2.0 ** (attempts - 1))
    rng = np.random.default_rng(10)
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for n, top in zip(attempts, ceiling, strict=True):
        waits = rng.uniform(0, top, size=20)
        offsets = rng.uniform(-0.18, 0.18, size=20)
        ax.scatter(
            n + offsets,
            waits,
            s=16,
            color=CYAN,
            alpha=0.8,
            linewidths=0,
            label="one client's actual wait (full jitter)" if n == 1 else None,
        )
    ax.step(
        attempts,
        ceiling,
        where="mid",
        color=VIOLET,
        linewidth=2,
        label="ceiling: 0.5 s, doubling, at most 30 s",
    )
    ax.set_xlabel("failed attempt number", fontsize=11, color=INK)
    ax.set_ylabel("wait before retrying (s)", fontsize=11, color=INK)
    ax.set_xticks(attempts)
    ax.set_ylim(0, 32)
    ax.tick_params(colors=INK, labelsize=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=10, loc="upper left")
    ax.set_title("Exponential back-off with jitter: 20 clients", fontsize=12, color=INK,
                 loc="left")  # fmt: skip
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None})
    plt.close(fig)
    return buffer.getvalue()


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    figures = {"crash-resume": crash_resume, "backoff": backoff}
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
