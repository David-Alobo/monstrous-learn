"""Chemical files and identity: the code of the lesson, in order.

SDF, SMILES, CSV and Parquet compared on one library, read safely at scale, and a stable identity (InChIKey) for every molecule so duplicates can be found.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/03-files-and-identity/
Run it from anywhere, e.g. from the series folder: uv run python 03-files-and-identity/code.py
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
import csv
import gzip
import hashlib
import io
import logging
import shutil
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from openbabel import pybel
from rdkit import Chem, RDLogger

import chemlib

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored)
WORK = Path("work")
# the teaching library of sections 1 to 6: its size and seed (same seed, same molecules)
LIBRARY_SIZE = 20_000
LIBRARY_SEED = 3
# the careless vendor's file (section 3): size, seeds, share of damaged records, bytes cut off
VENDOR_SIZE = 2_000
VENDOR_SEED = 5
VENDOR_DEFECT_RATE = 0.05
VENDOR_DEFECT_SEED = 6
TRUNCATED_BYTES = 300
# rows per Parquet row group when streaming an SDF (section 3); larger uses more memory
BATCH_SIZE = 5_000
# Parquet compression codec ("zstd" is small and fast; "snappy" is the common default)
PARQUET_COMPRESSION = "zstd"
# the supplier's shipment with added duplicates (section 5)
SHIPMENT_SIZE = 3_000
SHIPMENT_SEED = 7
SHIPMENT_DEFECT_RATE = 0.06
SHIPMENT_DEFECT_SEED = 8
# how many molecules to compare between RDKit and Open Babel (section 6)
TOOLKIT_SAMPLE = 1_000
# bytes read at a time when computing a checksum (section 7): 1 MiB
CHECKSUM_CHUNK = 1 << 20

WORK.mkdir(exist_ok=True)

# ---- 1. One library, five files ----
library = chemlib.library(LIBRARY_SIZE, seed=LIBRARY_SEED)
print(library.head(3).to_string(index=False))
def write_sdf(df: pd.DataFrame, path: Path) -> None:
    """Write a library as SDF: a connection table per molecule, the other columns as data fields."""
    with Chem.SDWriter(str(path)) as writer:
        for row in df.itertuples(index=False):
            mol = Chem.MolFromSmiles(row.smiles)
            mol.SetProp("_Name", row.id)  # the first line of the record
            mol.SetProp("vendor", row.vendor)
            mol.SetProp("price_usd", f"{row.price_usd:.2f}")
            mol.SetProp("stock_mg", str(row.stock_mg))
            writer.write(mol)


def write_smi(df: pd.DataFrame, path: Path) -> None:
    """Write a SMILES file: one SMILES and one name per line."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in df.itertuples(index=False):
            handle.write(f"{row.smiles} {row.id}\n")


def gzip_copy(path: Path) -> Path:
    """A gzipped copy of a file, as path + '.gz' (mtime=0: the same input gives the same bytes)."""
    target = path.with_name(path.name + ".gz")
    with path.open("rb") as source, gzip.GzipFile(target, "wb", mtime=0) as packed:
        shutil.copyfileobj(source, packed)
    return target


SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("smiles", pa.string()),
        ("vendor", pa.string()),
        ("price_usd", pa.float64()),
        ("stock_mg", pa.int64()),
    ]
)

files = {
    "SDF": WORK / "library.sdf",
    "SMILES": WORK / "library.smi",
    "CSV": WORK / "library.csv",
    "Parquet": WORK / "library.parquet",
}
write_sdf(library, files["SDF"])
files["SDF (gzip)"] = gzip_copy(files["SDF"])
write_smi(library, files["SMILES"])
library.to_csv(files["CSV"], index=False)
table = pa.Table.from_pandas(library, schema=SCHEMA, preserve_index=False)
pq.write_table(table, files["Parquet"], compression=PARQUET_COMPRESSION)

for name, path in files.items():
    size = path.stat().st_size
    print(f"{name:11} {size / 1e6:6.2f} MB  {size / len(library):6.0f} bytes per molecule")
def read_sdf_table(path: Path) -> pd.DataFrame:
    """Read every record of an SDF (plain or gzipped) into a table of its name and data fields."""
    opener = gzip.open if path.suffix == ".gz" else open
    rows = []
    with opener(path, "rb") as handle:
        for mol in Chem.ForwardSDMolSupplier(handle):
            rows.append({"id": mol.GetProp("_Name"), **mol.GetPropsAsDict()})
    return pd.DataFrame(rows)


readers = {
    "SDF": read_sdf_table,
    "SMILES": lambda path: pd.read_csv(path, sep=" ", names=["smiles", "id"]),
    "CSV": pd.read_csv,
    "Parquet": pd.read_parquet,
}
tables = {}
for name, reader in readers.items():
    start = time.perf_counter()
    tables[name] = reader(files[name])
    seconds = time.perf_counter() - start
    print(f"{name:11} {seconds:6.3f} s  {len(tables[name]):,} rows")

# ---- 2. What each format keeps and loses ----
print(pq.read_schema(files["Parquet"]).remove_metadata())
print("Parquet round trip equal:", tables["Parquet"].equals(library))
print("CSV round trip equal:    ", tables["CSV"].equals(library))
print("SMILES file columns:     ", list(tables["SMILES"].columns))
print("SDF columns and types:   ", tables["SDF"].dtypes.astype(str).to_dict())
mol = Chem.MolFromSmiles("CCO")
mol.SetProp("catalogue_no", "00417")
print(mol.GetPropsAsDict())
mol.SetDoubleProp("price_usd", 57.66)
buffer = io.StringIO()
with Chem.SDWriter(buffer) as writer:
    writer.write(mol)
print(buffer.getvalue().split("M  END")[1])

# ---- 3. Reading an SDF the way industry does ----
RDLogger.DisableLog("rdApp.*")  # we record every failure ourselves, below


def write_unchecked_sdf(df: pd.DataFrame, path: Path) -> None:
    """Write an SDF without checking valences, as some tools do; skip SMILES that cannot be read."""
    no_valence_check = Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES
    written = skipped = 0
    with Chem.SDWriter(str(path)) as writer:
        for row in df.itertuples(index=False):
            mol = Chem.MolFromSmiles(row.smiles, sanitize=False)
            if mol is None:
                skipped += 1
                continue
            Chem.SanitizeMol(mol, no_valence_check)
            mol.SetProp("_Name", row.id)
            mol.SetProp("vendor", row.vendor)
            mol.SetProp("price_usd", f"{row.price_usd:.2f}")
            mol.SetProp("stock_mg", str(row.stock_mg))
            writer.write(mol)
            written += 1
    log.info("wrote %d records to %s; skipped %d unreadable SMILES", written, path.name, skipped)


vendor_library = chemlib.library(VENDOR_SIZE, seed=VENDOR_SEED)
received = chemlib.add_defects(vendor_library, rate=VENDOR_DEFECT_RATE, seed=VENDOR_DEFECT_SEED)
print(received["defect"].value_counts().to_string())
vendor_file = WORK / "vendor.sdf"
write_unchecked_sdf(received, vendor_file)
vendor_file.write_bytes(vendor_file.read_bytes()[:-TRUNCATED_BYTES])  # the download stopped early
def records(path: Path) -> Iterator[tuple[int, Chem.Mol | None, str]]:
    """Yield (record number, molecule or None, reason it failed) for each record of an SDF."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as handle:
        for number, mol in enumerate(Chem.ForwardSDMolSupplier(handle, sanitize=False)):
            if mol is None:
                yield number, None, "the record could not be parsed"
                continue
            try:
                Chem.SanitizeMol(mol)
            except Chem.MolSanitizeException as error:  # keep RDKit's message
                yield number, None, str(error).splitlines()[0]
                continue
            yield number, mol, ""


read, reasons = 0, Counter()
for number, mol, reason in records(vendor_file):
    if mol is None:
        log.warning("record %d failed: %s", number, reason)
        reasons[reason] += 1
    else:
        read += 1
log.info("%d molecules read; %d records failed", read, reasons.total())
for reason, count in reasons.most_common():
    print(f"{count:3}  {reason}")

# ---- Properties as typed columns ----
ROW_SCHEMA = pa.schema(
    [
        ("record", pa.int64()),
        ("id", pa.string()),
        ("smiles", pa.string()),
        ("inchikey", pa.string()),
        ("vendor", pa.string()),
        ("price_usd", pa.float64()),
        ("stock_mg", pa.int64()),
    ]
)


def typed_row(number: int, mol: Chem.Mol) -> dict:
    """One SDF record as a row of values with the types we chose, not the types a guesser picked."""
    return {
        "record": number,
        "id": mol.GetProp("_Name"),
        "smiles": Chem.MolToSmiles(mol),
        "inchikey": Chem.MolToInchiKey(mol),
        "vendor": mol.GetProp("vendor"),
        "price_usd": float(mol.GetProp("price_usd")),
        "stock_mg": int(mol.GetProp("stock_mg")),
    }


def sdf_to_parquet(
    source: Path, target: Path, batch_size: int = BATCH_SIZE
) -> list[tuple[int, str]]:
    """Stream an SDF into Parquet one batch at a time; return the records that failed."""
    failures, batch, rows = [], [], 0
    with pq.ParquetWriter(target, ROW_SCHEMA, compression=PARQUET_COMPRESSION) as writer:
        for number, mol, reason in records(source):
            if mol is None:
                log.warning("record %d failed: %s", number, reason)
                failures.append((number, reason))
                continue
            batch.append(typed_row(number, mol))
            if len(batch) == batch_size:
                writer.write_table(pa.Table.from_pylist(batch, schema=ROW_SCHEMA))
                rows += len(batch)
                batch = []
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=ROW_SCHEMA))
            rows += len(batch)
    log.info("wrote %d rows to %s; %d records failed", rows, target.name, len(failures))
    return failures


keys_file = WORK / "library-keys.parquet"
sdf_to_parquet(files["SDF (gzip)"], keys_file)
print("row groups (one per batch):", pq.ParquetFile(keys_file).metadata.num_row_groups)
compounds = pd.read_parquet(keys_file)
print(compounds[["id", "inchikey", "price_usd", "stock_mg"]].head(3).to_string(index=False))

# ---- 4. CSV and chemistry ----
catalogue = [
    {"catalogue_no": "00417", "name": "2,4-dichlorophenol", "smiles": "Oc1ccc(Cl)cc1Cl",
     "price": "$12.50", "storage": "2–8 °C"},
    {"catalogue_no": "01203", "name": "acetonitrile", "smiles": "CC#N",
     "price": "$8.00", "storage": "15–25 °C"},
    {"catalogue_no": "00090", "name": "4'-hydroxyacetophenone", "smiles": "CC(=O)c1ccc(O)cc1",
     "price": "$1,250.00", "storage": "15–25 °C"},
]
csv_file = WORK / "catalogue.csv"
with open(csv_file, "w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(catalogue[0]))
    writer.writeheader()
    writer.writerows(catalogue)
print(csv_file.read_text(encoding="utf-8"))
header, *lines = csv_file.read_text(encoding="utf-8").splitlines()
print(len(header.split(",")), "columns in the header")
for line in lines:
    print(len(line.split(",")), "fields:", line.split(",")[:3])
guessed = pd.read_csv(csv_file)
print(guessed.dtypes.astype(str).to_dict())
print("catalogue numbers:", guessed["catalogue_no"].tolist())
print("prices:", guessed["price"].tolist())
print(pd.read_csv(csv_file, comment="#")["smiles"].tolist())
old_file = WORK / "catalogue-cp1252.csv"
old_file.write_bytes(csv_file.read_text(encoding="utf-8").encode("cp1252"))
try:
    pd.read_csv(old_file)
except UnicodeDecodeError as error:
    print("UnicodeDecodeError:", error.reason)
print(pd.read_csv(old_file, encoding="cp1252")["storage"].tolist())
clean = pd.read_csv(csv_file, dtype={"catalogue_no": str}, encoding="utf-8")
clean["price_usd"] = clean.pop("price").str.replace("[$,]", "", regex=True).astype(float)
CATALOGUE_SCHEMA = pa.schema(
    [
        ("catalogue_no", pa.string()),
        ("name", pa.string()),
        ("smiles", pa.string()),
        ("storage", pa.string()),
        ("price_usd", pa.float64()),
    ]
)
catalogue_file = WORK / "catalogue.parquet"
clean_table = pa.Table.from_pandas(clean, schema=CATALOGUE_SCHEMA, preserve_index=False)
pq.write_table(clean_table, catalogue_file)
print(pd.read_parquet(catalogue_file).to_string(index=False))
print("total price:", pd.read_parquet(catalogue_file)["price_usd"].sum())

# ---- 5. Identity and duplicates ----
print("distinct SMILES as written:", library["smiles"].nunique())
print("distinct canonical SMILES: ", compounds["smiles"].nunique())
print("distinct InChIKeys:        ", compounds["inchikey"].nunique())
sizes = compounds.groupby("inchikey").size()
print("molecules listed twice:", int((sizes == 2).sum()))
print("molecules listed more than twice:", int((sizes > 2).sum()))
first_key = sizes[sizes == 2].index[0]
pair = compounds.loc[compounds["inchikey"] == first_key, ["id", "inchikey"]]
pair = pair.merge(library[["id", "smiles"]], on="id")
print(pair.to_string(index=False))
def inchikey(smiles: str) -> str | None:
    """The InChIKey of a SMILES, or None if RDKit cannot read it."""
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToInchiKey(mol) if mol is not None else None


shipment_library = chemlib.library(SHIPMENT_SIZE, seed=SHIPMENT_SEED)
shipment = chemlib.add_defects(
    shipment_library, rate=SHIPMENT_DEFECT_RATE, seed=SHIPMENT_DEFECT_SEED
)
shipment["inchikey"] = shipment["smiles"].map(inchikey)
added = shipment["defect"] == "duplicate"
same_string = shipment["smiles"].duplicated(keep=False)
same_key = shipment["inchikey"].notna() & shipment["inchikey"].duplicated(keep=False)
print("duplicates added:", int(added.sum()))
print("rows sharing a SMILES string with another row:", int(same_string.sum()))
print("rows sharing an InChIKey with another row:    ", int(same_key.sum()))
print("every added duplicate found:", bool(same_key[added].all()))
added_keys = set(shipment.loc[added, "inchikey"])
from_added = same_key & shipment["inchikey"].isin(added_keys)
print("rows that are an added duplicate or its original:", int(from_added.sum()))
example = shipment.loc[added, "id"].iloc[0].removesuffix("-dup")
copies = shipment[shipment["id"].str.startswith(example)]
print(copies[["id", "smiles", "inchikey"]].to_string(index=False))

# ---- 6. Toolkits disagree ----
pybel.ob.obErrorLog.SetOutputLevel(0)  # quiet: we compare the results ourselves


def rdkit_canonical(smiles: str) -> str:
    """RDKit's canonical SMILES."""
    return Chem.MolToSmiles(Chem.MolFromSmiles(smiles))


def openbabel_canonical(smiles: str) -> str:
    """Open Babel's canonical SMILES (its output is the SMILES, a tab, then a title)."""
    return pybel.readstring("smi", smiles).write("can").split("\t")[0].strip()


rows = []
for smiles in library["smiles"].head(TOOLKIT_SAMPLE):
    rd, ob = rdkit_canonical(smiles), openbabel_canonical(smiles)
    rows.append(
        {
            "same canonical SMILES": rd == ob,
            "RDKit agrees with itself": rdkit_canonical(ob) == rd,
            "Open Babel agrees with itself": openbabel_canonical(rd) == ob,
            "same InChIKey": inchikey(rd) == inchikey(ob),
        }
    )
print(pd.DataFrame(rows).sum().to_string())
print("RDKit:     ", rd)
print("Open Babel:", ob)

# ---- 7. Did the file arrive unchanged? ----
def sha256(path: Path, chunk_size: int = CHECKSUM_CHUNK) -> str:
    """The SHA-256 checksum of a file, read a chunk at a time so any size of file fits."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(paths: list[Path], manifest: Path) -> None:
    """Write a manifest: one line per file, its checksum then its name (as sha256sum writes)."""
    lines = [f"{sha256(path)}  {path.name}\n" for path in paths]
    manifest.write_text("".join(lines), encoding="utf-8")
    log.info("wrote the checksums of %d files to %s", len(lines), manifest.name)


def verify(manifest: Path) -> list[str]:
    """Check every file listed in a manifest; return the names whose checksum no longer matches."""
    changed = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if sha256(manifest.parent / name) != expected:
            log.warning("%s: checksum does not match the manifest", name)
            changed.append(name)
    return changed


manifest = WORK / "SHA256SUMS"
write_checksums([files["SMILES"], files["Parquet"]], manifest)
print(manifest.read_text(encoding="utf-8"), end="")
print("changed files:", verify(manifest))
text = files["SMILES"].read_text(encoding="utf-8")
files["SMILES"].write_text(text.replace("Cl", "Br", 1), encoding="utf-8", newline="\n")
print("same size:", files["SMILES"].stat().st_size == len(text.encode("utf-8")))
print("changed files:", verify(manifest))
