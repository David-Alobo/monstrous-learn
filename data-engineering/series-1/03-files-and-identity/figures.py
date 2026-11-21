"""Draw the figures of Module 3 (figures/*.svg) from the same library and code as the lesson.

Usage (from the series folder):
    uv run python 03-files-and-identity/figures.py

The file sizes are measured by writing the lesson's library in each format to a temporary folder;
the molecules are drawn by RDKit, and the canonical SMILES come from RDKit and Open Babel
themselves. The SVGs are committed, so the course site builds without RDKit.
"""

from __future__ import annotations

import gzip
import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib
import pyarrow as pa
import pyarrow.parquet as pq
from openbabel import pybel
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1]))  # the series folder, for chemlib and figurekit
import chemlib  # noqa: E402
from figurekit import CYAN, INK, MUTED, VIOLET, options  # noqa: E402

OUT = Path(__file__).parent / "figures"
# the lesson's Setup settings that the figures depend on
LIBRARY_SIZE = 20_000
LIBRARY_SEED = 3
PARQUET_COMPRESSION = "zstd"
TOOLKIT_SAMPLE = 1_000
SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("smiles", pa.string()),
        ("vendor", pa.string()),
        ("price_usd", pa.float64()),
        ("stock_mg", pa.int64()),
    ]
)
# the first pair of symmetric duplicates the lesson finds in the library
DUPLICATE_IDS = ["ML-00868944", "ML-00869234"]
# the lesson reads the first TOOLKIT_SAMPLE molecules with both toolkits and prints the last
TOOLKIT_ROW = TOOLKIT_SAMPLE - 1


def _write_formats(folder: Path) -> dict[str, int]:
    """Write the lesson's library in each format, as the lesson does, and measure each file.

    Args:
        folder: Where to write the files.

    Returns:
        The size of each file in bytes, by format.
    """
    library = chemlib.library(LIBRARY_SIZE, seed=LIBRARY_SEED)
    sdf, smi = folder / "library.sdf", folder / "library.smi"
    csv, parquet = folder / "library.csv", folder / "library.parquet"
    with Chem.SDWriter(str(sdf)) as writer:
        for row in library.itertuples(index=False):
            mol = Chem.MolFromSmiles(row.smiles)
            mol.SetProp("_Name", row.id)
            mol.SetProp("vendor", row.vendor)
            mol.SetProp("price_usd", f"{row.price_usd:.2f}")
            mol.SetProp("stock_mg", str(row.stock_mg))
            writer.write(mol)
    packed = folder / "library.sdf.gz"
    with open(sdf, "rb") as source, gzip.GzipFile(packed, "wb", mtime=0) as target:
        shutil.copyfileobj(source, target)
    with open(smi, "w", encoding="utf-8", newline="\n") as handle:
        for row in library.itertuples(index=False):
            handle.write(f"{row.smiles} {row.id}\n")
    library.to_csv(csv, index=False)
    table = pa.Table.from_pandas(library, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, parquet, compression=PARQUET_COMPRESSION)
    paths = {"SDF": sdf, "SDF (gzip)": packed, "CSV": csv, "SMILES": smi, "Parquet": parquet}
    return {name: path.stat().st_size for name, path in paths.items()}


def file_sizes() -> str:
    """A bar chart of the size on disk of the same 20,000 molecules in each format."""
    with tempfile.TemporaryDirectory() as tmp:
        sizes = _write_formats(Path(tmp))
    names = list(sizes)[::-1]  # largest at the top
    megabytes = [sizes[name] / 1e6 for name in names]
    plt.rcParams.update({"svg.hashsalt": "module-03", "svg.fonttype": "none", "font.size": 12})
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    colours = [VIOLET if name.startswith("SDF") else CYAN for name in names]
    bars = ax.barh(names, megabytes, color=colours)
    for bar, value in zip(bars, megabytes, strict=True):
        ax.text(bar.get_width() + 0.6, bar.get_y() + bar.get_height() / 2, f"{value:.2f} MB",
                va="center", color=INK, fontsize=11)  # fmt: skip
    ax.set_xlabel("Size on disk (MB) of 20,000 molecules", color=INK)
    ax.set_xlim(0, max(megabytes) * 1.2)
    ax.tick_params(colors=INK)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    fig.tight_layout()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "chart.svg"
        fig.savefig(path, format="svg", metadata={"Date": None})
        plt.close(fig)
        return path.read_text(encoding="utf-8")


def duplicate_group() -> str:
    """Two library entries, two IDs and two SMILES, one molecule: one InChIKey."""
    library = chemlib.library(LIBRARY_SIZE, seed=LIBRARY_SEED).set_index("id")
    smiles = [library.at[i, "smiles"] for i in DUPLICATE_IDS]
    mols = [Chem.MolFromSmiles(s) for s in smiles]
    keys = {Chem.MolToInchiKey(m) for m in mols}
    if len(keys) != 1:
        raise ValueError("the two entries are not the same molecule")
    d = rdMolDraw2D.MolDraw2DSVG(840, 360, 420, 300)
    options(d)
    d.DrawMolecules(mols, legends=DUPLICATE_IDS)
    d.FinishDrawing()
    svg = d.GetDrawingText().replace("height='360px'", "height='420px'")
    svg = svg.replace("viewBox='0 0 840 360'", "viewBox='0 0 840 420'")
    lines = [
        (310, 12, MUTED, f"{DUPLICATE_IDS[0]}: {smiles[0]}"),
        (330, 12, MUTED, f"{DUPLICATE_IDS[1]}: {smiles[1]}"),
        (380, 16, VIOLET, f"one InChIKey for both: {keys.pop()}"),
    ]
    text = "".join(
        f"<text x='420' y='{y}' text-anchor='middle' font-family='sans-serif' "
        f"font-size='{size}' fill='{colour}'>{line}</text>"
        for y, size, colour, line in lines
    )
    return svg.replace("</svg>", f"<rect x='0' y='360' width='840' height='60' fill='#ffffff'/>"
                       f"{text}</svg>")  # fmt: skip


def toolkits_one_key() -> str:
    """One molecule: RDKit's and Open Babel's canonical SMILES differ, the InChIKey is one."""
    pybel.ob.obErrorLog.SetOutputLevel(0)
    smiles = chemlib.library(LIBRARY_SIZE, seed=LIBRARY_SEED)["smiles"].iloc[TOOLKIT_ROW]
    mol = Chem.MolFromSmiles(smiles)
    rd = Chem.MolToSmiles(mol)
    ob = pybel.readstring("smi", smiles).write("can").split("\t")[0].strip()
    key_rd = Chem.MolToInchiKey(Chem.MolFromSmiles(rd))
    key_ob = Chem.MolToInchiKey(Chem.MolFromSmiles(ob))
    if key_rd != key_ob:
        raise ValueError("the two canonical SMILES are not the same molecule")
    d = rdMolDraw2D.MolDraw2DSVG(380, 300)
    options(d)
    d.DrawMolecule(mol)
    d.FinishDrawing()
    drawing = d.GetDrawingText().split("\n", 1)[1]  # drop the XML declaration
    drawing = drawing.replace("<svg", "<svg x='0' y='0'", 1)
    w, h = 860, 300

    def label(y: float, size: int, colour: str, text: str, weight: str = "normal") -> str:
        return (f"<text x='400' y='{y}' font-family='sans-serif' font-size='{size}' "
                f"font-weight='{weight}' fill='{colour}'>{text}</text>")  # fmt: skip

    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}'>"
        f"<rect width='{w}' height='{h}' fill='#ffffff'/>"
        f"<g>{drawing}</g>"
        + label(70, 14, MUTED, "RDKit canonical SMILES")
        + label(92, 14, INK, rd)
        + label(132, 14, MUTED, "Open Babel canonical SMILES")
        + label(154, 14, INK, ob)
        + label(204, 14, MUTED, "InChIKey (from either SMILES)")
        + label(228, 17, VIOLET, key_rd, "bold")
        + "</svg>"
    )


def main() -> None:
    """Write every figure."""
    OUT.mkdir(exist_ok=True)
    figures = {
        "file-sizes": file_sizes,
        "duplicate-group": duplicate_group,
        "toolkits-one-key": toolkits_one_key,
    }
    for name, make in figures.items():
        (OUT / f"{name}.svg").write_text(make(), encoding="utf-8", newline="\n")
        print(f"figures/{name}.svg")


if __name__ == "__main__":
    main()
