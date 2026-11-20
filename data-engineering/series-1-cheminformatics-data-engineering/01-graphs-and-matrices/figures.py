"""Draw the figures of Module 1 (figures/*.svg) from the same molecules as the lesson.

Usage (from the series folder):
    uv run python 01-graphs-and-matrices/figures.py

Every figure is drawn by RDKit or built from RDKit's own coordinates and matrices, so the pictures
show exactly what the code does. The SVGs are committed, so the course site builds without RDKit.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for figurekit
from figurekit import ASPIRIN, ELEMENT, INK, MUTED, options  # noqa: E402

OUT = Path(__file__).parent / "figures"


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


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    figures = {
        "aspirin-atoms": aspirin_atoms,
        "aspirin-graph": aspirin_graph,
        "aspirin-adjacency": aspirin_adjacency,
    }
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
