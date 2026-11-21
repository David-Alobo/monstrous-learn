"""Draw the figures of Module 5 (figures/*.svg) with the lesson's own drawing helper.

Usage (from the series folder):
    uv run python 05-graphs-and-graph-databases/figures.py

The two pictures are what the lesson's "Seeing the molecules" blocks draw from Neo4j's answers:
everything phenol leads to, and the route from phenol to aspirin. Their content is written out here
(the same compounds, steps and reactions as the lesson's network), so the figures can be drawn
without Neo4j. The screenshot figures/neo4j-network.png was taken from Neo4j Browser by hand. The
SVGs are committed, so the course site builds without running anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))  # this module's folder, for drawing.py
from drawing import grid_svg, scheme_svg  # noqa: E402

OUT = HERE / "figures"

# what phenol leads to, as the lesson's reachability query returns it: (name, SMILES, steps)
FROM_PHENOL = [
    ("4-nitrophenol", "O=[N+]([O-])c1ccc(O)cc1", 1),
    ("salicylic acid", "O=C(O)c1ccccc1O", 1),
    ("4-aminophenol", "Nc1ccc(O)cc1", 2),
    ("aspirin", "CC(=O)Oc1ccccc1C(=O)O", 2),
    ("methyl salicylate", "COC(=O)c1ccccc1O", 2),
    ("paracetamol", "CC(=O)Nc1ccc(O)cc1", 3),
]
# the route from phenol to aspirin, as the lesson's route query returns it
ROUTE_ASPIRIN = [
    {"compound": "phenol", "smiles": "Oc1ccccc1"},
    {"reaction": "Kolbe-Schmitt carboxylation", "with": ["carbon dioxide"]},
    {"compound": "salicylic acid", "smiles": "O=C(O)c1ccccc1O"},
    {"reaction": "acetylation of salicylic acid", "with": ["acetic anhydride"]},
    {"compound": "aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
]


def main() -> None:
    """Write both figures."""
    OUT.mkdir(exist_ok=True)
    grid = grid_svg([(s, f"{n} ({k} step{'s' if k > 1 else ''})") for n, s, k in FROM_PHENOL])
    (OUT / "from-phenol.svg").write_text(grid, encoding="utf-8")
    (OUT / "route-aspirin.svg").write_text(scheme_svg(ROUTE_ASPIRIN), encoding="utf-8")


if __name__ == "__main__":
    main()
