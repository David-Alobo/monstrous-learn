"""Draw molecules in boxes: a grid of structures, and a synthesis route as a reaction scheme.

Used by Module 5's lesson (after asking Neo4j for the molecules) and by its figures.py. Every
structure is drawn by RDKit in its own square box, with its name underneath, and the result is one
SVG picture (a text format for drawings that browsers, notebooks and documents all show).
"""

from __future__ import annotations

import re
from html import escape

from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D

INK, VIOLET, MUTED = "#1d2130", "#7c5cf0", "#8b91a1"
BOX = 180  # side of a structure's square box, in pixels
CAPTION = 34  # space under the structure for its name
GAP = 24  # space between boxes in a grid
ARROW = 150  # length of a reaction arrow in a scheme
FONT = 'font-family="sans-serif"'


class Picture(str):
    """SVG text that a notebook (Jupyter, Colab) shows as a picture when a cell ends with it."""

    def _repr_svg_(self) -> str:
        """The picture, for the notebook to show.

        Returns:
            The SVG text.
        """
        return str(self)


def _structure(smiles: str, size: int) -> str:
    """RDKit's drawing of one molecule, as SVG elements without the outer <svg> wrapper.

    Args:
        smiles: The molecule.
        size: Width and height of the drawing, in pixels.

    Returns:
        The drawing's SVG elements.
    """
    drawer = rdMolDraw2D.MolDraw2DSVG(size, size)
    options = drawer.drawOptions()
    options.bondLineWidth = 2
    options.minFontSize = 13
    options.padding = 0.12
    options.clearBackground = False  # the box behind it is the background
    drawer.DrawMolecule(Chem.MolFromSmiles(smiles))
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    return re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", svg, flags=re.S)


def _box(smiles: str, name: str, x: float, y: float, accent: str = VIOLET) -> str:
    """One molecule in a square box with rounded corners, its name centred underneath.

    Args:
        smiles: The molecule.
        name: The caption.
        x: Left edge of the box.
        y: Top edge of the box.
        accent: Colour of the box's border.

    Returns:
        The box's SVG elements.
    """
    height = BOX + CAPTION
    return (
        f'<rect x="{x}" y="{y}" width="{BOX}" height="{height}" rx="10" fill="#ffffff" '
        f'stroke="{accent}" stroke-width="2"/>'
        f'<g transform="translate({x},{y})">{_structure(smiles, BOX)}</g>'
        f'<line x1="{x + 12}" y1="{y + BOX}" x2="{x + BOX - 12}" y2="{y + BOX}" stroke="#e3e5ec"/>'
        f'<text x="{x + BOX / 2}" y="{y + BOX + 22}" {FONT} font-size="14" fill="{INK}" '
        f'text-anchor="middle">{escape(name)}</text>'
    )


def _svg(width: float, height: float, body: str) -> Picture:
    """A complete SVG picture with a white background.

    Args:
        width: Width in pixels.
        height: Height in pixels.
        body: The picture's elements.

    Returns:
        The SVG text.
    """
    return Picture(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}"><rect width="{width}" height="{height}" '
        f'fill="#ffffff"/>{body}</svg>'
    )


def grid_svg(molecules: list[tuple[str, str]], columns: int = 3) -> Picture:
    """Several molecules side by side, each in its own box, in rows of `columns`.

    Args:
        molecules: (SMILES, caption) for each molecule, in the order to draw them.
        columns: How many boxes per row.

    Returns:
        The SVG picture.
    """
    rows = -(-len(molecules) // columns)  # rows needed, rounding up
    width = GAP + columns * (BOX + GAP)
    height = GAP + rows * (BOX + CAPTION + GAP)
    body = "".join(
        _box(smiles, caption, GAP + (k % columns) * (BOX + GAP),
             GAP + (k // columns) * (BOX + CAPTION + GAP))
        for k, (smiles, caption) in enumerate(molecules)
    )  # fmt: skip
    return _svg(width, height, body)


def scheme_svg(steps: list[dict]) -> Picture:
    """A synthesis route drawn as a reaction scheme: boxes joined by arrows.

    Args:
        steps: The route in order, alternating compounds and reactions:
            {"compound": name, "smiles": ...}, {"reaction": name, "with": [other reactants]},
            {"compound": ...}, ... The reagents are written above each arrow and the reaction's
            name below it.

    Returns:
        The SVG picture.
    """
    compounds = [s for s in steps if "compound" in s]
    width = GAP + len(compounds) * BOX + (len(compounds) - 1) * ARROW + GAP
    height = GAP + BOX + CAPTION + GAP
    body, x = [], GAP
    for step in steps:
        if "compound" in step:
            body.append(_box(step["smiles"], step["compound"], x, GAP))
            x += BOX
            continue
        y = GAP + BOX / 2
        body.append(
            f'<line x1="{x + 10}" y1="{y}" x2="{x + ARROW - 14}" y2="{y}" stroke="{INK}" '
            f'stroke-width="2"/><path d="M{x + ARROW - 10} {y} l-12 -6 v12 z" fill="{INK}"/>'
        )
        reagents = " + ".join(step["with"])
        if reagents:
            body.append(f'<text x="{x + ARROW / 2}" y="{y - 12}" {FONT} font-size="13" '
                        f'fill="{INK}" text-anchor="middle">{escape(reagents)}</text>')  # fmt: skip
        for k, word in enumerate(_wrap(step["reaction"], 20)):
            body.append(f'<text x="{x + ARROW / 2}" y="{y + 22 + 15 * k}" {FONT} font-size="12" '
                        f'fill="{MUTED}" text-anchor="middle">{escape(word)}</text>')  # fmt: skip
        x += ARROW
    return _svg(width, height, "".join(body))


def _wrap(text: str, width: int) -> list[str]:
    """Split text into lines of at most about `width` characters, at spaces.

    Args:
        text: The text.
        width: The longest line wanted.

    Returns:
        The lines.
    """
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return [*lines, line] if line else lines
