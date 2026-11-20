"""Draw the figures of Module 6 (figures/*.svg) from the lesson's own code and results.

Usage (from the series folder):
    uv run python 06-validating-molecules/figures.py

The script runs the lesson's code (as the tests do) and draws from its results, so the numbers in
the pictures are exactly what the code finds. The SVGs are committed, so the course site builds
without RDKit.
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
import matplotlib.ticker  # noqa: E402

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # the series folder, for figurekit, lessonkit and chemlib
import lessonkit  # noqa: E402
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

OUT = HERE / "figures"
ACTION_COLOUR = {"reject": VIOLET, "fix": CYAN, "warn": MUTED}
plt.rcParams.update(
    {
        "svg.hashsalt": "module-6",
        "svg.fonttype": "none",
        "font.family": "sans-serif",
        "font.size": 12,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
    }
)


def lesson_namespace() -> dict:
    """Run every python block of the lesson, quietly, and return the variables it made."""
    _meta, body = lessonkit.front_matter((HERE / "lesson.md").read_text(encoding="utf-8"))
    namespace: dict = {"__name__": "__lesson__"}
    here = os.getcwd()
    os.chdir(HERE)
    try:
        for kind, code, _start, _end in lessonkit.blocks(body):
            if kind == "python":
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(code, "lesson.md", "exec"), namespace)
    finally:
        os.chdir(here)
    return namespace


def box(x: float, y: float, w: float, h: float, lines: list[str], fill: str, ink: str) -> str:
    """A rounded box with one or more centred lines of text."""
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
             f'stroke="{ink}" stroke-width="1.5"/>']  # fmt: skip
    top = y + h / 2 - 9 * (len(lines) - 1)
    for k, line in enumerate(lines):
        weight = "600" if k == 0 else "400"
        parts.append(
            f'<text x="{x + w / 2}" y="{top + 18 * k + 5}" font-family="sans-serif" '
            f'font-size="14" font-weight="{weight}" fill="{INK}" text-anchor="middle">{line}</text>'
        )
    return "".join(parts)


def arrow(x1: float, y1: float, x2: float, y2: float, label: str = "",
          at: tuple[float, float] | None = None) -> str:  # fmt: skip
    """A straight arrow with an optional label, placed at `at` or beside the arrow's middle."""
    text = ""
    if label:
        lx, ly = at or ((x1 + x2) / 2 + 8, (y1 + y2) / 2 - 8)
        text = (f'<text x="{lx}" y="{ly}" font-family="sans-serif" '
                f'font-size="13" fill="{MUTED}">{label}</text>')  # fmt: skip
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{INK}" stroke-width="1.5" '
        f'marker-end="url(#head)"/>{text}'
    )


def validation_gate(ns: dict) -> str:
    """The gate as a flow diagram, with the lesson's own counts."""
    verdicts = ns["results"]["verdict"].value_counts()
    total = len(ns["results"])
    q = ns["results"][ns["results"]["verdict"] == "quarantine"]
    fixable = sum(all(i.action != "reject" for i in issues) for issues in q["issues"])
    rejected = len(q) - fixable
    reading = {"PARSE", "SANITISATION", *ns["PROBLEM_CODES"].values()}
    unreadable = sum(issues[0].code in reading for issues in q["issues"])
    w, h = 860, 470
    pale = {"in": "#eef0f5", "gate": "#f1edfe", "ok": "#e6f6f8", "bad": "#f1edfe"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
        f'markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>'
        f"</defs>",
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        box(30, 30, 220, 60, ["Incoming records", f"{total:,} SMILES"], pale["in"], MUTED),
        box(
            30,
            150,
            220,
            80,
            ["1. Read and sanitise", "MolFromSmiles(sanitize=False)", "DetectChemistryProblems"],
            pale["gate"],
            VIOLET,
        ),  # fmt: skip
        box(
            30,
            300,
            220,
            120,
            [
                "2. Check the molecule",
                "elements (allow-list)",
                "fragments, net charge",
                "stereo (warn), size",
            ],
            pale["gate"],
            VIOLET,
        ),  # fmt: skip
        box(
            560,
            150,
            270,
            100,
            [
                "Quarantine",
                f"{verdicts.get('quarantine', 0):,} records",
                "every issue: code, message, action",
            ],
            pale["bad"],
            VIOLET,
        ),  # fmt: skip
        box(
            560,
            330,
            270,
            80,
            ["Accept", f"{verdicts.get('accept', 0):,} records", "warnings stored with the record"],
            pale["ok"],
            CYAN,
        ),  # fmt: skip
        box(560, 30, 125, 70, ["Reject", f"{rejected} records"], "#ffffff", VIOLET),
        box(705, 30, 125, 70, ["Fix: Module 7", f"{fixable} records"], "#ffffff", CYAN),
        arrow(140, 90, 140, 148),
        arrow(140, 230, 140, 298, "readable"),
        arrow(250, 190, 558, 190, f"cannot be read ({unreadable})", (300, 180)),
        arrow(250, 320, 558, 235, "any reject or fix issue", (310, 330)),
        arrow(250, 370, 558, 370, "no issues, or warnings only", (300, 360)),
        arrow(640, 150, 625, 102),
        arrow(750, 150, 765, 102),
        f'<text x="30" y="{h - 14}" font-family="sans-serif" font-size="13" fill="{MUTED}">'
        f"Nothing leaves the gate without a verdict: accepted + quarantined = {total:,}</text>",
    ]
    return "".join(parts) + "</svg>"


def reasons(ns: dict) -> str:
    """Records per reason code, coloured by the action each reason calls for."""
    summary = ns["summary"].sort_values("records")
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    colours = [ACTION_COLOUR[a] for a in summary["action"]]
    ax.barh(summary["code"], summary["records"], color=colours)
    for y, n in enumerate(summary["records"]):
        ax.text(n * 1.08, y, f"{n:,}", va="center", fontsize=11, color=INK)
    ax.set_xscale("log")
    ax.set_xlim(10, 30_000)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel(f"records with this reason (log scale; {len(ns['results']):,} records in all)")
    ax.spines[["top", "right"]].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in ACTION_COLOUR.values()]
    ax.legend(handles, ["reject", "fix (Module 7)", "warn"], frameon=False, loc="lower right")
    fig.tight_layout()
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None})
    plt.close(fig)
    return buffer.getvalue()


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    ns = lesson_namespace()
    figures = {"validation-gate": validation_gate, "reasons": reasons}
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(ns), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
