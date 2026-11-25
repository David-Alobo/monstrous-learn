"""The lab of Series 2: a small kinase drug-discovery lab's data, week by week, made in code.

Series 1 used this lab's molecules (chemlib) and its five kinase targets without naming it. Here it
has a project and a timeline. The project's target is EGFR. Each week the chemists register about
forty new compounds from three chemical series; every compound is tested on EGFR, in duplicate,
the week after it is registered, and the potent ones are tested on four other kinases (ABL1,
BRAF, CDK2, JAK2) the week after that, to check they are selective.

Potencies are not random. They follow from structure with a simple additive model (Free-Wilson):
each scaffold has a base potency on each target, each substituent at each position adds or takes
away a fixed amount, and each measurement has a little noise. So a substituent can help EGFR and
hurt JAK2, a series can be selective, and a few changes have large effects (activity cliffs), as in
real projects. The numbers are synthetic, and the course says so wherever they appear.

The files carry the problems real lab files have, planted on purpose and listed in `events`:

    from labdata import Lab

    lab = Lab()                       # the whole story, the same on every computer
    lab.registry_export(3)            # the compound registry as exported at the end of week 3
    lab.assay_export(3)               # the assay results the plate reader exported in week 3
    lab.write_week(3, "inbox")        # the files that arrived in week 3, as files
    lab.events                        # what was planted, and in which week
    lab.true_pic50("LAB-0042", "EGFR")  # the truth behind the measurements, for checking

No data is downloaded and nothing is redistributed.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import chemlib

# the five kinases of Series 1, with their ChEMBL target IDs (checked on ChEMBL: human, single protein)
TARGETS = {
    "EGFR": "CHEMBL203",
    "ABL1": "CHEMBL1862",
    "BRAF": "CHEMBL5145",
    "CDK2": "CHEMBL301",
    "JAK2": "CHEMBL2971",
}
PRIMARY = "EGFR"  # the project's target
PANEL = ["ABL1", "BRAF", "CDK2", "JAK2"]  # the selectivity panel
# the project's three chemical series: positions of chemlib.SCAFFOLDS
SERIES = {11: "aminopyrimidines", 3: "pyrimidine piperazines", 2: "ureas"}
START = date(2026, 9, 7)  # the Monday of week 1
WEEKS = 12
CHEMISTS = ["AO", "BK", "CN", "DS"]
SALTS = {"": "", "HCl": ".Cl", "TFA": ".O=C(O)C(F)(F)F"}
TOP_NM = 30_000.0  # the highest concentration tested: weaker compounds are reported as "> 30 uM"
PANEL_CUTOFF = 7.0  # compounds at least this potent on EGFR (pIC50) go on to the panel
NOISE = 0.15  # measurement noise, in pIC50 units


def monday(week: int) -> date:
    """The Monday of a week of the project.

    Args:
        week: The week, from 1.

    Returns:
        Its date.
    """
    return START + timedelta(weeks=week - 1)


class Lab:
    """The lab's compounds, its true potencies, its measurements and the files it produces."""

    def __init__(self, seed: int = 0, per_week: int = 40, weeks: int = WEEKS) -> None:
        """Make the lab's whole story, the same for the same seed on every computer.

        Args:
            seed: Which story.
            per_week: How many compounds are registered each week.
            weeks: How many weeks the project runs.
        """
        self.seed, self.weeks = seed, weeks
        rng = np.random.default_rng(seed)
        self._model = self._potency_model(rng)
        self.compounds = self._register(rng, per_week)
        self.results = self._measure(rng)
        self.events = self._plan_events()

    # ---------------------------------------------------------------- the potency model
    def _potency_model(self, rng: np.random.Generator) -> dict:
        """Base potencies and substituent effects for every target, series and position.

        Args:
            rng: The random generator.

        Returns:
            The model's numbers: base[target][scaffold] and effect[target][scaffold][position].
        """
        n_sub = len(chemlib.SUBSTITUENTS)
        base, effect = {}, {}
        for target in TARGETS:
            base[target], effect[target] = {}, {}
            for scaffold in SERIES:
                # the project's target is reached best; the panel kinases less so
                centre = 6.4 if target == PRIMARY else 5.4
                base[target][scaffold] = rng.normal(centre, 0.4)
                slots = chemlib.SCAFFOLDS[scaffold].count("{")
                effect[target][scaffold] = rng.normal(0.0, 0.3, size=(slots, n_sub))
        # a few large, target-specific effects: the activity cliffs a project learns from
        cliffs = [
            ("EGFR", 11, 0, "C(F)(F)F", +1.4), ("EGFR", 11, 1, "N8CCOCC8", +1.0),
            ("JAK2", 11, 1, "N8CCOCC8", +1.6), ("EGFR", 3, 1, "c8ccncc8", -1.5),
            ("CDK2", 2, 0, "Cl", +1.2), ("EGFR", 2, 1, "C#N", +1.1),
        ]  # fmt: skip
        for target, scaffold, position, sub, size in cliffs:
            effect[target][scaffold][position, chemlib.SUBSTITUENTS.index(sub)] = size
        return {"base": base, "effect": effect}

    def _pic50(self, index: int, target: str) -> float:
        """The true pIC50 of a chemlib molecule on a target.

        Args:
            index: The molecule's number in chemlib.
            target: The target's gene name.

        Returns:
            Base potency plus the effect of each substituent, kept within 3.5 to 10.
        """
        scaffold, picks = chemlib.parts_at(index)
        value = self._model["base"][target][scaffold]
        for position, sub in enumerate(picks):
            value += self._model["effect"][target][scaffold][position, sub]
        return float(np.clip(value, 3.5, 10.0))

    # ---------------------------------------------------------------- compounds
    def _register(self, rng: np.random.Generator, per_week: int) -> pd.DataFrame:
        """The compounds registered over the project, with the week each was registered.

        Args:
            rng: The random generator.
            per_week: How many each week.

        Returns:
            One row per compound: compound_id, chemlib index, series, parent SMILES, salt, batch,
            chemist, vendor and the week it was registered.
        """
        rows, seen = [], set()
        n_sub = len(chemlib.SUBSTITUENTS)
        for week in range(1, self.weeks + 1):
            for _ in range(per_week):
                while True:
                    scaffold = int(rng.choice(list(SERIES), p=[0.5, 0.3, 0.2]))
                    slots = chemlib.SCAFFOLDS[scaffold].count("{")
                    index = chemlib.first_index(scaffold) + int(rng.integers(0, n_sub**slots))
                    if index not in seen:
                        seen.add(index)
                        break
                salt = str(rng.choice(list(SALTS), p=[0.85, 0.1, 0.05]))
                rows.append(
                    {
                        "compound_id": f"LAB-{len(rows) + 1:04d}",
                        "chemlib_index": index,
                        "series": SERIES[scaffold],
                        "parent_smiles": chemlib.smiles_at(index),
                        "salt": salt,
                        "batch": 1,
                        "chemist": str(rng.choice(CHEMISTS)),
                        "vendor": chemlib.VENDORS[index % len(chemlib.VENDORS)],
                        "registered_week": week,
                    }
                )
        return pd.DataFrame(rows)

    def true_pic50(self, compound_id: str, target: str) -> float:
        """The true pIC50 of a registered compound on a target (what the measurements estimate).

        Args:
            compound_id: The compound, e.g. "LAB-0042".
            target: The target's gene name, e.g. "EGFR".

        Returns:
            Its pIC50.
        """
        row = self.compounds.loc[self.compounds["compound_id"] == compound_id].iloc[0]
        return self._pic50(int(row["chemlib_index"]), target)

    # ---------------------------------------------------------------- measurements
    def _measure(self, rng: np.random.Generator) -> pd.DataFrame:
        """Every measurement of the project: EGFR the week after registration, the panel after.

        Args:
            rng: The random generator.

        Returns:
            One row per measurement, with its week, plate, target, IC50 in nM and relation.
        """
        rows = []
        plates: dict[int, int] = {}

        def measure(compound: pd.Series, target: str, week: int) -> None:
            """Add two replicate measurements of a compound on a target in a week."""
            if week > self.weeks:
                return
            truth = self._pic50(int(compound["chemlib_index"]), target)
            plates[week] = plates.get(week, 0) + 1
            plate = f"P{week:02d}-{(plates[week] - 1) // 20 + 1:02d}"  # about 20 tests a plate
            for replicate in (1, 2):
                measured = truth + rng.normal(0, NOISE)
                ic50 = 10 ** (9 - measured)
                relation = ">" if ic50 > TOP_NM else "="
                rows.append(
                    {
                        "compound_id": compound["compound_id"],
                        "target": target,
                        "week": week,
                        "plate": plate,
                        "replicate": replicate,
                        "ic50_nm": TOP_NM if relation == ">" else float(f"{ic50:.3g}"),
                        "relation": relation,
                    }
                )

        for _, compound in self.compounds.iterrows():
            tested = int(compound["registered_week"]) + 1
            measure(compound, PRIMARY, tested)
            if self._pic50(int(compound["chemlib_index"]), PRIMARY) >= PANEL_CUTOFF:
                for target in PANEL:
                    measure(compound, target, tested + 1)
        out = pd.DataFrame(rows).sort_values(
            ["week", "plate", "compound_id", "target", "replicate"]
        )
        out.insert(0, "result_id", [f"R-{i:05d}" for i in range(1, len(out) + 1)])
        return out.reset_index(drop=True)

    # ---------------------------------------------------------------- planted events
    def _plan_events(self) -> pd.DataFrame:
        """What is planted in the files, and in which week: the problems later modules solve.

        Returns:
            One row per event: week, kind, what happens, and the module that deals with it.
        """
        fixed = self.compounds.iloc[41]["compound_id"]  # registered in week 2
        rows = [
            (2, "unit spellings", "results in µM are written as uM or μM on some plates", 2),
            (4, "resent file", "week 3's assay file arrives again, under a new name", 2),
            (5, "schema change", "the plate reader's export renames 'units' to 'unit' and adds 'operator'", 2),
            (7, "re-registration", f"{fixed}'s structure is corrected in the registry", 6),
            (8, "corrected plate", "plate P08-01 is re-read; its corrected results replace the first ones", 6),
            (10, "late file", "week 10's assay file arrives a week late, with week 11's", 8),
        ]  # fmt: skip
        return pd.DataFrame(rows, columns=["week", "kind", "what", "module"])

    # ---------------------------------------------------------------- the files
    def registry_export(self, week: int) -> pd.DataFrame:
        """The compound registry as the chemists' spreadsheet exports it at the end of a week.

        Args:
            week: The week.

        Returns:
            Every compound registered so far, with the SMILES as registered (salt included).
        """
        reg = self.compounds[self.compounds["registered_week"] <= week].copy()
        reg["smiles"] = reg["parent_smiles"] + reg["salt"].map(SALTS)
        fixed = self.compounds.iloc[41]["compound_id"]
        if week < 7:  # until week 7 one compound is registered with a wrong structure
            wrong = reg["compound_id"] == fixed
            reg.loc[wrong, "smiles"] = reg.loc[wrong, "smiles"].str.replace("N", "C", n=1)
        reg["registered_on"] = reg["registered_week"].map(lambda w: monday(w) + timedelta(days=4))
        return reg[["compound_id", "smiles", "salt", "batch", "chemist", "vendor", "registered_on"]]

    def assay_export(self, week: int) -> pd.DataFrame:
        """The assay results the plate reader exports for a week, with that week's quirks.

        Args:
            week: The week.

        Returns:
            The week's results, as the file has them (column names and unit spellings included).
        """
        res = self.results[self.results["week"] == week].copy()
        rng = np.random.default_rng(self.seed * 1000 + week)
        micromolar = res["ic50_nm"] >= 1000
        value = np.where(micromolar, res["ic50_nm"] / 1000, res["ic50_nm"])
        units = np.where(micromolar, "µM", "nM").astype(object)
        if week >= 2:  # some plates spell micromolar differently
            odd = micromolar & (rng.random(len(res)) < 0.3)
            units[odd.to_numpy()] = rng.choice(["uM", "μM"], int(odd.sum()))
        out = pd.DataFrame(
            {
                "result_id": res["result_id"],
                "compound_id": res["compound_id"],
                "target": res["target"],
                "plate": res["plate"],
                "replicate": res["replicate"],
                "relation": res["relation"],
                "value": [float(f"{v:.3g}") for v in value],
                "units": units,
                "run_date": [monday(w) + timedelta(days=2) for w in res["week"]],
            }
        )
        if week == 8:  # plate P08-01 is re-read: corrected rows follow, marked as such
            first = out["plate"] == "P08-01"
            corrected = out[first].copy()
            corrected["result_id"] = corrected["result_id"] + "-c"
            corrected["value"] = [float(f"{v * 0.5:.3g}") for v in corrected["value"]]
            out["status"] = "final"
            out.loc[first, "status"] = "superseded"
            corrected["status"] = "corrected"
            out = pd.concat([out, corrected], ignore_index=True)
        if week >= 5:  # the plate reader's software was updated
            out = out.rename(columns={"units": "unit"})
            out.insert(len(out.columns) - 1, "operator", rng.choice(CHEMISTS, len(out)))
        return out.reset_index(drop=True)

    def files(self, week: int) -> dict[str, pd.DataFrame]:
        """The files that arrive in a week, by file name.

        Args:
            week: The week.

        Returns:
            The registry export, and the assay files that arrived that week (none in week 1,
            when nothing has been tested yet; a resent copy of week 3's in week 4; week 10's
            arriving in week 11).
        """
        out = {f"registry_{monday(week):%Y-%m-%d}.csv": self.registry_export(week)}
        if week != 10 and (self.results["week"] == week).any():
            out[f"assay_{monday(week):%Y-%m-%d}.csv"] = self.assay_export(week)
        if week == 4:
            out[f"assay_{monday(3):%Y-%m-%d}_resent.csv"] = self.assay_export(3)
        if week == 11:
            out[f"assay_{monday(10):%Y-%m-%d}.csv"] = self.assay_export(10)
        return out

    def write_week(self, week: int, folder: str | Path) -> list[Path]:
        """Write the files that arrive in a week into a folder, as the lab would receive them.

        Args:
            week: The week.
            folder: Where to write them (made if needed).

        Returns:
            The files written.
        """
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        written = []
        for name, table in self.files(week).items():
            path = folder / name
            table.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
            written.append(path)
        return written
