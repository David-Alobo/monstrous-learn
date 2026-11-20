"""The functions Module 9 runs in other processes and on Dask workers.

They live in a file of their own, not in the lesson's code, so that every worker can import them by
name. A worker started with "spawn" (the default on Windows and macOS) is a fresh Python process: it
can only run a function it can import, and a function defined in a notebook or in the script that
started it cannot always be found. A module file works with every backend, and can be tested.
"""

from __future__ import annotations

import time

import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, rdFingerprintGenerator

RDLogger.DisableLog("rdApp.*")  # keep the workers quiet; failures are recorded in the results
MORGAN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def describe(smiles: list[str]) -> list[tuple[str, float, float, int]]:
    """Standardise and describe a chunk of molecules, given as SMILES.

    Args:
        smiles: The molecules of one chunk.

    Returns:
        For each molecule, in the same order: canonical SMILES, molecular weight, polar surface
        area and the number of bits set in its 2048-bit Morgan fingerprint ("", 0.0, 0.0, 0 for
        SMILES RDKit cannot read).
    """
    rows = []
    for text in smiles:
        mol = Chem.MolFromSmiles(text)
        if mol is None:
            rows.append(("", 0.0, 0.0, 0))
            continue
        rows.append(
            (
                Chem.MolToSmiles(mol),
                round(Descriptors.MolWt(mol), 2),
                round(Descriptors.TPSA(mol), 2),
                MORGAN.GetFingerprint(mol).GetNumOnBits(),
            )
        )
    return rows


COLUMNS = {"canonical_smiles": "string", "mw": "float64", "tpsa": "float64", "bits_on": "int64"}


def describe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """describe() for one partition of a table with id, smiles and vendor columns.

    Args:
        frame: One partition (a pandas table).

    Returns:
        Its id and vendor, with the columns in COLUMNS added.
    """
    described = pd.DataFrame(describe(list(frame["smiles"])), columns=list(COLUMNS))
    described = described.astype(COLUMNS)
    described.index = frame.index
    return pd.concat([frame[["id", "vendor"]], described], axis=1)


def look_up(identifier: str) -> str:
    """Stand-in for a web request (a PubChem lookup, say): mostly waiting, little computing.

    Args:
        identifier: A molecule's id.

    Returns:
        A made-up record for it, after waiting 50 milliseconds.
    """
    time.sleep(0.05)
    return f"record for {identifier}"
