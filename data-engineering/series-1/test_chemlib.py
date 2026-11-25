"""The teaching library generator: valid molecules, the same every time, defects on record."""

import numpy as np
import pytest
from rdkit import Chem, RDLogger

import chemlib

RDLogger.DisableLog("rdApp.*")


def test_every_scaffold_and_substituent_gives_a_valid_molecule():
    for scaffold in chemlib.SCAFFOLDS:
        for sub in chemlib.SUBSTITUENTS:
            smiles = chemlib._fill(scaffold, [sub] * chemlib._slots(scaffold))
            assert Chem.MolFromSmiles(smiles) is not None, smiles


def test_random_molecules_are_valid():
    rng = np.random.default_rng(0)
    for i in rng.choice(chemlib.size(), 2000, replace=False):
        assert Chem.MolFromSmiles(chemlib.smiles_at(int(i))) is not None


def test_the_same_library_on_every_run():
    a, b = chemlib.library(500, seed=3), chemlib.library(500, seed=3)
    pd_equal = a.equals(b)
    assert pd_equal and a["id"].is_unique
    assert not a.equals(chemlib.library(500, seed=4))


def test_stream_matches_numbering():
    first = next(chemlib.stream(10, batch=4))
    assert list(first["smiles"]) == [chemlib.smiles_at(i) for i in range(4)]
    assert sum(len(b) for b in chemlib.stream(10, batch=4)) == 10


@pytest.mark.parametrize("kind", list(chemlib.DEFECTS))
def test_defects_are_what_they_say(kind):
    dirty = chemlib.add_defects(chemlib.library(1200, seed=5), rate=0.1, seed=6)
    rows = dirty[dirty["defect"] == kind]
    assert len(rows) > 0
    for smiles in rows["smiles"]:
        mol = Chem.MolFromSmiles(smiles)
        if kind in ("invalid", "valence"):
            assert mol is None, smiles
        elif kind in ("salt", "solvent"):
            assert mol is not None and len(Chem.GetMolFrags(mol)) == 2, smiles
        elif kind == "element":
            assert mol is not None and any(a.GetSymbol() == "Se" for a in mol.GetAtoms()), smiles
        elif kind == "duplicate":
            original = dirty[dirty["id"] == rows[rows["smiles"] == smiles]["id"].iloc[0][:-4]]
            canon = Chem.MolToSmiles(mol)
            assert canon == Chem.MolToSmiles(Chem.MolFromSmiles(original["smiles"].iloc[0]))
    clean = dirty[dirty["defect"] == ""]
    assert all(Chem.MolFromSmiles(s) is not None for s in clean["smiles"])


def test_parts_at_rebuilds_every_molecule_and_first_index_starts_each_scaffold():
    for scaffold in range(len(chemlib.SCAFFOLDS)):
        start = chemlib.first_index(scaffold)
        for index in (start, start + 1, start + 777):
            number, picks = chemlib.parts_at(index)
            assert number == scaffold
            assert len(picks) == chemlib.SCAFFOLDS[scaffold].count("{")
            subs = [chemlib.SUBSTITUENTS[r] for r in picks]
            assert chemlib._fill(chemlib.SCAFFOLDS[number], subs) == chemlib.smiles_at(index)
    assert chemlib.first_index(0) == 0
