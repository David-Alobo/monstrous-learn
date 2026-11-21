"""The functions Module 9 runs in other processes and on Dask workers.

They live in a file of their own, not in the lesson's code, so that every worker can import them by
name. A worker started with "spawn" (the default on Windows and macOS) is a fresh Python process: it
can only run a function it can import, and a function defined in a notebook or in the script that
started it cannot always be found. A module file works with every backend, and can be tested.
"""

from __future__ import annotations

import logging
import time
from collections import namedtuple

import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, rdFingerprintGenerator

log = logging.getLogger(__name__)
# RDKit's own message for every unreadable SMILES is turned off; describe() logs one line per chunk
RDLogger.DisableLog("rdApp.*")

FP_RADIUS, FP_BITS = 2, 2048  # Morgan fingerprint settings
LOOK_UP_SECONDS = 0.05  # how long the stand-in web request waits
MORGAN = rdFingerprintGenerator.GetMorganGenerator(radius=FP_RADIUS, fpSize=FP_BITS)

# one row of results: a tuple whose positions also have names, so it prints readably, compares
# equal to a plain tuple, and pickles to and from worker processes like one
Description = namedtuple("Description", ["canonical_smiles", "mw", "tpsa", "bits_on"])
UNREADABLE = Description("", 0.0, 0.0, 0)


def describe(smiles: list[str]) -> list[Description]:
    """Standardise and describe a chunk of molecules, given as SMILES.

    Args:
        smiles: The molecules of one chunk.

    Returns:
        For each molecule, in the same order: canonical SMILES, molecular weight, polar surface
        area and the number of bits set in its 2048-bit Morgan fingerprint (UNREADABLE for SMILES
        RDKit cannot read, with one warning per chunk saying how many).
    """
    rows = []
    for text in smiles:
        mol = Chem.MolFromSmiles(text)
        if mol is None:
            rows.append(UNREADABLE)
            continue
        rows.append(
            Description(
                Chem.MolToSmiles(mol),
                round(Descriptors.MolWt(mol), 2),
                round(Descriptors.TPSA(mol), 2),
                MORGAN.GetFingerprint(mol).GetNumOnBits(),
            )
        )
    unreadable = rows.count(UNREADABLE)
    if unreadable:
        log.warning("%d of %d SMILES could not be read", unreadable, len(smiles))
    return rows


# the pandas type of each field of Description, for tables of results
COLUMNS = {"canonical_smiles": "string", "mw": "float64", "tpsa": "float64", "bits_on": "int64"}


def describe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """describe() for one partition of a table with id, smiles and vendor columns.

    Args:
        frame: One partition (a pandas table).

    Returns:
        Its id and vendor, with the columns in COLUMNS added.
    """
    described = pd.DataFrame(describe(list(frame["smiles"])), columns=list(Description._fields))
    described = described.astype(COLUMNS)
    described.index = frame.index
    return pd.concat([frame[["id", "vendor"]], described], axis=1)


def look_up(identifier: str) -> str:
    """Stand-in for a web request (a PubChem lookup, say): mostly waiting, little computing.

    Args:
        identifier: A molecule's id.

    Returns:
        A made-up record for it, after waiting LOOK_UP_SECONDS.
    """
    time.sleep(LOOK_UP_SECONDS)
    return f"record for {identifier}"
