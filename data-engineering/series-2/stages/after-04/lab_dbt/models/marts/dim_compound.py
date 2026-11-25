"""One row per compound, with its series and properties worked out once (Module 3)."""
from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, Lipinski

RDLogger.DisableLog("rdApp.*")
# the three chemical series, each as the core its compounds share
SERIES = {
    "aminopyrimidines": "c1ccc(nc1)Nc2ncccn2",
    "pyrimidine piperazines": "c1nccc(n1)N2CCN(CC2)C(=O)c3ccccc3",
    "ureas": "O=C(Nc1ccccc1)Nc2cccnc2",
}
CORES = {name: Chem.MolFromSmiles(core) for name, core in SERIES.items()}


def series_of(mol):
    """The series whose core the molecule contains (None if no core, or several)."""
    hits = [name for name, core in CORES.items() if mol.HasSubstructMatch(core)]
    return hits[0] if len(hits) == 1 else None


def model(dbt, session):
    compounds = dbt.ref("stg_compounds").df().sort_values("compound_id", ignore_index=True)
    mols = [Chem.MolFromSmiles(s) for s in compounds["parent_smiles"]]
    compounds.insert(0, "compound_key", range(1, len(compounds) + 1))
    compounds["series"] = [series_of(m) for m in mols]
    compounds["mw"] = [round(Descriptors.MolWt(m), 1) for m in mols]
    compounds["clogp"] = [round(Crippen.MolLogP(m), 2) for m in mols]
    compounds["hbd"] = [Lipinski.NumHDonors(m) for m in mols]
    compounds["hba"] = [Lipinski.NumHAcceptors(m) for m in mols]
    compounds["heavy_atoms"] = [m.GetNumHeavyAtoms() for m in mols]
    return compounds
