"""Draw the figures of Module 2 (figures/*.svg) from the same molecules as the lesson.

Usage (from the series folder):
    uv run python 02-text-patterns-and-numbers/figures.py

Every figure is drawn by RDKit or built from RDKit's own fingerprints, so the pictures
show exactly what the code does. The SVGs are committed, so the course site builds without RDKit.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdkit import Chem, DataStructs
from rdkit.Chem import Draw, rdFingerprintGenerator
from rdkit.Chem.Draw import rdMolDraw2D

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for figurekit
from figurekit import ASPIRIN, CYAN, INK, MUTED, VIOLET, options  # noqa: E402

OUT = Path(__file__).parent / "figures"


def ibuprofen_enantiomers() -> str:
    """The two enantiomers of ibuprofen, with RDKit's own R/S labels."""
    smiles = ["CC(C)Cc1ccc(cc1)[C@H](C)C(=O)O", "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O"]
    mols = [Chem.MolFromSmiles(s) for s in smiles]
    d = rdMolDraw2D.MolDraw2DSVG(720, 300, 360, 300)
    options(d)
    d.drawOptions().addStereoAnnotation = True
    d.DrawMolecules(mols, legends=["(S)-ibuprofen", "(R)-ibuprofen"])
    d.FinishDrawing()
    return d.GetDrawingText()


def smarts_acid() -> str:
    """Four molecules with the carboxylic-acid SMARTS match highlighted (none in the ester)."""
    names = ["aspirin", "salicylic acid", "methyl salicylate", "ibuprofen"]
    smiles = [ASPIRIN, "O=C(O)c1ccccc1O", "COC(=O)c1ccccc1O", "CC(C)Cc1ccc(cc1)[C@H](C)C(=O)O"]
    acid = Chem.MolFromSmarts("[CX3](=O)[OX2H1]")
    mols = [Chem.MolFromSmiles(s) for s in smiles]
    hits = [list(m.GetSubstructMatch(acid)) for m in mols]
    legends = [
        f"{n}: {'acid' if h else 'no acid (ester)'}" for n, h in zip(names, hits, strict=True)
    ]
    return Draw.MolsToGridImage(mols, molsPerRow=2, subImgSize=(360, 260), legends=legends,
                                highlightAtomLists=hits, useSVG=True)  # fmt: skip


def fingerprint_bits() -> str:
    """The Morgan bits of aspirin and salicylic acid, with the bits they share marked."""
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    a = gen.GetFingerprint(Chem.MolFromSmiles(ASPIRIN))
    b = gen.GetFingerprint(Chem.MolFromSmiles("O=C(O)c1ccccc1O"))
    on_a, on_b = set(a.GetOnBits()), set(b.GetOnBits())
    shared = on_a & on_b
    w, h, left, top = 760, 230, 150, 36
    bar = (w - left - 20) / 2048

    def row(y: float, on: set[int], label: str) -> str:
        cells = "".join(
            f'<rect x="{left + i * bar:.2f}" y="{y}" width="3" height="40" '
            f'fill="{VIOLET if i in shared else CYAN}"/>'
            for i in sorted(on)
        )
        return (f'<rect x="{left}" y="{y}" width="{w - left - 20}" height="40" fill="#f1f2f6"/>'
                f'{cells}<text x="12" y="{y + 25}" font-family="sans-serif" font-size="14" '
                f'fill="{INK}">{label}</text>')  # fmt: skip

    t = DataStructs.TanimotoSimilarity(a, b)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>'
        f'<text x="{left}" y="22" font-family="sans-serif" font-size="13" fill="{MUTED}">'
        f"2048 bits, bit 0 on the left; each coloured mark is a bit that is on</text>"
        + row(top, on_a, f"aspirin ({len(on_a)})")
        + row(top + 60, on_b, f"salicylic acid ({len(on_b)})")
        + f'<rect x="{left}" y="{top + 128}" width="12" height="12" fill="{VIOLET}"/>'
        f'<text x="{left + 18}" y="{top + 139}" font-family="sans-serif" font-size="13" '
        f'fill="{INK}">in both ({len(shared)})</text>'
        f'<rect x="{left + 140}" y="{top + 128}" width="12" height="12" fill="{CYAN}"/>'
        f'<text x="{left + 158}" y="{top + 139}" font-family="sans-serif" font-size="13" '
        f'fill="{INK}">in one only</text>'
        f'<text x="{left}" y="{top + 172}" font-family="sans-serif" font-size="14" fill="{INK}">'
        f"Tanimoto similarity = {len(shared)} shared / {len(on_a | on_b)} in either = {t:.2f}"
        f"</text></svg>"
    )


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    figures = {
        "ibuprofen-enantiomers": ibuprofen_enantiomers,
        "smarts-acid": smarts_acid,
        "fingerprint-bits": fingerprint_bits,
    }
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
