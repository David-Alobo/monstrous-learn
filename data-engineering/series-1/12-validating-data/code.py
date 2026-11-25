"""Validating data: records with Pydantic, tables with Pandera: the code of the lesson, in order.

Write down what a table of activity data must contain, check single records at the edges with Pydantic and whole batches with Pandera, and quarantine what fails with the reason why.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/12-validating-data/
Run it from anywhere, e.g. from the series folder: uv run python 12-validating-data/code.py
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
import json
import logging
import math
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self

import duckdb
import numpy as np
import pandas as pd
import pandera.pandas as pa
import pint
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

import chemlib

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
# the database the checked measurements and the quarantine are loaded into
DB_PATH = WORK / "activity.duckdb"
# the test data: how many compounds and measurements, and the seeds that make them
N_COMPOUNDS = 2_000
COMPOUND_SEED = 12
N_MEASUREMENTS = 5_000
MEASUREMENT_SEED = 13
FAULT_SEED = 14
# the name of the batch we check (a real job takes it from the file or the run)
BATCH_ID = "batch-0001"
# the targets we screen: the only target_id values the contract allows
TARGETS = ["ABL1", "BRAF", "CDK2", "EGFR", "JAK2"]
# how far a stored pChEMBL may be from 9 - log10(value in nM) and still be accepted
PCHEMBL_TOLERANCE = 0.01
# the largest share of failing rows a batch may have and still be loaded (0.05 is 5%)
MAX_FAILED_SHARE = 0.05
# the timing comparison repeats the batch this many times (40 gives about 200,000 rows)
BENCHMARK_COPIES = 40

WORK.mkdir(exist_ok=True)
RDLogger.DisableLog("rdApp.*")  # RDKit's own warnings would repeat what our errors say

# ---- 1. A data contract ----
CONTRACT = {
    "name": "measurements",
    "version": "1.0.0",
    "columns": {
        "measurement_id": "text, required, unique, M- and six digits",
        "compound_id": "text, required, ML- and eight digits, must exist in the compounds table",
        "smiles": "text, required, readable by RDKit",
        "inchikey": "text, required, 14-10-1 capital letters, must match the SMILES",
        "target_id": "text, required, one of the targets we screen",
        "activity_type": "text, required, one of IC50, Ki, Kd, EC50",
        "value": "number, required, greater than 0",
        "units": "text, required, one of nM, µM, mM",
        "pchembl": "number, optional, 0 to 14, equal to 9 - log10(value in nM) "
                   f"within {PCHEMBL_TOLERANCE}",
    },
    "rows": "no two rows with the same compound, target, activity type, value and units",
}

contract_file = WORK / f"contract-{CONTRACT['name']}-{CONTRACT['version']}.json"
contract_file.write_text(json.dumps(CONTRACT, indent=2, ensure_ascii=False), encoding="utf-8")
log.info("wrote %s with %d columns", contract_file.name, len(CONTRACT["columns"]))

# ---- A model for one measurement ----
MEASUREMENT_ID = r"^M-\d{6}$"  # the identifier formats the contract gives
COMPOUND_ID = r"^ML-\d{8}$"


class ActivityType(str, Enum):
    """The kinds of activity this table accepts."""

    IC50 = "IC50"
    KI = "Ki"
    KD = "Kd"
    EC50 = "EC50"


class Unit(str, Enum):
    """Concentration units, written exactly as the contract says (with the micro sign µ)."""

    NM = "nM"
    UM = "µM"
    MM = "mM"


NM_PER_UNIT = {Unit.NM: 1.0, Unit.UM: 1_000.0, Unit.MM: 1_000_000.0}


class Activity(BaseModel):
    """One measured activity: what was measured, against what, and its value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str = Field(pattern=r"^[A-Z0-9]{2,10}$")
    activity_type: ActivityType
    value: float = Field(gt=0)
    units: Unit
    pchembl: float | None = Field(default=None, ge=0, le=14)

    @property
    def value_nm(self) -> float:
        """The value in nanomolar."""
        return self.value * NM_PER_UNIT[self.units]

    @model_validator(mode="after")
    def pchembl_matches_value(self) -> Self:
        """pChEMBL is -log10 of the molar value, so it must agree with value and units."""
        if self.pchembl is not None:
            expected = 9 - math.log10(self.value_nm)
            if abs(self.pchembl - expected) > PCHEMBL_TOLERANCE:
                raise ValueError(
                    f"pchembl {self.pchembl} does not match {self.value} {self.units.value} "
                    f"(expected {expected:.2f})"
                )
        return self


class Measurement(Activity):
    """An activity together with the compound it was measured for."""

    measurement_id: str = Field(pattern=MEASUREMENT_ID)
    compound_id: str = Field(pattern=COMPOUND_ID)
    smiles: str

    @field_validator("smiles")
    @classmethod
    def readable_by_rdkit(cls, smiles: str) -> str:
        """Refuse a SMILES that RDKit cannot read."""
        if Chem.MolFromSmiles(smiles) is None:
            raise ValueError("RDKit cannot read this SMILES")
        return smiles

# ---- Good records and bad records ----
good = {
    "measurement_id": "M-000001",
    "compound_id": "ML-00012345",
    "smiles": "CC(=O)Oc1ccccc1C(=O)O",
    "target_id": "EGFR",
    "activity_type": "IC50",
    "value": 0.25,
    "units": "µM",
    "pchembl": 6.6,
}
m = Measurement.model_validate(good)
print(m.activity_type, m.units, m.value_nm, "nM")
a = Activity(target_id="JAK2", activity_type="Ki", value=4.2, units="nM")
print(a)
def show_errors(record: dict) -> None:
    """Validate a record and print 'valid' or one line per problem."""
    try:
        Measurement.model_validate(record)
        print("valid")
    except ValidationError as error:
        for problem in error.errors():
            where = ".".join(str(part) for part in problem["loc"]) or "record"
            print(f"  {where}: {problem['msg']}")


print("micromolar typed as uM, and a negative value:")
show_errors({**good, "units": "uM", "value": -0.25})
print("units missing, and a SMILES with a ring that never closes:")
show_errors({k: v for k, v in good.items() if k != "units"} | {"smiles": "c1ccccc"})
print("pchembl worked out as if the value were in nM:")
show_errors({**good, "pchembl": 9.6})
print("an extra column:")
show_errors({**good, "assay_ref": "lab book 7"})
UNIT_SPELLINGS = {"uM": "µM", "μM": "µM", "nm": "nM", "um": "µM", "mm": "mM"}


def normalise_units(units: str | None) -> str | None:
    """Map a known alternative spelling of a unit to the contract's spelling; leave others."""
    if units is None:
        return None
    return UNIT_SPELLINGS.get(units, units)


print("Greek mu and micro sign are the same character:", "μM" == "µM")
for spelling in ["uM", "μM", "µM", "nM", "pM"]:
    print(f"{spelling.encode('unicode_escape').decode():>10} -> {normalise_units(spelling)}")

# ---- One unit, one scale: nanomolar and pIC50 ----
def to_nm(value: float, units: str) -> float:
    """A concentration in nanomolar."""
    return value * NM_PER_UNIT[Unit(units)]


def p_activity(value_nm: float) -> float:
    """-log10 of the molar concentration, from a value in nanomolar."""
    return 9 - math.log10(value_nm)


def test_conversion() -> None:
    """Known values: 50 nM written three ways, and the anchor points of the log scale."""
    assert math.isclose(to_nm(50, "nM"), 50)
    assert math.isclose(to_nm(0.05, "µM"), 50)
    assert math.isclose(to_nm(0.00005, "mM"), 50)
    assert math.isclose(p_activity(to_nm(1, "nM")), 9)
    assert math.isclose(p_activity(to_nm(1, "µM")), 6)
    assert math.isclose(p_activity(to_nm(1, "mM")), 3)
    assert math.isclose(p_activity(to_nm(250, "nM")), 6.60, abs_tol=0.01)


test_conversion()
log.info("conversion tests passed")

# ---- Letting a library check the units ----
ureg = pint.UnitRegistry()
for spelling in ["nM", "uM", "µM", "μM", "pM", "nm", "ug/mL"]:
    unit = ureg.Unit(spelling)
    code = spelling.encode("unicode_escape").decode()
    print(f"{code:>10} -> {unit!s:22} measures {unit.dimensionality}")
print(ureg.Quantity(4.2, "uM").to("nM"))
try:
    ureg.Quantity(5, "ug/mL").to("nM")
except pint.DimensionalityError as error:
    print("refused:", error)
aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
mw = ureg.Quantity(Descriptors.MolWt(aspirin), "g/mol")
dose = ureg.Quantity(5, "ug/mL")
in_nm = dose.to("nM", "chemistry", mw=mw)
print(f"aspirin, {mw:.2f~P}: {dose:~P} is {in_nm:.1f~P}, pIC50 {p_activity(in_nm.magnitude):.2f}")
MOLAR = ureg.Unit("M").dimensionality


def is_concentration(units: str) -> bool:
    """Whether pint reads a spelling as an amount per volume (a molar concentration)."""
    try:
        return ureg.Unit(units).dimensionality == MOLAR
    except (pint.PintError, ValueError, TypeError):
        return False


for spelling in ["µM", "umol/L", "nm", "ug/mL", "%", "n/a", "10 nM", ""]:
    print(f"{spelling!r:>9} -> {is_concentration(spelling)}")

# ---- 3. Test data with known faults ----
compounds = chemlib.library(N_COMPOUNDS, seed=COMPOUND_SEED)[["id", "smiles"]]
compounds = compounds.rename(columns={"id": "compound_id"})
compounds["inchikey"] = [Chem.MolToInchiKey(Chem.MolFromSmiles(s)) for s in compounds["smiles"]]
log.info("made %d compounds", len(compounds))
print(compounds.head(3).to_string(index=False))
def make_measurements(compounds: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """n synthetic measurements for random compounds, with consistent values, units and pChEMBL."""
    rng = np.random.default_rng(seed)
    rows = compounds.iloc[rng.integers(0, len(compounds), n)].reset_index(drop=True)
    potency = rng.normal(6.5, 1.2, n).clip(3.5, 10.5)  # on the pIC50 scale
    value_nm = 10 ** (9 - potency)
    micromolar = (value_nm >= 1_000) | (rng.random(n) < 0.2)
    units = np.where(micromolar, "µM", "nM")
    value = np.where(micromolar, value_nm / 1_000, value_nm)
    value = np.array([float(f"{v:.3g}") for v in value])  # three significant figures
    pchembl = np.round(9 - np.log10(np.where(micromolar, value * 1_000, value)), 2)
    pchembl[rng.random(n) < 0.1] = np.nan
    return pd.DataFrame(
        {
            "measurement_id": [f"M-{i:06d}" for i in range(1, n + 1)],
            "compound_id": rows["compound_id"],
            "smiles": rows["smiles"],
            "inchikey": rows["inchikey"],
            "target_id": rng.choice(TARGETS, n),
            "activity_type": rng.choice([t.value for t in ActivityType], n,
                                        p=[0.6, 0.2, 0.1, 0.1]),
            "value": value,
            "units": units,
            "pchembl": pchembl,
        }
    )


clean = make_measurements(compounds, N_MEASUREMENTS, seed=MEASUREMENT_SEED)
print(clean[["measurement_id", "compound_id", "target_id", "activity_type", "value", "units",
             "pchembl"]].head(4).to_string(index=False))
print(clean["units"].value_counts().to_dict())
FAULTS = {
    "µM written as uM": 30,
    "duplicate measurement": 20,
    "units missing": 15,
    "pchembl in wrong units": 12,
    "InChIKey of another compound": 8,
    "unknown compound": 6,
    "negative value": 5,
    "malformed InChIKey": 4,
}


def inject_faults(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    """A copy of df with FAULTS added, and a series saying which row has which ("" if none)."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    fault = pd.Series("", index=out.index)
    micromolar = out.index[out["units"] == "µM"]
    with_pchembl = out.index[out["pchembl"].notna() & (out["units"] == "µM")]
    used: set[int] = set()

    def pick(kind: str, pool: pd.Index) -> list[int]:
        """FAULTS[kind] rows from pool that have no fault yet."""
        free = [i for i in pool if i not in used]
        chosen = [int(i) for i in rng.choice(free, FAULTS[kind], replace=False)]
        used.update(chosen)
        if kind != "duplicate measurement":  # duplicates are new rows, added below
            fault[chosen] = kind
        return chosen

    for i in pick("units missing", out.index):
        out.loc[i, "units"] = None
    for i in pick("µM written as uM", micromolar):
        out.loc[i, "units"] = "uM"
    for i in pick("negative value", out.index):
        out.loc[i, "value"] = -out.loc[i, "value"]
    for i in pick("malformed InChIKey", out.index):
        out.loc[i, "inchikey"] = out.loc[i, "inchikey"][:-2]  # the final "-N" cut off
    for i in pick("InChIKey of another compound", out.index):
        others = compounds.loc[compounds["inchikey"] != out.loc[i, "inchikey"], "inchikey"]
        out.loc[i, "inchikey"] = others.iloc[int(rng.integers(len(others)))]
    for i in pick("pchembl in wrong units", with_pchembl):
        out.loc[i, "pchembl"] = round(9 - math.log10(out.loc[i, "value"]), 2)  # as if in nM
    for i in pick("unknown compound", out.index):
        out.loc[i, "compound_id"] = f"ML-9{i:07d}"
    copies = out.loc[pick("duplicate measurement", out.index)].copy()  # loaded a second time
    copies["measurement_id"] = [f"M-{len(out) + k:06d}" for k in range(1, len(copies) + 1)]
    out = pd.concat([out, copies], ignore_index=True)
    fault = pd.concat([fault, pd.Series("duplicate measurement", index=range(len(df), len(out)))])
    return out, fault


batch, truth = inject_faults(clean, seed=FAULT_SEED)
print(len(batch), "rows,", int((truth != "").sum()), "with a fault")
print(truth[truth != ""].value_counts().sort_index().to_string())

# ---- A schema for the whole table ----
INCHIKEY = r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$"


def pchembl_matches_value(df: pd.DataFrame) -> pd.Series:
    """True where pchembl is empty, cannot be checked yet, or equals 9 - log10(value in nM)."""
    factor = df["units"].map({u.value: f for u, f in NM_PER_UNIT.items()})
    checkable = df["pchembl"].notna() & factor.notna() & (df["value"] > 0)
    value_nm = (df["value"] * factor).where(checkable, 1.0)
    expected = 9 - np.log10(value_nm.astype(float))
    return ~checkable | ((df["pchembl"] - expected).abs() <= PCHEMBL_TOLERANCE)


def inchikey_matches_smiles(df: pd.DataFrame) -> pd.Series:
    """True where the InChIKey is malformed (another check reports it) or matches the SMILES."""
    keys = {s: Chem.MolToInchiKey(Chem.MolFromSmiles(s)) for s in df["smiles"].unique()}
    well_formed = df["inchikey"].str.match(INCHIKEY)
    return ~well_formed | (df["smiles"].map(keys) == df["inchikey"])


def measurement_schema(known_compounds: pd.Series) -> pa.DataFrameSchema:
    """The measurements contract, version 1.0.0, as a Pandera schema."""
    return pa.DataFrameSchema(
        {
            "measurement_id": pa.Column(str, pa.Check.str_matches(MEASUREMENT_ID), unique=True),
            "compound_id": pa.Column(str, [pa.Check.str_matches(COMPOUND_ID),
                                           pa.Check.isin(known_compounds.tolist())]),
            "smiles": pa.Column(str),
            "inchikey": pa.Column(str, pa.Check.str_matches(INCHIKEY)),
            "target_id": pa.Column(str, pa.Check.isin(TARGETS)),
            "activity_type": pa.Column(str, pa.Check.isin([t.value for t in ActivityType])),
            "value": pa.Column(float, pa.Check.gt(0)),
            "units": pa.Column(str, pa.Check.isin([u.value for u in Unit])),
            "pchembl": pa.Column(float, pa.Check.in_range(0, 14), nullable=True),
        },
        checks=[
            pa.Check(pchembl_matches_value, name="pchembl_matches_value"),
            pa.Check(inchikey_matches_smiles, name="inchikey_matches_smiles"),
        ],
        unique=["compound_id", "target_id", "activity_type", "value", "units"],
        report_duplicates="exclude_first",
        strict=True,
        name=f"measurements {CONTRACT['version']}",
    )


schema = measurement_schema(compounds["compound_id"])
print("schema columns match the contract:", list(schema.columns) == list(CONTRACT["columns"]))
log.info("the clean table passes: %d rows", len(schema.validate(clean)))

# ---- Lazy validation: every failure at once ----
try:
    schema.validate(batch, lazy=True)
except pa.errors.SchemaErrors as error:
    failures = error.failure_cases
print(len(failures), "failure cases")
print(failures[["column", "check", "failure_case", "index"]].head(6).to_string(index=False))
def label(row: pd.Series) -> str:
    """A short name for a failed check: the column (for column checks) and the check's name."""
    check = str(row["check"]).split("(")[0]
    if row["schema_context"] == "Column":
        return f"{row['column']}: {check}"
    return check


failures["label"] = failures.apply(label, axis=1)
failed_rows = failures.dropna(subset=["index"]).drop_duplicates(["label", "index"])
by_check = failed_rows.groupby("label").size().sort_values(ascending=False)
print(by_check.to_string())
caught = set(failed_rows["index"].astype(int))
injected = set(truth.index[truth != ""])
print("injected faults caught:", len(injected & caught), "of", len(injected))
print("clean rows flagged:", len(caught - injected))

# ---- Quarantine the failing rows, keep the rest ----
reasons = failed_rows.groupby("index")["label"].apply(lambda s: "; ".join(sorted(s)))
reasons.index = reasons.index.astype(int)
quarantine = batch.loc[reasons.index].assign(reason=reasons)
kept = batch.drop(index=reasons.index)
schema.validate(kept, lazy=True)  # raises if anything that fails is still there
log.info("kept %d rows, quarantined %d", len(kept), len(quarantine))
print(quarantine[["measurement_id", "units", "value", "reason"]].head(4).to_string(index=False))
DB_PATH.unlink(missing_ok=True)
with duckdb.connect(str(DB_PATH)) as db:
    db.execute("CREATE TABLE measurements AS SELECT * FROM kept")
    db.execute("CREATE TABLE quarantine AS SELECT ? AS batch_id, * FROM quarantine", [BATCH_ID])
    for row in db.sql(
        "SELECT batch_id, reason, count(*) AS n_rows FROM quarantine "
        "GROUP BY ALL ORDER BY n_rows DESC, reason"
    ).fetchall():
        print(row)

# ---- Stop the batch, or let it through? ----
@dataclass(frozen=True, slots=True)
class BatchDecision:
    """What was decided about one batch, and the numbers it was decided on."""

    batch_id: str
    n_rows: int
    n_failed: int
    action: str  # "load" or "stop"


def decide(batch_id: str, n_rows: int, n_failed: int,
           max_failed_share: float = MAX_FAILED_SHARE) -> BatchDecision:
    """Load the batch if its share of failing rows is within the threshold, otherwise stop it."""
    action = "load" if n_failed / n_rows <= max_failed_share else "stop"
    return BatchDecision(batch_id, n_rows, n_failed, action)


supplier_manifest = {"file": f"{BATCH_ID}.csv", "rows": 5_020}
print("rows agree with the manifest:",
      len(kept) + len(quarantine) == len(batch) == supplier_manifest["rows"])
decision = decide(BATCH_ID, len(batch), len(quarantine))
log.info("%s: %d of %d rows failed (%.2f%%), %s", decision.batch_id, decision.n_failed,
         decision.n_rows, 100 * decision.n_failed / decision.n_rows, decision.action)
print(decision)

try:
    schema.validate(batch.drop(columns="units"), lazy=True)
except pa.errors.SchemaErrors as error:
    missing = error.failure_cases.query("check == 'column_in_dataframe'")
    log.error("batch stopped, column missing: %s", missing["failure_case"].tolist())

# ---- 5. Records or tables? Measuring the difference ----
ACTIVITY_COLUMNS = ["target_id", "activity_type", "value", "units", "pchembl"]
activity_schema = pa.DataFrameSchema(
    {name: schema.columns[name] for name in ACTIVITY_COLUMNS},
    checks=[pa.Check(pchembl_matches_value, name="pchembl_matches_value")],
)
big = pd.concat([batch[ACTIVITY_COLUMNS]] * BENCHMARK_COPIES, ignore_index=True)


def as_records(df: pd.DataFrame) -> list[dict]:
    """One dictionary per row, with empty cells as None (what Pydantic expects)."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def failing_records(records: list[dict]) -> set[int]:
    """Validate every record as an Activity; the positions of the records that fail."""
    failed: set[int] = set()
    for i, record in enumerate(records):
        try:
            Activity.model_validate(record)
        except ValidationError:
            failed.add(i)
    return failed


def failing_rows(df: pd.DataFrame) -> set[int]:
    """Validate the table in one lazy pass; the positions of the rows that fail."""
    try:
        activity_schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as error:
        return set(error.failure_cases["index"].dropna().astype(int))
    return set()


start = time.perf_counter()
records = as_records(big)
to_records_s = time.perf_counter() - start
start = time.perf_counter()
by_record = failing_records(records)
pydantic_s = time.perf_counter() - start
start = time.perf_counter()
by_table = failing_rows(big)
pandera_s = time.perf_counter() - start
print(len(big), "rows;", len(by_record), "fail;", "same rows:", by_record == by_table)
per_million = 1_000_000 / len(big)
record_route = to_records_s + pydantic_s
print(f"rows to dictionaries:          {to_records_s:.2f} s")
print(f"Pydantic, one record at a time: {pydantic_s:.2f} s "
      f"({pydantic_s / len(big) * 1e6:.1f} microseconds per record)")
print(f"Pandera, one pass over the table: {pandera_s:.2f} s")
print(f"for a million rows: about {record_route * per_million:.1f} s one record at a time, "
      f"{pandera_s * per_million:.1f} s as a table ({record_route / pandera_s:.0f} times faster)")
