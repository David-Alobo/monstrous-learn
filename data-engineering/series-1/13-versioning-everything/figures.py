"""Draw the figures of Module 13 (figures/*.svg): what gets versioned, and a provenance record.

Usage (from the series folder):
    uv run python 13-versioning-everything/figures.py

Both figures are diagrams of the ideas in the lesson, drawn as plain SVG. The field names in the
provenance record are the ones the lesson's write_with_provenance() writes. The SVGs are
committed, so the course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for figurekit
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

OUT = Path(__file__).parent / "figures"
FONT = 'font-family="sans-serif"'
PALE_VIOLET, PALE_CYAN, PALE = "#ece7fd", "#e0f4f7", "#f1f2f6"


def start(w: int, h: int) -> list[str]:
    """The opening of an SVG with a white card and an arrow head.

    Args:
        w: Width.
        h: Height.

    Returns:
        The first SVG elements.
    """
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>'
        f"</defs>",
    ]


def box(x: float, y: float, w: float, h: float, lines: list[str], fill: str) -> str:
    """A rounded box with centred lines of text, the first in bold.

    Args:
        x: Left edge.
        y: Top edge.
        w: Width.
        h: Height.
        lines: The text, one entry per line.
        fill: The box colour.

    Returns:
        The SVG elements.
    """
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}"/>']
    top = y + h / 2 - (len(lines) - 1) * 9
    for k, line in enumerate(lines):
        weight = "600" if k == 0 else "400"
        parts.append(
            f'<text x="{x + w / 2}" y="{top + 18 * k + 5}" {FONT} font-size="13" '
            f'font-weight="{weight}" fill="{INK}" text-anchor="middle">{line}</text>'
        )
    return "".join(parts)


def arrow(x1: float, y1: float, x2: float, y2: float, dashed: bool = False) -> str:
    """A grey arrow from (x1, y1) to (x2, y2).

    Args:
        x1: Start, x.
        y1: Start, y.
        x2: End, x.
        y2: End, y.
        dashed: Draw it dashed.

    Returns:
        The SVG element.
    """
    dash = ' stroke-dasharray="5,4"' if dashed else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTED}" stroke-width="2"{dash} '
        f'marker-end="url(#head)"/>'
    )


def text(x: float, y: float, words: str, colour: str = MUTED, size: int = 12) -> str:
    """A line of text.

    Args:
        x: Left edge.
        y: Baseline.
        words: The text.
        colour: Its colour.
        size: Font size.

    Returns:
        The SVG element.
    """
    return f'<text x="{x}" y="{y}" {FONT} font-size="{size}" fill="{colour}">{words}</text>'


def what_gets_versioned() -> str:
    """The six things that are versioned, the tool for each, and how they connect."""
    w, h = 900, 430
    parts = start(w, h)
    parts.append(text(20, 30, "In the git repository: one commit pins all of these", VIOLET, 14))
    # the repository, holding code and the small files that pin everything else
    parts.append(
        f'<rect x="20" y="44" width="560" height="250" rx="12" fill="none" stroke="{VIOLET}" '
        f'stroke-width="2" stroke-dasharray="6,4"/>'
    )
    inside = [
        (36, 64, ["code", "commit + tag v1.0.0"]),
        (214, 64, ["environment", "pyproject.toml + uv.lock"]),
        (392, 64, ["data pointers", ".dvc files: md5 + size"]),
        (36, 164, ["standardisation rules", "version + SHA-256"]),
        (214, 164, ["container recipe", "Dockerfile, base @sha256"]),
        (392, 164, ["database schema", "numbered .sql files"]),
    ]
    for x, y, lines in inside:
        parts.append(box(x, y, 172, 70, lines, PALE_VIOLET))
    parts.append(text(40, 270, "git describe names it: v1.0.0, v1.0.0-1-g&lt;commit&gt;, -dirty"))
    # outside the repository: the things the pointers name
    parts.append(text(620, 30, "Outside git, named by hash", CYAN, 14))
    parts.append(box(620, 60, 260, 70, ["data files", "DVC cache and remote (S3, ...)"],
                     PALE_CYAN))  # fmt: skip
    parts.append(box(620, 150, 260, 70, ["database", "schema_migrations: what was applied"],
                     PALE_CYAN))  # fmt: skip
    parts.append(box(620, 240, 260, 70, ["container image", "registry, pulled by digest"],
                     PALE_CYAN))  # fmt: skip
    parts.append(arrow(564, 99, 618, 95))
    parts.append(arrow(564, 199, 618, 185))
    parts.append(arrow(300, 236, 618, 276))
    # the result and its record
    parts.append(box(250, 330, 400, 76, ["result + provenance record", "names the commit, versions,"
                                         " schema, rules hash,", "input hashes and parameters"],
                     PALE))  # fmt: skip
    parts.append(arrow(300, 296, 340, 328, dashed=True))
    parts.append(arrow(750, 312, 610, 330, dashed=True))
    parts.append(text(20, 422, "Dashed: the record refers to them, so the result can be traced"
                      " back and rebuilt."))  # fmt: skip
    return "".join(parts) + "</svg>"


def provenance_record() -> str:
    """A result file, its provenance record, and the inputs the record names by hash."""
    w, h = 900, 430
    parts = start(w, h)
    parts.append(box(20, 160, 180, 76, ["median-price.csv", "the result", "sha256 of its bytes"],
                     PALE))  # fmt: skip
    # the record as a card of fields
    fields = [
        ("result", "file name and sha256"),
        ("code_version", "git describe: v1.0.0-1-g&lt;commit&gt;"),
        ("environment", "python, pandas, numpy, duckdb, dvc"),
        ("schema_version", "max(version) in schema_migrations"),
        ("rules", "version 2.1.0 + sha256"),
        ("inputs", "path -&gt; sha256, for every input file"),
        ("parameters", "min_stock_mg: 100"),
        ("created_utc", "when it ran"),
    ]
    x0, y0, row = 260, 40, 38
    parts.append(
        f'<rect x="{x0}" y="{y0 - 10}" width="380" height="{len(fields) * row + 50}" rx="10" '
        f'fill="{PALE_VIOLET}"/>'
    )
    parts.append(text(x0 + 16, y0 + 14, "median-price.csv.provenance.json", INK, 14))
    for k, (key, value) in enumerate(fields):
        y = y0 + 44 + k * row
        parts.append(text(x0 + 16, y, key, VIOLET, 13))
        parts.append(text(x0 + 130, y, value, INK, 12))
    parts.append(arrow(200, 198, 258, 198))
    # what each field points at
    targets = [
        (1, ["git repository", "the code at that commit"]),
        (3, ["database", "schema_migrations table"]),
        (4, ["standardisation rules", "hashed again and compared"]),
        (5, ["compounds.csv", "hashed again and compared"]),
    ]
    for k, (index, lines) in enumerate(targets):
        y = 30 + k * 88
        parts.append(box(700, y, 190, 64, lines, PALE_CYAN))
        parts.append(arrow(x0 + 380, y0 + 40 + index * row, 698, y + 32, dashed=True))
    parts.append(text(20, 418, "Check: recompute every hash and compare. Rebuild: same code, same"
                      " inputs, same parameters; the result's hash must match."))  # fmt: skip
    return "".join(parts) + "</svg>"


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    figures = {
        "what-gets-versioned": what_gets_versioned,
        "provenance-record": provenance_record,
    }
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
