"""Libraries larger than memory: the code of the lesson, in order.

Stream molecules in batches, write a partitioned Parquet dataset and query it with DuckDB, so a library far larger than memory is processed in a fixed amount of memory.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/08-larger-than-memory/
Run it from anywhere, e.g. from the series folder: uv run python 08-larger-than-memory/code.py
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
import logging
import re
import shutil
import sys
import threading
import time
import tracemalloc
from collections import Counter, defaultdict, deque, namedtuple
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from itertools import chain, groupby, islice
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psutil
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from rdkit import Chem
from rdkit.Chem import Descriptors, rdFingerprintGenerator

import chemlib

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson writes its files (git-ignored)
WORK = Path("work")
SAMPLE_CSV = WORK / "sample.csv"
SAMPLE_PARQUET = WORK / "sample.parquet"
STREAMED = WORK / "stream.parquet"  # the streamed library, made in section 3
LOADED = WORK / "load-everything.parquet"  # the same, made by loading everything
DESCRIPTORS = WORK / "descriptors.parquet"
DATASET = WORK / "library"  # the partitioned dataset of section 5

SAMPLE_SIZE = 20_000  # molecules measured in sections 1 and 4; any size up to chemlib.size()
SEED = 8  # which sample; change it for different molecules
N_RECORDS = 100_000  # records built in section 2 to measure containers
N_MOLECULES = 300_000  # molecules streamed into Parquet; chemlib.size() streams them all
BATCH = 25_000  # molecules per batch: sets the streaming memory, whatever N_MOLECULES is
REBATCH = 12_000  # the batch size a later step wants, in the itertools example
DELIVERIES = [(30_000, 0), (20_000, 1_000_000)]  # (molecules, first molecule) of two deliveries
FP_RADIUS, FP_BITS = 2, 2048  # Morgan fingerprint settings
WATCH_SECONDS = 0.005  # how often the memory watcher looks at the process

N_CHECKED = 100_000  # molecules checked for defects while streaming, in batches of CHECK_BATCH
CHECK_BATCH = 10_000
DEFECT_RATE = 0.02  # share of damaged records in a normal delivery
WORSE_RATE = 0.08  # ... and in the later batches, from a supplier's worse export
WORSE_FROM = 6  # the first batch (counting from 0) of the worse export
WINDOW = 3  # how many recent batches the rolling defect rate covers
ALERT_SHARE = 0.03  # warn when the rolling defect rate is above this

RDKIT_N, RDKIT_BATCH, RDKIT_START = 20_000, 5_000, 1_000_000  # the RDKit streaming example
ROW_GROUP = 20_000  # rows per Parquet row group in the dataset; 100,000 to 1,000,000 in production
DUCKDB_MEMORY = "200MB"  # the memory limit DuckDB is held to in section 6

WORK.mkdir(exist_ok=True)
print(f"the generator can make {chemlib.size():,} molecules; we stream {N_MOLECULES:,} "
      f"in batches of {BATCH:,}")

# ---- What one molecule costs ----
sample = chemlib.library(SAMPLE_SIZE, seed=SEED)
sample.to_csv(SAMPLE_CSV, index=False)
pq.write_table(pa.Table.from_pandas(sample, preserve_index=False), SAMPLE_PARQUET,
               compression="zstd")
text_as_objects = sample.astype({"id": object, "smiles": object, "vendor": object})

sizes = {
    "CSV file": SAMPLE_CSV.stat().st_size,
    "Parquet file (zstd)": SAMPLE_PARQUET.stat().st_size,
    "Arrow table": pa.Table.from_pandas(sample, preserve_index=False).nbytes,
    "pandas, Arrow text": sample.memory_usage(deep=True).sum(),
    "pandas, Python text": text_as_objects.memory_usage(deep=True).sum(),
}
for name, size in sizes.items():
    print(f"{name:22}{size / 1e6:6.1f} MB {size / len(sample):6.0f} bytes per molecule")

# ---- Molecules and fingerprints cost more ----
process = psutil.Process()
before = process.memory_info().rss
molecules = [Chem.MolFromSmiles(smiles) for smiles in sample["smiles"]]
after = process.memory_info().rss
per_molecule = (after - before) / len(molecules)
print(f"{len(molecules):,} RDKit molecules: about {(after - before) / 1e6:.0f} MB, "
      f"{per_molecule:,.0f} bytes each")
morgan = rdFingerprintGenerator.GetMorganGenerator(radius=FP_RADIUS, fpSize=FP_BITS)
fingerprints = np.array([morgan.GetFingerprintAsNumPy(m) for m in molecules], dtype=np.uint8)
packed = np.packbits(fingerprints, axis=1)
print("one byte per bit:", fingerprints.shape, f"{fingerprints.nbytes / 1e6:.1f} MB")
print("packed bits:     ", packed.shape, f"{packed.nbytes / 1e6:.1f} MB")

full = chemlib.size()
for name in ["pandas, Arrow text", "pandas, Python text"]:
    print(f"all {full:,} molecules, {name}: {full * sizes[name] / len(sample) / 1e9:.2f} GB")
print(f"all {full:,} molecules, fingerprints one byte per bit: {full * FP_BITS / 1e9:.2f} GB")

# ---- Measure before optimising ----
source = chemlib.library(N_RECORDS, seed=SEED)
FIELDS = list(source.columns)
rows = list(zip(*(source[name].tolist() for name in FIELDS)))  # plain tuples of Python values

tracemalloc.start()
as_dicts = [dict(zip(FIELDS, row)) for row in rows]
cheap = [record for record in as_dicts if record["price_usd"] < 50]
snapshot = tracemalloc.take_snapshot()
del as_dicts
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"{len(cheap):,} cheap records kept")
print(f"peak {peak / 1e6:.1f} MB, still held {current / 1e6:.1f} MB")
for stat in snapshot.statistics("lineno")[:2]:
    print(f"line {stat.traceback[0].lineno}: {stat.size / 1e6:.1f} MB "
          f"in {stat.count:,} allocations")

# ---- One record, four containers ----
Molecule = namedtuple("Molecule", FIELDS)


@dataclass(frozen=True)
class MoleculeRecord:
    """One catalogue record, as an ordinary dataclass."""

    id: str
    smiles: str
    vendor: str
    price_usd: float
    stock_mg: int


@dataclass(frozen=True, slots=True)
class SlottedRecord:
    """The same record, with slots: a fixed set of fields and no per-instance dictionary."""

    id: str
    smiles: str
    vendor: str
    price_usd: float
    stock_mg: int


def bytes_per_record(build: Callable[[tuple], object]) -> float:
    """Memory tracemalloc sees while one container is built per row, divided by the rows."""
    tracemalloc.start()
    made = [build(row) for row in rows]
    current, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return current / len(made)


containers = {
    "dict": lambda row: dict(zip(FIELDS, row)),
    "dataclass": lambda row: MoleculeRecord(*row),
    "named tuple": Molecule._make,
    "dataclass, slots": lambda row: SlottedRecord(*row),
}
costs = {name: bytes_per_record(build) for name, build in containers.items()}
for name, cost in costs.items():
    print(f"{name:17}{cost:5.0f} bytes per record, {cost / costs['dict']:.2f} of a dict")
saved = (costs["dict"] - costs["dataclass, slots"]) * chemlib.size()
print(f"slots instead of dicts for all {chemlib.size():,} molecules: {saved / 1e6:.0f} MB less")
print(Molecule._make(rows[0]))

# ---- Generators make data only when asked ----
batches = chemlib.stream(N_MOLECULES, batch=BATCH)
print(type(batches).__name__)
first = next(batches)
print(len(first), "rows in the first batch; the other batches do not exist yet")
print(first.head(3).to_string(index=False))

# ---- A processing step that works on one batch ----
ATOM = r"\[[^\]]+\]|Br|Cl|[BCNOPSFI]|[bcnops]"
HALOGEN = r"Br|Cl|F|I"


def add_columns(batch: pd.DataFrame) -> pd.DataFrame:
    """Add heavy-atom and halogen counts, worked out from each SMILES string."""
    out = batch.copy()
    out["heavy_atoms"] = out["smiles"].str.count(ATOM).astype("int16")
    out["halogens"] = out["smiles"].str.count(HALOGEN).astype("int16")
    return out


checked = add_columns(sample)
rdkit_counts = [m.GetNumHeavyAtoms() for m in molecules]
print("heavy atoms agree with RDKit for all 20,000:",
      bool((checked["heavy_atoms"] == rdkit_counts).all()))

# ---- Batches of any size, with itertools ----
def batched(items: Iterable, size: int) -> Iterator[list]:
    """Cut any iterable into lists of `size` items (the last may be shorter), lazily."""
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


deliveries = (chemlib.stream(n, batch=CHECK_BATCH, start=s) for n, s in DELIVERIES)
rows_in_order = chain.from_iterable(b.itertuples(index=False) for b in chain(*deliveries))
for k, batch in enumerate(batched(rows_in_order, REBATCH)):
    log.info("batch %d: %s rows, %s to %s", k, f"{len(batch):,}", batch[0].id, batch[-1].id)
by_id = checked.itertuples(index=False)
runs = sum(1 for _ in groupby(by_id, key=lambda row: row.heavy_atoms))
print(f"groups in id order: {runs:,}")

by_size = checked.sort_values(["heavy_atoms", "id"]).itertuples(index=False)
for heavy_atoms, group in islice(groupby(by_size, key=lambda row: row.heavy_atoms), 4):
    members = list(group)  # this group only, not the whole table
    cheapest = min(members, key=lambda row: row.price_usd)
    print(f"{heavy_atoms} heavy atoms: {len(members):>4,} molecules, "
          f"cheapest {cheapest.id} at ${cheapest.price_usd:.2f}")

# ---- Writing batch by batch ----
def peak_memory(job: Callable[..., None], *args: object) -> int:
    """Run job(*args) and return the most memory (bytes) the process held above its start."""
    start = process.memory_info().rss
    peak = start
    done = threading.Event()

    def watch() -> None:
        nonlocal peak
        while not done.is_set():
            peak = max(peak, process.memory_info().rss)
            time.sleep(WATCH_SECONDS)

    watcher = threading.Thread(target=watch)
    watcher.start()
    try:
        job(*args)
    finally:
        done.set()
        watcher.join()
    return max(peak, process.memory_info().rss) - start
SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("smiles", pa.string()),
        ("vendor", pa.string()),
        ("price_usd", pa.float64()),
        ("stock_mg", pa.int64()),
        ("heavy_atoms", pa.int16()),
        ("halogens", pa.int16()),
    ]
)


def load_everything(path: Path, n: int) -> None:
    """Make every row first, then process and write them all at once."""
    everything = pd.concat(list(chemlib.stream(n, batch=BATCH)), ignore_index=True)
    table = pa.Table.from_pandas(add_columns(everything), schema=SCHEMA, preserve_index=False)
    pq.write_table(table, path, compression="zstd")


def stream_to_parquet(path: Path, n: int) -> None:
    """Make, process and write one batch at a time."""
    with pq.ParquetWriter(path, SCHEMA, compression="zstd") as writer:
        for batch in chemlib.stream(n, batch=BATCH):
            table = pa.Table.from_pandas(add_columns(batch), schema=SCHEMA, preserve_index=False)
            writer.write_table(table)


stream_to_parquet(WORK / "warm-up.parquet", BATCH)  # one small run, so start-up costs don't count
peaks = {
    "stream": peak_memory(stream_to_parquet, STREAMED, N_MOLECULES),
    "load everything": peak_memory(load_everything, LOADED, N_MOLECULES),
}
for name, peak in peaks.items():
    log.info("%-16s peak %5.0f MB above the start", name, peak / 1e6)
streamed = pq.ParquetFile(STREAMED)
loaded = pq.read_table(LOADED)
print("rows:", streamed.metadata.num_rows, " row groups:", streamed.metadata.num_row_groups)
print("same contents:", streamed.read().equals(loaded))

# ---- Counting while streaming: Counter, defaultdict and deque ----
ELEMENT = r"Br|Cl|Se|[BCNOPSFI]|[bcnops]"  # aromatic atoms are written in lower case

defects = Counter()
elements = Counter()
flagged = defaultdict(list)  # defect kind -> ids of the records that have it
recent = deque(maxlen=WINDOW)  # defect rate of the last WINDOW batches
for k, batch in enumerate(chemlib.stream(N_CHECKED, batch=CHECK_BATCH)):
    rate = DEFECT_RATE if k < WORSE_FROM else WORSE_RATE
    batch = chemlib.add_defects(batch, rate=rate, seed=SEED + k)
    bad = batch[batch["defect"] != ""]
    defects.update(bad["defect"])
    for kind, molecule_id in zip(bad["defect"], bad["id"], strict=True):
        flagged[kind].append(molecule_id)
    for smiles in batch["smiles"]:
        elements.update(symbol.capitalize() for symbol in re.findall(ELEMENT, smiles))
    recent.append(len(bad) / len(batch))
    rolling = sum(recent) / len(recent)
    log.info("batch %d: %4.1f%% defective, last %d batches %4.1f%%",
             k, 100 * recent[-1], len(recent), 100 * rolling)
    if rolling > ALERT_SHARE:
        log.warning("rolling defect rate %.1f%% is above %.0f%%", 100 * rolling, 100 * ALERT_SHARE)
print("defects:", defects.most_common())
print("elements:", elements.most_common())
for kind, ids in sorted(flagged.items()):
    print(f"{kind:9} {len(ids):>4} records, first {ids[0]}")
print("the rolling window holds", len(recent), "rates:", [f"{r:.3f}" for r in recent])

# ---- The same pattern with RDKit ----
def describe(batch: pd.DataFrame) -> pd.DataFrame:
    """Canonical SMILES, molecular weight and polar surface area for one batch."""
    mols = [Chem.MolFromSmiles(s) for s in batch["smiles"]]
    return pd.DataFrame(
        {
            "id": batch["id"].to_numpy(),
            "canonical_smiles": [Chem.MolToSmiles(m) for m in mols],
            "mw": [round(Descriptors.MolWt(m), 2) for m in mols],
            "tpsa": [round(Descriptors.TPSA(m), 2) for m in mols],
        }
    )


writer = None
for batch in chemlib.stream(RDKIT_N, batch=RDKIT_BATCH, start=RDKIT_START):
    table = pa.Table.from_pandas(describe(batch), preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(DESCRIPTORS, table.schema, compression="zstd")
    writer.write_table(table)
writer.close()

described = pq.read_table(DESCRIPTORS)
log.info("wrote %d rows in %d row groups to %s", described.num_rows,
         pq.ParquetFile(DESCRIPTORS).num_row_groups, DESCRIPTORS.as_posix())
print(described.slice(0, 3).to_pandas().to_string(index=False))

# ---- Smaller numbers, checked ----
def smallest_int(values: pd.Series) -> pd.Series:
    """The column in the smallest integer type that holds every value (checked, not assumed)."""
    for dtype in (np.uint8, np.int8, np.uint16, np.int16, np.uint32, np.int32):
        limits = np.iinfo(dtype)
        if limits.min <= values.min() and values.max() <= limits.max:
            return values.astype(dtype)
    return values


damaged = add_columns(chemlib.add_defects(sample, rate=DEFECT_RATE, seed=SEED))
compact = damaged.copy()
for name in ["stock_mg", "heavy_atoms", "halogens"]:
    compact[name] = smallest_int(damaged[name])
    print(f"{name:12} {damaged[name].min():>3} to {damaged[name].max():>3}: "
          f"{damaged[name].dtype} -> {compact[name].dtype}")
compact["price_usd"] = damaged["price_usd"].astype(np.float32)
back = compact["price_usd"].astype(np.float64).round(2)
print("float32 prices give back every price to the cent:", bool((back == damaged["price_usd"]).all()))

# ---- Categories for repeated text ----
compact = compact.astype({"vendor": "category", "defect": "category"})
print(compact["defect"].cat.categories.tolist(), compact["defect"].cat.codes.dtype)

memory = pd.DataFrame(
    {
        "before": damaged.dtypes.astype(str),
        "bytes per row": damaged.memory_usage(deep=True, index=False) / len(damaged),
        "after": compact.dtypes.astype(str),
        "bytes per row, after": compact.memory_usage(deep=True, index=False) / len(compact),
    }
)
print(memory.round(1).to_string())
total_before = damaged.memory_usage(deep=True).sum()
total_after = compact.memory_usage(deep=True).sum()
print(f"whole table: {total_before / 1e6:.2f} MB -> {total_after / 1e6:.2f} MB, "
      f"{total_after / total_before:.0%} of the original")

# ---- Dictionary encoding in Arrow and Parquet ----
vendor_table = pa.Table.from_pandas(compact[["vendor"]], preserve_index=False)
print(vendor_table.schema.field("vendor").type)
for use_dictionary in [True, False]:
    path = WORK / f"vendor-dictionary-{use_dictionary}.parquet"
    pq.write_table(vendor_table, path, compression="none", use_dictionary=use_dictionary)
    column = pq.ParquetFile(path).metadata.row_group(0).column(0)
    print(f"use_dictionary={use_dictionary!s:5} {column.total_uncompressed_size / 1e3:6.1f} kB, "
          f"encodings {sorted(column.encodings)}")

# ---- One copy of each string: `sys.intern` ----
with SAMPLE_CSV.open(encoding="utf-8", newline="") as handle:
    vendors = [row["vendor"] for row in csv.DictReader(handle)]
interned = [sys.intern(vendor) for vendor in vendors]
print(f"{len(vendors):,} vendor names: {len({id(v) for v in vendors}):,} string objects as read, "
      f"{len({id(v) for v in interned})} after sys.intern")

# ---- Writing it with PyArrow ----
shutil.rmtree(DATASET, ignore_errors=True)
ds.write_dataset(
    ds.dataset(STREAMED, format="parquet"),
    DATASET,
    format="parquet",
    partitioning=["vendor"],
    partitioning_flavor="hive",
    file_options=ds.ParquetFileFormat().make_write_options(compression="zstd"),
    max_rows_per_group=ROW_GROUP,
    min_rows_per_group=ROW_GROUP,
    preserve_order=True,
)
for path in sorted(DATASET.rglob("*.parquet")):
    meta = pq.ParquetFile(path).metadata
    print(path.relative_to(WORK).as_posix(), f"{meta.num_rows:,} rows,",
          meta.num_row_groups, "row groups")

# ---- Reading back only what you need ----
library = ds.dataset(DATASET, format="parquet", partitioning="hive")
print(library.schema.names)
print(f"{library.count_rows():,} rows in {len(library.files)} files")
wanted = (
    (pc.field("vendor") == "Vendor B")
    & (pc.field("heavy_atoms") <= 20)
    & (pc.field("halogens") == 0)
)
small = library.to_table(columns=["id", "smiles", "heavy_atoms"], filter=wanted)
print(f"{small.num_rows:,} rows, columns {small.column_names}")
print(small.slice(0, 3).to_pandas().to_string(index=False))
vendor_b = next(f for f in library.get_fragments() if "Vendor%20B" in f.path)
groups = vendor_b.metadata
for i in range(groups.num_row_groups):
    stats = groups.row_group(i).column(0).statistics
    print(f"row group {i}: id {stats.min} to {stats.max}")
one_range = (pc.field("id") >= "ML-00100000") & (pc.field("id") < "ML-00110000")
kept = vendor_b.split_by_row_group(filter=one_range, schema=library.schema)
print(f"row groups that could match: {len(kept)} of {groups.num_row_groups}")

# ---- 6. Querying the dataset with DuckDB ----
con = duckdb.connect()
LIBRARY = f"read_parquet('{DATASET.as_posix()}/**/*.parquet', hive_partitioning = true)"
summary = con.sql(f"""
    SELECT vendor,
           count(*) AS molecules,
           round(avg(price_usd), 2) AS mean_price_usd,
           min(heavy_atoms) AS min_heavy_atoms,
           max(heavy_atoms) AS max_heavy_atoms
    FROM {LIBRARY}
    GROUP BY vendor
    ORDER BY vendor
""").df()
print(summary.to_string(index=False))
cheapest = con.sql(f"""
    SELECT id, vendor, price_usd, heavy_atoms, smiles
    FROM {LIBRARY}
    WHERE heavy_atoms BETWEEN 25 AND 30 AND halogens = 0
    ORDER BY price_usd, id
    LIMIT 5
""").df()
print(cheapest.to_string(index=False))
plan = con.sql(f"""
    EXPLAIN SELECT count(*) FROM {LIBRARY}
    WHERE vendor = 'Vendor B' AND heavy_atoms BETWEEN 25 AND 30
""").fetchall()[0][1]
for line in plan.splitlines():
    text = line.strip("│╭╮╰╯─┬┴ ")  # drop the boxes DuckDB draws, keep their contents
    if text:
        print(text)

# ---- Why this scales ----
con.sql(f"SET memory_limit = '{DUCKDB_MEMORY}'")
capped = con.sql(f"SELECT count(*) FROM {LIBRARY} WHERE heavy_atoms BETWEEN 25 AND 30").fetchall()[0]
print(f"{capped[0]:,} molecules with 25 to 30 heavy atoms, counted within a {DUCKDB_MEMORY} limit")
con.close()
