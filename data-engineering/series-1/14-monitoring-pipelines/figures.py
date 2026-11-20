"""Draw the figures of Module 14 (figures/*.svg) from the lesson's own runs.

Usage (from the series folder):
    uv run python 14-monitoring-pipelines/figures.py

The charts come from running the lesson's code (every python block, in order, as the tests do) and
plotting what it recorded, so the pictures show exactly what the lesson's runs did. The diagram of
the monitoring loop is drawn by hand. The SVGs are committed, so the course site builds without
running anything.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import duckdb  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for figurekit, lessonkit
import lessonkit  # noqa: E402
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "figures"
plt.rcParams.update({"svg.hashsalt": "monstrous-14", "svg.fonttype": "none", "font.size": 10})


def run_lesson() -> dict:
    """Run every python block of the lesson in one namespace, from the module's folder.

    Returns:
        The namespace the lesson's code leaves behind.
    """
    text = (HERE / "lesson.md").read_text(encoding="utf-8")
    namespace: dict = {"__name__": "__lesson__"}
    here = os.getcwd()
    os.chdir(HERE)
    try:
        for kind, body, _, _ in lessonkit.blocks(text):
            if kind == "python":
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(body, "lesson.md", "exec"), namespace)
    finally:
        os.chdir(here)
    return namespace


def monitoring_loop() -> str:
    """The monitoring loop: run, record, check, alert, and a person who fixes and reruns."""
    w, h = 760, 300
    boxes = [
        (30, "Run", "steps: validate, dedupe,", "enrich, describe, publish"),
        (215, "Record", "JSON log lines; run and", "step rows in DuckDB"),
        (400, "Check", "reconcile; freshness;", "quarantine rate; drift"),
        (585, "Alert", "page or ticket, once", "when a rule starts or stops"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
        f'markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>'
        "</defs>",
    ]
    for k, (x, title, line1, line2) in enumerate(boxes):
        colour = VIOLET if k % 2 == 0 else CYAN
        parts.append(
            f'<rect x="{x}" y="60" width="150" height="100" rx="10" fill="#ffffff" '
            f'stroke="{colour}" stroke-width="2.5"/>'
            f'<text x="{x + 75}" y="92" font-family="sans-serif" font-size="17" font-weight="600" '
            f'fill="{INK}" text-anchor="middle">{title}</text>'
            f'<text x="{x + 75}" y="118" font-family="sans-serif" font-size="11.5" '
            f'fill="{INK}" text-anchor="middle">{line1}</text>'
            f'<text x="{x + 75}" y="136" font-family="sans-serif" font-size="11.5" '
            f'fill="{INK}" text-anchor="middle">{line2}</text>'
        )
        if k < len(boxes) - 1:
            parts.append(
                f'<line x1="{x + 152}" y1="110" x2="{x + 183}" y2="110" stroke="{MUTED}" '
                f'stroke-width="2" marker-end="url(#arrow)"/>'
            )
    parts.append(
        f'<path d="M660,162 L660,240 L105,240 L105,166" fill="none" stroke="{MUTED}" '
        f'stroke-width="2" stroke-dasharray="6 4" marker-end="url(#arrow)"/>'
        f'<text x="382" y="262" font-family="sans-serif" font-size="13" fill="{INK}" '
        'text-anchor="middle">a person investigates, fixes the cause, and the next run is '
        "checked again</text>"
        f'<text x="380" y="34" font-family="sans-serif" font-size="13" fill="{MUTED}" '
        'text-anchor="middle">every night, for every run: did it run, did it do the right '
        "thing, is the data what we expect?</text>"
    )
    return "".join(parts) + "</svg>"


def drift_histograms(ns: dict) -> None:
    """Molecular weight of the reference, an ordinary batch and the one-page batch."""
    reference = ns["reference"]["mw"].to_numpy()
    ordinary, one_page = ns["ordinary"][0], ns["one_page"][0]
    bins = np.arange(150, 651, 12.5)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(reference, bins, density=True, color=MUTED, alpha=0.55, label="reference (run 1)")
    ax.hist(ordinary, bins, density=True, histtype="step", linewidth=2, color=CYAN,
            label=f"ordinary batch (PSI {ns['psi'](reference, ordinary):.3f})")  # fmt: skip
    ax.hist(one_page, bins, density=True, histtype="step", linewidth=2, color=VIOLET,
            label=f"one-page batch (PSI {ns['psi'](reference, one_page):.2f})")  # fmt: skip
    ax.set_xlabel("molecular weight (g/mol)")
    ax.set_ylabel("share of molecules per g/mol")
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "drift-histograms.svg")
    plt.close(fig)


def main() -> None:
    """Run the lesson and write every figure."""
    OUT.mkdir(exist_ok=True)
    (OUT / "monitoring-loop.svg").write_text(monitoring_loop(), encoding="utf-8")
    print("figures/monitoring-loop.svg")
    ns = run_lesson()
    drift_histograms(ns)
    print("figures/drift-histograms.svg")
    db = duckdb.connect(str(HERE / "work" / "monitoring.duckdb"), read_only=True)
    ns["dashboard"](db, OUT / "run-dashboard.svg")
    db.close()
    print("figures/run-dashboard.svg")


if __name__ == "__main__":
    main()
