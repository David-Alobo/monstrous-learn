"""Shared drawing settings for the figures of every module in this series."""

from __future__ import annotations

from rdkit.Chem.Draw import rdMolDraw2D

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
