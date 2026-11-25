import numpy as np
import pandas as pd
import pytest
from rdkit import Chem, RDLogger

import chemlib
import labdata

RDLogger.DisableLog("rdApp.*")


@pytest.fixture(scope="module")
def lab():
    return labdata.Lab()


def test_the_same_story_every_time(lab):
    again = labdata.Lab()
    pd.testing.assert_frame_equal(lab.compounds, again.compounds)
    pd.testing.assert_frame_equal(lab.results, again.results)
    pd.testing.assert_frame_equal(lab.assay_export(8), again.assay_export(8))


def test_compounds_are_unique_valid_and_registered_weekly(lab):
    c = lab.compounds
    assert len(c) == 40 * labdata.WEEKS
    assert c["compound_id"].is_unique and c["chemlib_index"].is_unique
    assert set(c["registered_week"]) == set(range(1, labdata.WEEKS + 1))
    assert all(Chem.MolFromSmiles(s) is not None for s in c["parent_smiles"])
    assert set(c["series"]) == set(labdata.SERIES.values())


def test_registry_exports_grow_and_carry_salts(lab):
    sizes = [len(lab.registry_export(w)) for w in range(1, labdata.WEEKS + 1)]
    assert sizes == sorted(sizes) and sizes[0] == 40
    reg = lab.registry_export(labdata.WEEKS)
    salted = reg[reg["salt"] != ""]
    assert len(salted) > 0 and all("." in s for s in salted["smiles"])
    assert all(Chem.MolFromSmiles(s) is not None for s in reg["smiles"])


def test_one_structure_is_corrected_in_week_7(lab):
    fixed = lab.compounds.iloc[41]["compound_id"]
    before = lab.registry_export(6).set_index("compound_id").loc[fixed, "smiles"]
    after = lab.registry_export(7).set_index("compound_id").loc[fixed, "smiles"]
    assert before != after
    assert Chem.MolFromSmiles(before) is not None and Chem.MolFromSmiles(after) is not None
    others = lab.registry_export(6).merge(lab.registry_export(7), on="compound_id")
    assert (others["smiles_x"] != others["smiles_y"]).sum() == 1


def test_measurements_follow_the_plan(lab):
    r = lab.results
    first = r.groupby(["compound_id", "target"])["week"].min().reset_index()
    first = first.merge(lab.compounds[["compound_id", "registered_week"]], on="compound_id")
    egfr = first[first["target"] == "EGFR"]
    assert (egfr["week"] == egfr["registered_week"] + 1).all()
    panel = first[first["target"] != "EGFR"]
    assert (panel["week"] == panel["registered_week"] + 2).all()
    assert (r.groupby(["compound_id", "target"]).size() == 2).all()  # duplicates
    assert set(r["relation"]) <= {"=", ">"}


def test_measurements_estimate_the_truth(lab):
    r = lab.results[lab.results["relation"] == "="].head(300)
    truth = [lab.true_pic50(c, t) for c, t in zip(r["compound_id"], r["target"], strict=True)]
    measured = 9 - np.log10(r["ic50_nm"].to_numpy())
    assert np.abs(measured - np.array(truth)).mean() < 0.25


def test_potency_follows_structure_with_cliffs(lab):
    # the planted cliff: CF3 at the first position of the aminopyrimidines raises EGFR potency
    scaffold, cf3 = 11, chemlib.SUBSTITUENTS.index("C(F)(F)F")
    start, n = chemlib.first_index(scaffold), len(chemlib.SUBSTITUENTS)
    pairs = []
    for rest in range(0, n**3, 997):  # the same molecule with and without CF3 at position 1
        base = start + rest * n
        pairs.append(lab._pic50(base + cf3, "EGFR") - lab._pic50(base, "EGFR"))
    assert np.mean(pairs) > 1.0
    # and potency differs between targets: the panel is weaker on average
    egfr = [lab._pic50(i, "EGFR") for i in lab.compounds["chemlib_index"]]
    jak2 = [lab._pic50(i, "JAK2") for i in lab.compounds["chemlib_index"]]
    assert np.mean(egfr) > np.mean(jak2)


def test_planted_events_happen_when_listed(lab):
    assert list(lab.events["week"]) == [2, 4, 5, 7, 8, 10]
    assert "units" in lab.assay_export(4).columns and "unit" not in lab.assay_export(4).columns
    week5 = lab.assay_export(5)
    assert "unit" in week5.columns and "operator" in week5.columns and "units" not in week5.columns
    assert set(lab.assay_export(1)["units"]) <= {"nM", "µM"}
    assert {"uM", "μM"} & set(lab.assay_export(3)["units"])
    week8 = lab.assay_export(8)
    assert set(week8["status"]) == {"final", "superseded", "corrected"}
    assert (week8["status"] == "superseded").sum() == (week8["status"] == "corrected").sum()


def test_files_arrive_as_described(lab, tmp_path):
    assert len(lab.files(3)) == 2
    assert any(name.endswith("_resent.csv") for name in lab.files(4))
    assert not any(name.startswith("assay_") for name in lab.files(10))
    assert sum(name.startswith("assay_") for name in lab.files(11)) == 2
    written = lab.write_week(4, tmp_path / "inbox")
    assert len(written) == 3 and all(p.exists() for p in written)
    back = pd.read_csv(written[0])
    assert len(back) == len(lab.registry_export(4))


def test_no_empty_assay_file_before_anything_is_tested(lab):
    assert list(lab.files(1)) == ["registry_2026-09-07.csv"]
