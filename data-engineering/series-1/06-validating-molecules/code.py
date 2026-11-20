"""Validating molecules: the code of the lesson, in order.

A validation gate that reads every record, checks it, and accepts it or quarantines it with recorded reasons, so no broken structure spreads and no record disappears silently.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/06-validating-molecules/
Run it from anywhere, e.g. from the series folder: uv run python 06-validating-molecules/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]

# ---- 1. What goes wrong without a gate ----
import chemlib

library = chemlib.library(10_000, seed=6)
dirty = chemlib.add_defects(library, rate=0.05, seed=7)
print(len(dirty), "records")
print(dirty["defect"].replace("", "(none)").value_counts().sort_index().to_string())
for kind, row in dirty[dirty["defect"] != ""].groupby("defect").head(1).iterrows():
    print(f"{row['defect']:10} {row['smiles']}")
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")  # silence RDKit, as many scripts do
mols = [Chem.MolFromSmiles(s) for s in dirty["smiles"]]
RDLogger.EnableLog("rdApp.*")
kept = [m for m in mols if m is not None]
print(len(dirty) - len(kept), "records vanished, with no reason recorded")
in_pieces = sum(len(Chem.GetMolFrags(m)) > 1 for m in kept)
with_selenium = sum(any(a.GetSymbol() == "Se" for a in m.GetAtoms()) for m in kept)
print(in_pieces, "kept records are in more than one piece")
print(with_selenium, "kept records contain selenium")

# ---- Reasons, not True or False ----
from typing import NamedTuple


class Issue(NamedTuple):
    """One problem found in a record: what it is, in words, and what to do about it."""

    code: str  # a short, stable reason code, e.g. "VALENCE"
    message: str  # what a person needs to know to act on it
    action: str  # "reject" (cannot be repaired), "fix" (Module 7 repairs it) or "warn"

# ---- Capturing RDKit's messages ----
import logging
import re

from rdkit import rdBase


class Collector(logging.Handler):
    """Keeps RDKit's log messages, without their timestamps, until they are read."""

    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        text = re.sub(r"^\[\d\d:\d\d:\d\d\] ", "", record.getMessage()).strip()
        self.messages.append(text)


rdBase.LogToPythonLogger()
collector = Collector()
rdkit_log = logging.getLogger("rdkit")
rdkit_log.handlers = [collector]  # replace RDKit's own handler, which prints to the screen
rdkit_log.propagate = False
PROBLEM_CODES = {
    "AtomValenceException": "VALENCE",
    "AtomKekulizeException": "AROMATICITY",
    "KekulizeException": "AROMATICITY",
}


def parse(smiles):
    """Read a SMILES and sanitise it, keeping RDKit's reasons when either step fails.

    Returns the sanitised molecule (or None) and a list of issues.
    """
    collector.messages.clear()
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        message = "; ".join(collector.messages) or "the SMILES could not be read"
        return None, [Issue("PARSE", message, "reject")]
    problems = Chem.DetectChemistryProblems(mol)
    if problems:
        issues = [
            Issue(PROBLEM_CODES.get(p.GetType(), "SANITISATION"), p.Message(), "reject")
            for p in problems
        ]
        return None, issues
    Chem.SanitizeMol(mol)
    return mol, []


examples = {
    "ethanol": "CCO",
    "unclosed ring": "c1ccccc",
    "five-bond carbon": "C(C)(C)(C)(C)C",
    "five-atom aromatic ring": "c1cccc1",
}
for name, smiles in examples.items():
    mol, issues = parse(smiles)
    print(f"{name}: {'read' if mol else 'not read'}")
    for issue in issues:
        print(f"    {issue.code}: {issue.message}")

# ---- Elements ----
ALLOWED_ELEMENTS = {"H", "B", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"}


def check_elements(mol):
    """Elements outside the allow-list."""
    found = sorted({atom.GetSymbol() for atom in mol.GetAtoms()} - ALLOWED_ELEMENTS)
    if not found:
        return []
    return [Issue("ELEMENT", f"element not allowed: {', '.join(found)}", "reject")]


print(check_elements(Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")))
print(check_elements(Chem.MolFromSmiles("C[Se]c1ccccc1")))

# ---- Fragments: salts, solvents and mixtures ----
SALTS = {"Cl": "hydrogen chloride", "[Cl-]": "chloride", "Br": "hydrogen bromide",
         "[Na+]": "sodium", "[K+]": "potassium", "O=C(O)C(F)(F)F": "trifluoroacetic acid"}
SOLVENTS = {"O": "water", "CCO": "ethanol", "CO": "methanol", "CS(C)=O": "DMSO",
            "ClCCl": "dichloromethane"}  # fmt: skip


def check_fragments(mol):
    """More than one molecule in the record: salts and solvents (fixable) or a mixture."""
    pieces = sorted(Chem.MolToSmiles(f) for f in Chem.GetMolFrags(mol, asMols=True))
    if len(pieces) == 1:
        return []
    largest = max(pieces, key=lambda s: Chem.MolFromSmiles(s).GetNumHeavyAtoms())
    issues = []
    for piece in pieces:
        if piece == largest:
            continue
        if piece in SALTS:
            issues.append(Issue("SALT", f"counter-ion {piece} ({SALTS[piece]})", "fix"))
        elif piece in SOLVENTS:
            issues.append(Issue("SOLVENT", f"solvent {piece} ({SOLVENTS[piece]})", "fix"))
        else:
            issues.append(Issue("MIXTURE", f"a second compound: {piece}", "reject"))
    return issues


records = {
    "sodium acetate": "CC(=O)[O-].[Na+]",
    "phenol hydrate": "c1ccccc1O.O",
    "triethylamine HCl": "CCN(CC)CC.Cl",
    "aspirin + paracetamol": "CC(=O)Oc1ccccc1C(=O)O.CC(=O)Nc1ccc(O)cc1",
    "benzene + ethanol": "c1ccccc1.CCO",
}
for name, smiles in records.items():
    for issue in check_fragments(Chem.MolFromSmiles(smiles)):
        print(f"{name:22} {issue.code}: {issue.message} -> {issue.action}")

# ---- Charges ----
def check_charge(mol):
    """A net formal charge on the record (charges that cancel, as in nitro groups, are fine)."""
    net = Chem.GetFormalCharge(mol)
    if net == 0:
        return []
    return [Issue("CHARGE", f"net charge {net:+d}", "fix")]


for smiles in ["C[N+](=O)[O-]", "[NH3+]CC(=O)[O-]", "CC[NH3+]", "CC(=O)[O-]"]:
    print(f"{smiles:18} {check_charge(Chem.MolFromSmiles(smiles))}")

# ---- Stereochemistry ----
def check_stereo(mol):
    """Stereocentres and double bonds whose configuration the record does not give."""
    missing = [
        info
        for info in Chem.FindPotentialStereo(mol)
        if info.specified == Chem.StereoSpecified.Unspecified
    ]
    if not missing:
        return []
    centres = sum(info.type == Chem.StereoType.Atom_Tetrahedral for info in missing)
    bonds = len(missing) - centres
    return [Issue("STEREO", f"unassigned: {centres} stereocentre(s), {bonds} double bond(s)",
                  "warn")]  # fmt: skip


for smiles in ["CC(C)Cc1ccc(cc1)[C@H](C)C(=O)O", "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "CC=CC"]:
    print(f"{smiles:32} {check_stereo(Chem.MolFromSmiles(smiles))}")

# ---- Size ----
from rdkit.Chem import Descriptors

HEAVY_ATOMS = (6, 50)
MAX_WEIGHT = 700.0


def check_size(mol):
    """The largest piece must be between the heavy-atom limits and below the weight limit."""
    piece = max(Chem.GetMolFrags(mol, asMols=True), key=lambda f: f.GetNumHeavyAtoms())
    heavy = piece.GetNumHeavyAtoms()
    weight = Descriptors.MolWt(piece)
    issues = []
    if not HEAVY_ATOMS[0] <= heavy <= HEAVY_ATOMS[1]:
        issues.append(Issue("SIZE", f"{heavy} heavy atoms (allowed {HEAVY_ATOMS})", "reject"))
    if weight > MAX_WEIGHT:
        issues.append(Issue("WEIGHT", f"molecular weight {weight:.0f} (max {MAX_WEIGHT:.0f})",
                            "reject"))  # fmt: skip
    return issues


for smiles in ["CCO", "CC(=O)Oc1ccccc1C(=O)O", "C" * 60]:
    print(f"{smiles[:24]:26} {check_size(Chem.MolFromSmiles(smiles))}")
heavy = [Chem.MolFromSmiles(s).GetNumHeavyAtoms() for s in library["smiles"]]
print("heavy atoms in the clean library:", min(heavy), "to", max(heavy))

# ---- 4. The gate ----
CHECKS = [check_elements, check_fragments, check_charge, check_stereo, check_size]


def validate(smiles):
    """Every issue found in one record: from parsing, or from every check if it can be read."""
    mol, issues = parse(smiles)
    if mol is None:
        return issues
    for check in CHECKS:
        issues = issues + check(mol)
    return issues


def verdict(issues):
    """Accept a record with no issues or only warnings; quarantine everything else."""
    blocking = [i for i in issues if i.action != "warn"]
    return "quarantine" if blocking else "accept"


for smiles in ["CC(=O)Oc1ccccc1C(=O)O", "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "CC[NH3+].[Cl-]"]:
    issues = validate(smiles)
    print(f"{smiles:30} {verdict(issues):10} {[i.code for i in issues]}")
import pandas as pd

results = dirty.copy()
results["issues"] = [validate(s) for s in results["smiles"]]
results["codes"] = [";".join(i.code for i in issues) for issues in results["issues"]]
results["verdict"] = [verdict(issues) for issues in results["issues"]]
print(results["verdict"].value_counts().to_string())
assert len(results) == len(dirty), "every record leaves the gate"
quarantine = (
    results[results["verdict"] == "quarantine"]
    .explode("issues")
    .assign(
        code=lambda t: [i.code for i in t["issues"]],
        message=lambda t: [i.message for i in t["issues"]],
        action=lambda t: [i.action for i in t["issues"]],
    )[["id", "smiles", "code", "message", "action"]]
    .sort_values(["id", "code"])
    .reset_index(drop=True)
)
print(len(quarantine), "issues on", quarantine["id"].nunique(), "quarantined records")
print(quarantine[["id", "code", "message"]].head(6).to_string(index=False, max_colwidth=60))
every_issue = results.explode("issues").dropna(subset=["issues"])
summary = (
    pd.DataFrame(
        {
            "id": every_issue["id"],
            "code": [i.code for i in every_issue["issues"]],
            "action": [i.action for i in every_issue["issues"]],
        }
    )
    .groupby(["code", "action"])["id"]
    .nunique()
    .rename("records")
    .reset_index()
    .sort_values(["records", "code"], ascending=[False, True])
)
print(summary.to_string(index=False))
from pathlib import Path

Path("work").mkdir(exist_ok=True)
accepted = results[results["verdict"] == "accept"].drop(columns=["issues"])
accepted.to_parquet("work/accepted.parquet", index=False)
quarantine.to_parquet("work/quarantine.parquet", index=False)
print(len(accepted), "accepted +", quarantine["id"].nunique(), "quarantined =", len(dirty))

# ---- 5. Checks across records: duplicates ----
readable = results[results["verdict"] == "accept"].copy()
readable["inchikey"] = [Chem.MolToInchiKey(Chem.MolFromSmiles(s)) for s in readable["smiles"]]
readable = readable.sort_values("id")
first_id = readable.groupby("inchikey")["id"].transform("first")
repeats = readable[readable["id"] != first_id]
print(len(repeats), "accepted records repeat an earlier one")
print(repeats.assign(repeats=first_id)[["id", "repeats", "defect"]].head(3).to_string(index=False))

# ---- 6. Checking the validator against the truth ----
results["duplicate flag"] = results["id"].isin(repeats["id"])
results["outcome"] = results["verdict"].where(~results["duplicate flag"], "accept, duplicate")
truth = results["defect"].replace("", "(none)")
print(pd.crosstab(truth, results["outcome"]).to_string())
quarantined = results[results["verdict"] == "quarantine"]
codes = quarantined["codes"].str.split(";").explode()
print(pd.crosstab(quarantined["defect"].reindex(codes.index), codes).to_string())
