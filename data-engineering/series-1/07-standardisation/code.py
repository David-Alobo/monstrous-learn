"""Standardisation as a tested transformation: the code of the lesson, in order.

One canonical form per compound, made by one pure, versioned function (clean up, choose the parent, neutralise, optionally choose one tautomer) and tested like any other software.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/07-standardisation/
Run it from anywhere, e.g. from the series folder: uv run python 07-standardisation/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]

# ---- 1. One compound, many records ----
from rdkit import Chem

records = {
    "free base": "O=C(NCc1ccc(F)cc1)c1ccc(C2CCNCC2)cc1",
    "hydrochloride, as HCl": "O=C(NCc1ccc(F)cc1)c1ccc(C2CCNCC2)cc1.Cl",
    "hydrochloride, ionic": "O=C(NCc1ccc(F)cc1)c1ccc(C2CC[NH2+]CC2)cc1.[Cl-]",
    "hydrate": "O=C(NCc1ccc(F)cc1)c1ccc(C2CCNCC2)cc1.O",
}
for name, smiles in records.items():
    print(f"{name:22} {Chem.MolToInchiKey(Chem.MolFromSmiles(smiles))}")

# ---- Clean-up: one way to draw each group ----
from rdkit.Chem.MolStandardize import rdMolStandardize

for smiles in ["CN(=O)=O", "CS(C)=O", "C[S+](C)[O-]"]:
    mol = Chem.MolFromSmiles(smiles)
    cleaned = rdMolStandardize.Cleanup(mol)
    print(f"{smiles:14} read as {Chem.MolToSmiles(mol):16} cleaned: {Chem.MolToSmiles(cleaned)}")

# ---- The parent: strip salts and solvents ----
chooser = rdMolStandardize.LargestFragmentChooser(preferOrganic=True)
for name in ["hydrochloride, as HCl", "hydrate"]:
    parent = chooser.choose(Chem.MolFromSmiles(records[name]))
    print(f"{name:22} -> {Chem.MolToSmiles(parent)}")

# ---- Neutralise ----
uncharger = rdMolStandardize.Uncharger()
for smiles in ["CC[NH3+]", "CC(=O)[O-]", "[NH3+]CC(=O)[O-]", "C[N+](C)(C)C"]:
    neutral = uncharger.uncharge(Chem.MolFromSmiles(smiles))
    print(f"{smiles:18} -> {Chem.MolToSmiles(neutral)}")

# ---- Canonical tautomer ----
enumerator = rdMolStandardize.TautomerEnumerator()
for smiles in ["Oc1ccccn1", "O=c1cccc[nH]1", "O=C1C=CCC=C1"]:
    canonical = enumerator.Canonicalize(Chem.MolFromSmiles(smiles))
    print(f"{smiles:14} -> {Chem.MolToSmiles(canonical)}")

# ---- 3. One pure function, with versioned rules ----
import hashlib
import json
from typing import NamedTuple

import rdkit

RULES_VERSION = "1.0.0"  # change it whenever a step or a default changes


class Options(NamedTuple):
    """Which standardisation steps to run, and their settings. Immutable, so it can be hashed."""

    cleanup: bool = True
    parent: bool = True
    uncharge: bool = True
    tautomer: bool = False
    max_tautomers: int = 1000


def config_hash(options):
    """A short fingerprint of everything that decides the output: the rules, options and RDKit."""
    config = {"rules": RULES_VERSION, "rdkit": rdkit.__version__, **options._asdict()}
    text = json.dumps(config, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:12]


DEFAULT = Options()
WITH_TAUTOMERS = Options(tautomer=True)
print("default:       ", config_hash(DEFAULT))
print("with tautomers:", config_hash(WITH_TAUTOMERS))
class Standardised(NamedTuple):
    """The canonical SMILES of a record and the steps that changed it."""

    smiles: str
    changed_by: tuple


def steps_for(options):
    """The standardisation steps switched on in `options`, in the order they run."""
    steps = []
    if options.cleanup:
        steps.append(("cleanup", rdMolStandardize.Cleanup))
    if options.parent:
        chooser = rdMolStandardize.LargestFragmentChooser(preferOrganic=True)
        steps.append(("parent", chooser.choose))
    if options.uncharge:
        steps.append(("uncharge", rdMolStandardize.Uncharger().uncharge))
    if options.tautomer:
        params = rdMolStandardize.CleanupParameters()
        params.maxTautomers = options.max_tautomers
        enumerator = rdMolStandardize.TautomerEnumerator(params)
        steps.append(("tautomer", enumerator.Canonicalize))
    return steps


def standardise(smiles, options=DEFAULT):
    """The canonical form of one record under `options`. Pure: nothing else is read or changed.

    Raises ValueError for SMILES that cannot be read: validate first (Module 6).
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"cannot read {smiles!r}: validate it first")
    changed_by = []
    for name, step in steps_for(options):
        before = Chem.MolToSmiles(mol)
        mol = step(mol)
        if Chem.MolToSmiles(mol) != before:
            changed_by.append(name)
    return Standardised(Chem.MolToSmiles(mol), tuple(changed_by))


for name, smiles in records.items():
    result = standardise(smiles)
    print(f"{name:22} {result.smiles}  changed by: {', '.join(result.changed_by) or '-'}")

# ---- 4. Testing it like software ----
def test_known_cases():
    """Records whose standard form is agreed in advance."""
    assert standardise("CC(=O)[O-].[Na+]").smiles == "CC(=O)O"  # sodium acetate -> acetic acid
    assert standardise("[NH3+]CC(=O)[O-]").smiles == "NCC(=O)O"  # zwitterion -> neutral glycine
    assert standardise("CCN(CC)CC.Cl").smiles == "CCN(CC)CC"  # salt stripped
    pyridone = standardise("O=c1cccc[nH]1", WITH_TAUTOMERS).smiles
    assert standardise("Oc1ccccn1", WITH_TAUTOMERS).smiles == pyridone  # a tautomer pair
    assert standardise("Oc1ccccn1").smiles != pyridone  # ... and without the tautomer step


test_known_cases()
print("known cases pass")
import chemlib


def is_idempotent(smiles, options=DEFAULT):
    """Standardising the output again gives the output."""
    once = standardise(smiles, options).smiles
    return standardise(once, options).smiles == once


def is_invariant(smiles, options=DEFAULT, n=3):
    """n randomly written SMILES of the same molecule all give one output."""
    mol = Chem.MolFromSmiles(smiles)
    variants = Chem.MolToRandomSmilesVect(mol, n, randomSeed=7)
    return len({standardise(s, options).smiles for s in [smiles, *variants]}) == 1


sample = chemlib.library(500, seed=31)["smiles"]
print("idempotent:", sum(is_idempotent(s) for s in sample), "of", len(sample))
print("invariant: ", sum(is_invariant(s) for s in sample), "of", len(sample))

# ---- Validate first ----
import pandas as pd
from rdkit import RDLogger

RDLogger.DisableLog("rdApp.*")  # the reasons are Module 6's subject; here we only need verdicts
ALLOWED_ELEMENTS = {"H", "B", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"}
SALTS_AND_SOLVENTS = {"Cl", "[Cl-]", "Br", "[Na+]", "[K+]", "O=C(O)C(F)(F)F", "O", "CCO", "CO"}


def gate(smiles):
    """'reject' for unreadable records, foreign elements or unknown fragments; else 'pass'."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return "reject"
    if {atom.GetSymbol() for atom in mol.GetAtoms()} - ALLOWED_ELEMENTS:
        return "reject"
    pieces = sorted(Chem.MolToSmiles(f) for f in Chem.GetMolFrags(mol, asMols=True))
    largest = max(pieces, key=lambda s: Chem.MolFromSmiles(s).GetNumHeavyAtoms())
    if any(p not in SALTS_AND_SOLVENTS for p in pieces if p != largest):
        return "reject"
    return "pass"


library = chemlib.library(4_000, seed=21)
vendor_a = chemlib.add_defects(library, rate=0.05, seed=22)
vendor_a["verdict"] = [gate(s) for s in vendor_a["smiles"]]
print(pd.crosstab(vendor_a["defect"].replace("", "(none)"), vendor_a["verdict"]).to_string())

# ---- A second supplier ----
BASIC_AMINE = Chem.MolFromSmarts("[NX3;H2,H1;!$(N-C=[O,N,S]);!$(N-a);!$(N-[S,N,O])]")


def as_hydrochloride(smiles):
    """The compound with its first basic amine protonated, and a chloride ion beside it."""
    mol = Chem.RWMol(Chem.MolFromSmiles(smiles))
    atom = mol.GetAtomWithIdx(mol.GetSubstructMatch(BASIC_AMINE)[0])
    atom.SetFormalCharge(1)
    atom.SetNumExplicitHs(atom.GetTotalNumHs() + 1)
    Chem.SanitizeMol(mol)
    return Chem.MolToSmiles(mol) + ".[Cl-]"


passed = vendor_a[(vendor_a["verdict"] == "pass") & (vendor_a["defect"] == "")]
basic = passed[[Chem.MolFromSmiles(s).HasSubstructMatch(BASIC_AMINE) for s in passed["smiles"]]]
picked = basic.sample(200, random_state=5).sort_values("id")
vendor_b = pd.DataFrame(
    {
        "id": [f"VB-{k:05d}" for k in range(len(picked))],
        "smiles": [
            as_hydrochloride(s) if k % 2 == 0 else s + ".O=C(O)C(F)(F)F"
            for k, s in enumerate(picked["smiles"])
        ],
    }
)
print(len(basic), "of vendor A's clean records have a basic amine; vendor B sells", len(vendor_b))
print(vendor_b.head(2).to_string(index=False))

# ---- Run it, with provenance ----
merged = pd.concat(
    [vendor_a.loc[vendor_a["verdict"] == "pass", ["id", "smiles"]], vendor_b],
    ignore_index=True,
)
results = [standardise(s) for s in merged["smiles"]]
standard = pd.DataFrame(
    {
        "id": merged["id"],
        "input_smiles": merged["smiles"],
        "smiles": [r.smiles for r in results],
        "changed_by": [",".join(r.changed_by) for r in results],
        "rules_version": RULES_VERSION,
        "config_hash": config_hash(DEFAULT),
    }
)
changed = standard[standard["changed_by"] != ""]
print(len(standard), "records standardised;", len(changed), "changed")
print(changed["changed_by"].value_counts().sort_index().to_string())
examples = changed.groupby("changed_by").head(1)
print(examples[["id", "input_smiles", "smiles"]].to_string(index=False, max_colwidth=58))

# ---- Duplicates that only standardisation reveals ----
def inchikey(smiles):
    """The InChIKey of a SMILES."""
    return Chem.MolToInchiKey(Chem.MolFromSmiles(smiles))


standard["inchikey_in"] = [inchikey(s) for s in standard["input_smiles"]]
standard["inchikey"] = [inchikey(s) for s in standard["smiles"]]


def duplicate_groups(keys):
    """How many identities are held by more than one record."""
    sizes = keys.value_counts()
    return int((sizes > 1).sum())


before = duplicate_groups(standard["inchikey_in"])
after = duplicate_groups(standard["inchikey"])
print("duplicate groups before standardisation:", before)
print("duplicate groups after standardisation: ", after)
distinct_in, distinct_out = standard["inchikey_in"].nunique(), standard["inchikey"].nunique()
print("distinct compounds:", distinct_in, "->", distinct_out)
group_ids = standard.groupby("inchikey")["id"].agg(sorted)
joined = group_ids[standard.groupby("inchikey")["inchikey_in"].nunique() > 1]
print(len(joined), "groups join records whose InChIKeys differed before; the first three:")
for key, ids in joined.head(3).items():
    print(f"  {key}: {', '.join(ids)}")
with_vendor_b = sum(any(i.startswith("VB-") for i in ids) for ids in joined)
grown = sum(standard.loc[standard["inchikey"] == key, "inchikey_in"].duplicated().any()
            for key in joined.index)  # fmt: skip
print(with_vendor_b, "of them include a vendor B record;", grown, "already held a duplicate before")
from pathlib import Path

Path("work").mkdir(exist_ok=True)
standard.to_parquet("work/standardised.parquet", index=False)
print(standard.columns.tolist())

# ---- 6. Tautomers: what they cost and when to skip them ----
import time

tautomer_sample = library["smiles"].head(200).tolist()
start = time.perf_counter()
plain = [standardise(s) for s in tautomer_sample]
middle = time.perf_counter()
with_tautomers = [standardise(s, WITH_TAUTOMERS) for s in tautomer_sample]
end = time.perf_counter()
print(f"without tautomers: {1000 * (middle - start) / len(tautomer_sample):.1f} ms per molecule")
print(f"with tautomers:    {1000 * (end - middle) / len(tautomer_sample):.1f} ms per molecule")
moved = [(p.smiles, t.smiles) for p, t in zip(plain, with_tautomers) if p.smiles != t.smiles]
same_key = sum(
    Chem.MolToInchiKey(Chem.MolFromSmiles(a)) == Chem.MolToInchiKey(Chem.MolFromSmiles(b))
    for a, b in moved
)
print(len(moved), "of", len(tautomer_sample), "changed by the tautomer step;", same_key,
      "of those keep their InChIKey")
print("for example:", moved[0][0], "->", moved[0][1])
counts = [len(enumerator.Enumerate(Chem.MolFromSmiles(s))) for s in tautomer_sample]
print("tautomers per molecule: median", sorted(counts)[len(counts) // 2], " most", max(counts))
print(standardise("CC(=O)NO", WITH_TAUTOMERS).smiles)
alanine_amide = "C[C@H](N)C(=O)NC"
print("default:       ", standardise(alanine_amide).smiles)
print("with tautomers:", standardise(alanine_amide, WITH_TAUTOMERS).smiles)
