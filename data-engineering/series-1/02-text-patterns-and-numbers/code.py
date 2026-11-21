"""Molecules as text, patterns and numbers: the code of the lesson, in order.

SMILES, InChI, molfiles, conformers, SMARTS, fingerprints and descriptors: what each keeps and loses, and which to store for which job.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/02-text-patterns-and-numbers/
Run it from anywhere, e.g. from the series folder: uv run python 02-text-patterns-and-numbers/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]

# ---- Setup ----
import logging

import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem, Descriptors, rdFingerprintGenerator

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# conformers (section 5): how many to generate, and the random seed that makes them repeatable
N_CONFORMERS = 5
CONFORMER_SEED = 42
# Morgan fingerprints (section 7): radius 2 is ECFP4-like; 2048 bits is a common length
MORGAN_RADIUS = 2
MORGAN_BITS = 2048
aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")

# ---- 1. SMILES: one molecule, many strings ----
for smiles in ["OCC", "CCO", "C(O)C", "[CH3][CH2][OH]"]:
    canonical = Chem.MolToSmiles(Chem.MolFromSmiles(smiles))
    print(f"{smiles:16} -> {canonical}")
benzene = Chem.MolFromSmiles("C1=CC=CC=C1")
print("as read:   ", Chem.MolToSmiles(benzene))
Chem.Kekulize(benzene, clearAromaticFlags=True)
print("kekulised: ", Chem.MolToSmiles(benzene))

# ---- 2. What a representation can lose: stereochemistry ----
s_ibuprofen = Chem.MolFromSmiles("CC(C)Cc1ccc(cc1)[C@H](C)C(=O)O")
r_ibuprofen = Chem.MolFromSmiles("CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O")
print("S:", Chem.FindMolChiralCenters(s_ibuprofen), Chem.MolToSmiles(s_ibuprofen))
print("R:", Chem.FindMolChiralCenters(r_ibuprofen), Chem.MolToSmiles(r_ibuprofen))
def flat(mol: Chem.Mol) -> str:
    """Canonical SMILES with the stereochemistry left out."""
    return Chem.MolToSmiles(mol, isomericSmiles=False)


print("isomeric SMILES equal:", Chem.MolToSmiles(s_ibuprofen) == Chem.MolToSmiles(r_ibuprofen))
print("flat SMILES equal:    ", flat(s_ibuprofen) == flat(r_ibuprofen))
print("flat:", flat(s_ibuprofen))

# ---- 3. InChI and InChIKey: an identity for every molecule ----
print(Chem.MolToInchi(aspirin))
print(Chem.MolToInchiKey(aspirin))
for name, mol in [("S", s_ibuprofen), ("R", r_ibuprofen)]:
    key = Chem.MolToInchiKey(mol)
    print(name, key, "  skeleton:", key[:14])
pyridone = Chem.MolFromSmiles("O=c1cccc[nH]1")
hydroxypyridine = Chem.MolFromSmiles("Oc1ccccn1")
print("SMILES equal:  ", Chem.MolToSmiles(pyridone) == Chem.MolToSmiles(hydroxypyridine))
print("InChIKey equal:", Chem.MolToInchiKey(pyridone) == Chem.MolToInchiKey(hydroxypyridine))

# ---- 4. Molfiles and SDF: the connection table ----
ethanol = Chem.MolFromSmiles("CCO")
print(Chem.MolToMolBlock(ethanol))

# ---- 5. Three dimensions: conformers ----
with_h = Chem.AddHs(aspirin)
ids = AllChem.EmbedMultipleConfs(with_h, numConfs=N_CONFORMERS, randomSeed=CONFORMER_SEED)
print(len(ids), "conformers of", with_h.GetNumAtoms(), "atoms (hydrogens included)")
print(
    "same atoms, different coordinates:",
    with_h.GetConformer(0).GetAtomPosition(0).x != with_h.GetConformer(1).GetAtomPosition(0).x,
)

# ---- 6. SMARTS: patterns, not molecules ----
library = {
    "aspirin": aspirin,
    "salicylic acid": Chem.MolFromSmiles("O=C(O)c1ccccc1O"),
    "methyl salicylate": Chem.MolFromSmiles("COC(=O)c1ccccc1O"),
    "ibuprofen": s_ibuprofen,
}
as_molecule = Chem.MolFromSmiles("C(=O)O")
acid = Chem.MolFromSmarts("[CX3](=O)[OX2H1]")
for name, mol in library.items():
    print(
        f"{name:18} C(=O)O as a molecule: {mol.HasSubstructMatch(as_molecule)!s:5}  "
        f"acid SMARTS: {mol.HasSubstructMatch(acid)}"
    )

# ---- 7. Fingerprints: molecules as bits ----
morgan = rdFingerprintGenerator.GetMorganGenerator(radius=MORGAN_RADIUS, fpSize=MORGAN_BITS)
fingerprints = {name: morgan.GetFingerprint(mol) for name, mol in library.items()}
print("bits set in aspirin:", fingerprints["aspirin"].GetNumOnBits(), "of", MORGAN_BITS)
for name in ["salicylic acid", "methyl salicylate", "ibuprofen"]:
    similarity = DataStructs.TanimotoSimilarity(fingerprints["aspirin"], fingerprints[name])
    print(f"Tanimoto similarity, aspirin and {name}: {similarity:.2f}")

# ---- 8. Descriptors: molecules as numbers ----
print(f"{'molecule':18}{'MW':>8}{'logP':>7}{'TPSA':>7}{'HBD':>5}")
for name, mol in library.items():
    print(
        f"{name:18}{Descriptors.MolWt(mol):8.1f}{Descriptors.MolLogP(mol):7.2f}"
        f"{Descriptors.TPSA(mol):7.1f}{Descriptors.NumHDonors(mol):5d}"
    )

# ---- 9. What to store, for which job ----
rows = []
for name, mol in library.items():
    rows.append(
        {
            "name": name,
            "inchikey": Chem.MolToInchiKey(mol),
            "smiles": Chem.MolToSmiles(mol),
            "mw": round(Descriptors.MolWt(mol), 2),
        }
    )
compounds = pd.DataFrame(rows)
print(compounds.to_string(index=False))
