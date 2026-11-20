"""Draw the figures of Module 1 (figures/*.svg) from the same molecules as the lesson.

Usage (from the series folder):
    uv run python 01-representing-molecules/figures.py

Every figure is drawn by RDKit or built from RDKit's own 2D coordinates, so the pictures show
exactly what the code does. The SVGs are committed, so the course site can be built without RDKit.
"""

from __future__ import annotations

from pathlib import Path

from rdkit import Chem, DataStructs
from rdkit.Chem import Draw, rdDepictor, rdFingerprintGenerator
from rdkit.Chem.Draw import rdMolDraw2D

OUT = Path(__file__).parent / "figures"
INK, VIOLET, CYAN, MUTED = "#1d2130", "#7c5cf0", "#0e9fb5", "#8b91a1"
ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
ELEMENT = {"C": "#3a3f52", "O": "#d6336c", "N": "#2f6fdf"}


def options(d: rdMolDraw2D.MolDraw2DSVG) -> None:
    """Common drawing options: a clean white card, readable type.

    Args:
        d: The drawer to configure.
    """
    o = d.drawOptions()
    o.bondLineWidth = 2
    o.minFontSize = 14
    o.padding = 0.08
    o.clearBackground = True


def aspirin_atoms() -> str:
    """Aspirin with every atom numbered, as RDKit reads it."""
    mol = Chem.MolFromSmiles(ASPIRIN)
    rdDepictor.Compute2DCoords(mol)
    d = rdMolDraw2D.MolDraw2DSVG(560, 360)
    options(d)
    d.drawOptions().addAtomIndices = True
    d.DrawMolecule(mol)
    d.FinishDrawing()
    return d.GetDrawingText()


def aspirin_graph() -> str:
    """Aspirin as a graph on RDKit's own coordinates: atoms as circles, bonds as lines."""
    mol = Chem.MolFromSmiles(ASPIRIN)
    rdDepictor.Compute2DCoords(mol)
    pos = mol.GetConformer().GetPositions()
    xs, ys = pos[:, 0], pos[:, 1]
    w, h, pad = 560, 360, 46
    sx = (w - 2 * pad) / (xs.max() - xs.min())
    sy = (h - 2 * pad) / (ys.max() - ys.min())
    s = min(sx, sy)
    ox = (w - s * (xs.max() - xs.min())) / 2
    oy = (h - s * (ys.max() - ys.min())) / 2

    def xy(i: int) -> tuple[float, float]:
        return ox + s * (xs[i] - xs.min()), h - (oy + s * (ys[i] - ys.min()))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" '
             f'height="{h}"><rect width="{w}" height="{h}" fill="#ffffff"/>']  # fmt: skip
    for b in mol.GetBonds():
        (x1, y1), (x2, y2) = xy(b.GetBeginAtomIdx()), xy(b.GetEndAtomIdx())
        order = b.GetBondTypeAsDouble()
        width = {1.0: 2.5, 1.5: 5, 2.0: 7}.get(order, 2.5)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#c4c8d4" '
            f'stroke-width="{width}" stroke-linecap="round"/>'
        )
    for a in mol.GetAtoms():
        x, y = xy(a.GetIdx())
        fill = ELEMENT.get(a.GetSymbol(), INK)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" fill="{fill}"/>'
            f'<text x="{x:.1f}" y="{y + 1:.1f}" font-family="sans-serif" font-size="13" '
            f'font-weight="600" fill="#fff" text-anchor="middle" '
            f'dominant-baseline="middle">{a.GetSymbol()}{a.GetIdx()}</text>'
        )
    legend = [
        ("node = atom (element + index)", INK),
        ("edge = bond; thicker = higher order", MUTED),
    ]
    for k, (label, colour) in enumerate(legend):
        parts.append(f'<text x="16" y="{h - 34 + 18 * k}" font-family="sans-serif" font-size="13" '
                     f'fill="{colour}">{label}</text>')  # fmt: skip
    return "".join(parts) + "</svg>"


def aspirin_adjacency() -> str:
    """Aspirin's adjacency matrix as a grid, coloured by bond order, from RDKit's own matrix."""
    mol = Chem.MolFromSmiles(ASPIRIN)
    orders = Chem.GetAdjacencyMatrix(mol, useBO=True)
    labels = [f"{a.GetSymbol()}{a.GetIdx()}" for a in mol.GetAtoms()]
    n, cell, left, top = len(labels), 30, 56, 48
    colour = {1.0: "#b7a6f6", 1.5: "#7c5cf0", 2.0: "#3f1fb8"}
    w, h = left + n * cell + 210, top + n * cell + 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]
    for k, label in enumerate(labels):
        fill = ELEMENT.get(label[0], INK)
        parts.append(
            f'<text x="{left - 8}" y="{top + k * cell + 20}" font-family="sans-serif" '
            f'font-size="12" text-anchor="end" fill="{fill}">{label}</text>'
            f'<text x="{left + k * cell + 15}" y="{top - 10}" font-family="sans-serif" '
            f'font-size="12" text-anchor="middle" fill="{fill}">{label}</text>'
        )
    for i in range(n):
        for j in range(n):
            fill = colour.get(float(orders[i][j]), "#f1f2f6")
            parts.append(
                f'<rect x="{left + j * cell + 1}" y="{top + i * cell + 1}" width="{cell - 2}" '
                f'height="{cell - 2}" rx="3" fill="{fill}"/>'
            )
    key = [("single bond", 1.0), ("aromatic bond", 1.5), ("double bond", 2.0)]
    kx = left + n * cell + 24
    for k, (label, order) in enumerate(key):
        parts.append(
            f'<rect x="{kx}" y="{top + 8 + k * 26}" width="16" height="16" rx="3" '
            f'fill="{colour[order]}"/><text x="{kx + 24}" y="{top + 21 + k * 26}" '
            f'font-family="sans-serif" font-size="13" fill="{INK}">{label}</text>'
        )
    parts.append(
        f'<rect x="{kx}" y="{top + 86}" width="16" height="16" rx="3" fill="#f1f2f6"/>'
        f'<text x="{kx + 24}" y="{top + 99}" font-family="sans-serif" font-size="13" '
        f'fill="{INK}">not bonded</text>'
        f'<text x="{kx}" y="{top + 136}" font-family="sans-serif" font-size="12" '
        f'fill="{MUTED}">{n} x {n} = {n * n} cells,</text>'
        f'<text x="{kx}" y="{top + 152}" font-family="sans-serif" font-size="12" '
        f'fill="{MUTED}">{mol.GetNumBonds()} bonds, each in 2 cells</text>'
    )
    return "".join(parts) + "</svg>"


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
        "aspirin-atoms": aspirin_atoms,
        "aspirin-graph": aspirin_graph,
        "aspirin-adjacency": aspirin_adjacency,
        "ibuprofen-enantiomers": ibuprofen_enantiomers,
        "smarts-acid": smarts_acid,
        "fingerprint-bits": fingerprint_bits,
    }
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
