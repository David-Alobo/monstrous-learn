"""Teaching compound libraries for Series 1, made in code: any size, the same on every computer.

Real screening libraries (Enamine REAL, for example) are built by combining building blocks on
scaffolds. This module does the same with a small set of drug-like scaffolds, each with two to four
positions (R1, R2, …) and a list of common substituents for each. Every combination is a valid
molecule, numbered from 0, so a library can be made, sampled or streamed without storing it. As in
real enumerated libraries, a few combinations give the same molecule (about 0.4%, by symmetry).

It also adds the faults real files have, on purpose and on record, so the validation and
standardisation modules have real problems to find (and a record of the truth to check against).

    from chemlib import library, size, stream, add_defects

    size()                          # how many molecules the generator can make
    df = library(10_000, seed=1)    # a sample: id, smiles, vendor, price_usd, stock_mg
    for batch in stream(1_000_000, batch=100_000): ...   # generate as you go, never all at once
    dirty = add_defects(df, rate=0.05, seed=2)            # with a `defect` column saying which

No data is downloaded and nothing is redistributed, so there are no licence questions.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import numpy as np
import pandas as pd

# Substituents as SMILES branches. They use no ring-closure digits below 8, so they can be dropped
# into any scaffold below without clashing with its rings.
SUBSTITUENTS = [
    "[H]", "C", "CC", "C(C)C", "C(F)(F)F", "F", "Cl", "Br", "OC", "OCC", "O", "N(C)C",
    "C#N", "C(=O)N", "C(=O)OC", "S(C)(=O)=O", "c8ccccc8", "c8ccncc8", "c8ccco8", "C8CC8",
    "C8CCOCC8", "N8CCOCC8", "N8CCCC8", "OC(F)(F)F", "CO", "CN", "C(=O)C", "c8ccc(F)cc8",
    "c8cn[nH]c8", "C8CCNCC8",
]  # fmt: skip
# Scaffolds: drug-like cores with numbered positions {1}, {2}, … for the substituents.
SCAFFOLDS = [
    "c1cc({1})ccc1C(=O)NCc2ccc({2})cc2",  # benzamides
    "c1cc({1})ccc1S(=O)(=O)Nc2ccc({2})cc2",  # sulfonamides
    "O=C(Nc1ccc({1})cc1)Nc2ccc({2})nc2",  # ureas
    "c1nc({1})cc(n1)N2CCN(CC2)C(=O)c3ccc({2})cc3",  # pyrimidine piperazines
    "c1cc2c(cc1{1})[nH]c(n2)c3ccc({2})cc3",  # benzimidazoles
    "c1cc({1})c(cc1)Oc2ccc(cc2)C(=O)N({2}){3}",  # diaryl ether amides
    "Cc1nc({1})sc1C(=O)NC({2})c2ccc({3})cc2",  # thiazole amides
    "c1cc({1})ccc1-c2nc({2})c({3})o2",  # oxazoles
    "O=C(c1ccc({1})cc1)N2CCC(CC2){2}",  # piperidine amides
    "c1ccc2c(c1)c({1})cn2C(=O)c3ccc({2})c({3})c3",  # indoles
    "c1c({1})cc(cc1{2})C(=O)NC(C{3})C(=O)N{4}",  # dipeptide-like
    "c1cc({1})c(nc1)Nc2nc({2})c({3})c({4})n2",  # aminopyrimidines
]
VENDORS = ["Vendor A", "Vendor B", "Vendor C"]


def _slots(scaffold: str) -> int:
    """How many substituent positions a scaffold has."""
    return scaffold.count("{")


def _counts() -> list[int]:
    """How many molecules each scaffold gives."""
    return [len(SUBSTITUENTS) ** _slots(s) for s in SCAFFOLDS]


def size() -> int:
    """How many different molecules the generator can make.

    Returns:
        The number of scaffold and substituent combinations.
    """
    return sum(_counts())


def _fill(scaffold: str, picks: list[str]) -> str:
    """A scaffold with its positions filled. "[H]" means "nothing there".

    Args:
        scaffold: A scaffold with positions {1}, {2}, ….
        picks: One substituent per position.

    Returns:
        The SMILES of the molecule.
    """
    smiles = scaffold
    for k, sub in enumerate(picks, start=1):
        smiles = smiles.replace(f"({{{k}}})", "" if sub == "[H]" else f"({sub})")
        smiles = smiles.replace(f"{{{k}}}", "" if sub == "[H]" else sub)
    return smiles


def smiles_at(index: int) -> str:
    """The molecule numbered `index` (0 to size() - 1), always the same.

    Args:
        index: Its number.

    Returns:
        Its SMILES.
    """
    for scaffold, n in zip(SCAFFOLDS, _counts(), strict=True):
        if index < n:
            picks, k = [], index
            for _ in range(_slots(scaffold)):
                k, r = divmod(k, len(SUBSTITUENTS))
                picks.append(SUBSTITUENTS[r])
            return _fill(scaffold, picks)
        index -= n
    raise IndexError(f"the generator makes {size()} molecules")


def _rows(indices: np.ndarray) -> pd.DataFrame:
    """A table of molecules with the catalogue data a vendor file would carry.

    Args:
        indices: Which molecules.

    Returns:
        id, smiles, vendor, price_usd and stock_mg for each.
    """
    idx = np.asarray(indices, dtype=np.int64)
    # vendor, price and stock follow from the molecule's number, so they are the same every time
    return pd.DataFrame(
        {
            "id": [f"ML-{i:08d}" for i in idx],
            "smiles": [smiles_at(int(i)) for i in idx],
            "vendor": [VENDORS[int(i) % len(VENDORS)] for i in idx],
            "price_usd": np.round(20 + (idx * 7919 % 48100) / 100, 2),
            "stock_mg": (idx * 104729 % 50 + 1) * 10,
        }
    )


def library(n: int, seed: int = 0) -> pd.DataFrame:
    """A random sample of n different molecules, the same for the same seed on every computer.

    Args:
        n: How many molecules.
        seed: Which sample.

    Returns:
        id, smiles, vendor, price_usd and stock_mg for each.
    """
    total = size()
    if n > total:
        raise ValueError(f"the generator makes {total} molecules, not {n}")
    rng = np.random.default_rng(seed)
    picked = rng.choice(total, size=n, replace=False) if n < total else np.arange(total)
    return _rows(np.sort(picked))


def stream(n: int, batch: int = 100_000, start: int = 0) -> Iterator[pd.DataFrame]:
    """The first n molecules (from `start`), made one batch at a time and never all at once.

    Args:
        n: How many molecules in all.
        batch: How many per batch.
        start: The number of the first molecule.

    Yields:
        One table per batch.
    """
    stop = min(start + n, size())
    for first in range(start, stop, batch):
        yield _rows(np.arange(first, min(first + batch, stop)))


DEFECTS = {
    "salt": "a counter-ion written into the record (.Cl or .[Na+])",
    "solvent": "a solvent molecule in the record (.O, .CCO)",
    "invalid": "SMILES that cannot be read (a ring that is never closed)",
    "valence": "an impossible valence (a carbon with five bonds)",
    "element": "an element the library should not contain (selenium)",
    "duplicate": "the same molecule again, written as a different SMILES",
}


def add_defects(df: pd.DataFrame, rate: float = 0.05, seed: int = 0) -> pd.DataFrame:
    """A copy of a library with faults added at a known rate, and a `defect` column saying which.

    Args:
        df: A library from library() or stream().
        rate: The share of rows to damage, split evenly across the kinds in DEFECTS.
        seed: Which rows and which faults.

    Returns:
        The damaged library; `defect` is "" for clean rows. Duplicates are added as new rows (with
        ids ending in "-dup"), the other faults change rows in place.
    """
    from rdkit import Chem

    rng = np.random.default_rng(seed)
    out = df.copy()
    out["defect"] = ""
    chosen = rng.choice(len(out), size=round(rate * len(out)), replace=False)
    kinds = list(DEFECTS)
    extra = []
    for k, row in enumerate(chosen):
        kind = kinds[k % len(kinds)]
        smi = out.at[row, "smiles"]
        if kind == "salt":
            smi += [".Cl", ".[Na+]"][k % 2]
        elif kind == "solvent":
            smi += [".O", ".CCO"][k % 2]
        elif kind == "invalid":
            smi = smi.replace("1", "", 1)  # remove one ring-opening digit: the ring never closes
        elif kind == "valence":
            smi = "C(C)(C)(C)(C)" + smi  # five bonds on one carbon
        elif kind == "element":
            smi = re.sub(r"C(?!l)", "[Se]", smi, count=1)  # an aliphatic carbon, not the C of Cl
        elif kind == "duplicate":
            mol = Chem.MolFromSmiles(smi)
            dup = out.loc[row].copy()
            dup["id"] = f"{dup['id']}-dup"
            dup["smiles"] = Chem.MolToSmiles(mol, canonical=False, doRandom=True)
            dup["defect"] = "duplicate"
            extra.append(dup)
            continue
        out.at[row, "smiles"] = smi
        out.at[row, "defect"] = kind
    if extra:
        out = pd.concat([out, pd.DataFrame(extra)], ignore_index=True)
    return out.sample(frac=1, random_state=seed).reset_index(drop=True)
