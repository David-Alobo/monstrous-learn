"""Draw the figures of Module 8 (figures/*.svg): which checks fired when, and the drift by week.

Usage (from the series folder, after running the lesson: both figures read its monitoring tables):
    uv run python 08-observability/figures.py

The SVGs are committed, so the course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("svg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for diagrams
from diagrams import CYAN, MUTED, ORANGE, VIOLET, Diagram

OUT = Path(__file__).parent / "figures"
WAREHOUSE = Path(__file__).parent / "work" / "lab.duckdb"
CHECKS = ["freshness", "volume", "schema", "registrations", "drift"]
WEEKS = range(5, 13)


def read(sql: str) -> list[tuple]:
    """Rows of a query on the lesson's warehouse, read-only.

    Args:
        sql: The query.

    Returns:
        The rows.
    """
    with duckdb.connect(str(WAREHOUSE), read_only=True) as db:
        return db.sql(sql).fetchall()


def alerts_grid() -> Diagram:
    """A grid of weeks and checks: a filled cell where a check raised an alert that week."""
    found: dict[tuple[int, str], int] = {}
    for week, check, n in read(
        "SELECT week, check_name, count(*) FROM monitoring.alerts GROUP BY ALL"
    ):
        found[(week, check)] = n
    d = Diagram(760, 330)
    d.text(20, 30, "Which checks raised an alert, week by week (weeks 5 to 12)", 16, weight="600")
    left, top, cw, ch = 150, 60, 70, 40
    for i, week in enumerate(WEEKS):
        d.text(left + i * cw + cw / 2, top - 8, f"week {week}", 12, MUTED, "middle")
    for j, check in enumerate(CHECKS):
        y = top + j * ch
        d.text(left - 12, y + 25, check, 13, anchor="end", weight="600")
        for i, week in enumerate(WEEKS):
            x = left + i * cw
            n = found.get((week, check), 0)
            fill = ORANGE if n else "#f4f5f8"
            d.parts.append(f'<rect x="{x + 3}" y="{y + 3}" width="{cw - 6}" height="{ch - 6}" '
                           f'rx="6" fill="{fill}"/>')  # fmt: skip
            if n:
                d.text(x + cw / 2, y + 25, str(n), 13, "#ffffff", "middle", "600")
    notes = ["5: units renamed", "7: LAB-0042", "8: re-read plate", "10: late file",
             "11: late file + drift", "12: drift"]  # fmt: skip
    d.text(20, top + 5 * ch + 30, "What they were: " + "; ".join(notes) + ".", 12, MUTED)
    d.text(20, top + 5 * ch + 50, "Weeks 6 and 9 were quiet: a check that fires only when "
           "something happened is a check people keep reading.", 12, MUTED)  # fmt: skip
    return d


def drift_chart() -> None:
    """The three drift measures by week, with the limit at which the check alerts."""
    rows = read("SELECT week, name, value FROM monitoring.metrics "
                "WHERE name LIKE 'drift_%' ORDER BY week")  # fmt: skip
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    styles = {"drift_clogp": ("cLogP", VIOLET, "o"), "drift_mw": ("molecular weight", CYAN, "s"),
              "drift_heavy_atoms": ("heavy atoms", ORANGE, "^")}  # fmt: skip
    for name, (label, colour, marker) in styles.items():
        points = [(w, v) for w, n, v in rows if n == name]
        ax.plot([p[0] for p in points], [p[1] for p in points], marker=marker, color=colour,
                label=label, linewidth=2)  # fmt: skip
    ax.axhline(1.0, color=MUTED, linestyle="--", linewidth=1.2)
    ax.text(6.0, 1.05, "alert above this line (DRIFT_LIMIT = 1.0)", color=MUTED, fontsize=9)
    ax.axhline(0.0, color="#d8dbe2", linewidth=1)
    ax.set_xticks(list(WEEKS))
    ax.set_xlabel("week registered")
    ax.set_ylabel("move from the baseline\n(baseline standard deviations)")
    ax.set_title("This week's compounds against weeks 1 to 4: the new chemist arrives in week 11",
                 fontsize=11, loc="left")  # fmt: skip
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "drift.svg")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    alerts_grid().save(OUT / "alerts-by-week.svg")
    drift_chart()
    print("wrote figures/alerts-by-week.svg and figures/drift.svg")
