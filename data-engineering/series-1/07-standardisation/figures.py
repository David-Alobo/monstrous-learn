"""Draw the figures of Module 7 (figures/*.svg) from the lesson's own code and results.

Usage (from the series folder):
    uv run python 07-standardisation/figures.py

The script runs the lesson's code (as the tests do) and draws from its results, so the molecules
in the pictures are exactly what the code produces. The SVGs are committed, so the course site
builds without RDKit.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import Draw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))  # the series folder, for figurekit, lessonkit and chemlib
import lessonkit  # noqa: E402
from figurekit import CYAN, INK, MUTED, VIOLET  # noqa: E402

OUT = HERE / "figures"


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


def before_after(ns: dict) -> str:
    """Pairs of records from the lesson's run: as received, and their standard form."""
    changed = ns["changed"]
    picks = [
        changed[changed["id"].str.startswith("ML-") & changed["input_smiles"].str.endswith(".Cl")],
        changed[changed["id"].str.startswith("ML-") & changed["input_smiles"].str.endswith(".CCO")],
        changed[changed["changed_by"] == "parent,uncharge"],
        changed[changed["input_smiles"].str.endswith(".O=C(O)C(F)(F)F")],
    ]
    labels = ["hydrochloride", "ethanol solvate", "ionic hydrochloride", "TFA salt"]
    mols, legends = [], []
    for rows, label in zip(picks, labels, strict=True):
        row = rows.iloc[0]
        mols += [Chem.MolFromSmiles(row["input_smiles"]), Chem.MolFromSmiles(row["smiles"])]
        legends += [f"{row['id']}: {label}, as received", f"standard form ({row['changed_by']})"]
    return Draw.MolsToGridImage(mols, molsPerRow=2, subImgSize=(380, 250), legends=legends,
                                useSVG=True)  # fmt: skip


def box(x: float, y: float, w: float, h: float, lines: list[str], stroke: str) -> str:
    """A rounded box with a bold first line and plain lines under it, all centred."""
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#ffffff" '
             f'stroke="{stroke}" stroke-width="1.8"/>']  # fmt: skip
    top = y + h / 2 - 9 * (len(lines) - 1)
    for k, line in enumerate(lines):
        weight = "600" if k == 0 else "400"
        size = 15 if k == 0 else 12.5
        parts.append(
            f'<text x="{x + w / 2}" y="{top + 18 * k + 5}" font-family="sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{INK}" text-anchor="middle">'
            f"{line}</text>"
        )
    return "".join(parts)


def arrow(x1: float, y: float, x2: float) -> str:
    """A horizontal arrow."""
    return (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{INK}" stroke-width="1.6" '
            f'marker-end="url(#head)"/>')  # fmt: skip


def steps(ns: dict) -> str:
    """The standardisation steps in order, with the configuration recorded beside the output."""
    w, h = 970, 280
    width, gap, y, bh = 136, 22, 70, 120
    boxes = [
        (["Input record", "as received", "e.g. a salt"], MUTED),
        (["1. Clean-up", "normalisation", "rules"], VIOLET),
        (["2. Parent", "largest organic", "fragment"], VIOLET),
        (["3. Uncharge", "neutralise by", "adding or removing H"], VIOLET),
        (["4. Tautomer", "one canonical", "tautomer (optional)"], MUTED),
        (["Output", "canonical SMILES", "InChIKey"], CYAN),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
        f'markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>'
        f"</defs>",
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="20" y="36" font-family="sans-serif" font-size="15" font-weight="600" '
        f'fill="{INK}">standardise(smiles, options): one pure function, steps in a fixed order'
        f"</text>",
    ]
    for k, (lines, colour) in enumerate(boxes):
        x = 20 + k * (width + gap)
        parts.append(box(x, y, width, bh, lines, colour))
        if k < len(boxes) - 1:
            parts.append(arrow(x + width + 2, y + bh / 2, x + width + gap - 2))
    options = ns["DEFAULT"]
    on = ", ".join(f"{k}={v}" for k, v in options._asdict().items())
    parts.append(
        f'<text x="20" y="232" font-family="sans-serif" font-size="13" fill="{MUTED}">'
        f"Options (immutable): {on}</text>"
        f'<text x="20" y="256" font-family="sans-serif" font-size="13" fill="{MUTED}">'
        f"Recorded with every output: input SMILES, steps that changed it, rules version "
        f"{ns['RULES_VERSION']}, configuration hash {ns['config_hash'](options)}</text>"
    )
    return "".join(parts) + "</svg>"


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    ns = lesson_namespace()
    figures = {"before-after": before_after, "standardisation-steps": steps}
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(ns), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
