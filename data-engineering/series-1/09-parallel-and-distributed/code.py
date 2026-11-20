"""Parallel and distributed processing: the code of the lesson, in order.

Spread standardisation and fingerprints across cores with joblib and across memory and machines with Dask, measure the speed-up, and know when parallel work stops helping.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/09-parallel-and-distributed/
Run it from anywhere, e.g. from the series folder: uv run python 09-parallel-and-distributed/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]

# ---- The worker function ----
import sys
from pathlib import Path

import chemlib

# Worker processes must import the functions they run by name, so those functions live in a file
# of their own, workers.py, in this folder. Putting the folder first on the import path lets this
# process, and the worker processes it starts (they copy the path), import it.
sys.path.insert(0, str(Path().resolve()))
import workers  # noqa: E402  (after the path is set)

Path("work").mkdir(exist_ok=True)
library = chemlib.library(12_000, seed=9)
smiles = list(library["smiles"])
print(len(smiles), "molecules; the first:", smiles[0])
print(workers.describe(smiles[:2]))

# ---- The serial run ----
import time

start = time.perf_counter()
serial = workers.describe(smiles)
serial_seconds = time.perf_counter() - start
per_molecule = serial_seconds / len(smiles)
print(f"{len(smiles):,} molecules in {serial_seconds:.1f} s, {per_molecule * 1e6:.0f} µs each")
print(f"all {chemlib.size():,} would take about {chemlib.size() * per_molecule / 60:.0f} minutes")

# ---- Chunks and workers ----
from joblib import Parallel, delayed


def chunked(items: list, size: int) -> list[list]:
    """Split a list into consecutive chunks of at most `size` items."""
    return [items[i : i + size] for i in range(0, len(items), size)]


chunks = chunked(smiles, 1_500)
parts = Parallel(n_jobs=4)(delayed(workers.describe)(chunk) for chunk in chunks)
in_parallel = [row for part in parts for row in part]
print(len(chunks), "chunks of", len(chunks[0]), "->", len(in_parallel), "rows")
print("identical to the serial run:", in_parallel == serial)

# ---- The speed-up ----
speed_up = {1: 1.0}
for n_jobs in [2, 4]:
    Parallel(n_jobs=n_jobs)(delayed(workers.describe)(c) for c in chunked(smiles[:40], 10))
    start = time.perf_counter()
    Parallel(n_jobs=n_jobs)(delayed(workers.describe)(chunk) for chunk in chunks)
    seconds = time.perf_counter() - start
    speed_up[n_jobs] = serial_seconds / seconds
    print(f"n_jobs={n_jobs}: {seconds:.1f} s, {speed_up[n_jobs]:.1f} times the serial speed")

# ---- 3. What to send: SMILES, not molecules ----
import pickle

from rdkit import Chem

chunk = chunks[0]
as_text = pickle.dumps(chunk)
as_molecules = pickle.dumps([Chem.MolFromSmiles(s) for s in chunk])
print(f"{len(chunk):,} SMILES:   {len(as_text) / 1e3:6.0f} kB")
print(f"{len(chunk):,} molecules: {len(as_molecules) / 1e3:6.0f} kB, "
      f"{len(as_molecules) / len(as_text):.0f} times as much")

# ---- 4. Choosing a chunk size ----
for size in [5, 1_500, 6_000]:
    pieces = chunked(smiles, size)
    start = time.perf_counter()
    Parallel(n_jobs=4, batch_size=1)(delayed(workers.describe)(piece) for piece in pieces)
    print(f"chunks of {size:>5,}: {len(pieces):>5,} tasks, {time.perf_counter() - start:.1f} s")

# ---- Amdahl's law ----
def amdahl(p: float, n: int) -> float:
    """The best speed-up with n workers when a fraction p of the work runs in parallel."""
    return 1 / ((1 - p) + p / n)


counts = [2, 4, 8, 16, 64]
print("best speed-up with this many workers:")
print(f"{'parallel fraction':>17}" + "".join(f"{n:>7}" for n in counts) + f"{'limit':>8}")
for p in [0.5, 0.9, 0.99]:
    row = "".join(f"{amdahl(p, n):7.1f}" for n in counts)
    print(f"{p:>17}{row}{1 / (1 - p):8.0f}")

# ---- Work that mostly waits: threads ----
ids = list(library["id"][:40])
start = time.perf_counter()
one_by_one = [workers.look_up(i) for i in ids]
waited = time.perf_counter() - start
start = time.perf_counter()
threaded = Parallel(n_jobs=8, prefer="threads")(delayed(workers.look_up)(i) for i in ids)
print(f"40 look-ups one by one: {waited:.1f} s; with 8 threads: {time.perf_counter() - start:.1f} s")
print("same results:", threaded == one_by_one)

# ---- A Parquet folder to work on ----
import shutil

folder = Path("work/molecules")
shutil.rmtree(folder, ignore_errors=True)
folder.mkdir(parents=True)
for k, batch in enumerate(chemlib.stream(24_000, batch=4_000, start=1_200_000)):
    batch.to_parquet(folder / f"part-{k:02d}.parquet", index=False)
print(sorted(p.name for p in folder.iterdir()))

# ---- Lazy partitions and a task graph ----
import dask.dataframe as dd
import pandas as pd

molecules = dd.read_parquet(folder)
meta = pd.DataFrame({"id": [], "vendor": [], **{c: [] for c in workers.COLUMNS}})
meta = meta.astype({"id": "string", "vendor": "string", **workers.COLUMNS})
described = molecules.map_partitions(workers.describe_frame, meta=meta)
print(type(described).__name__, "with", described.npartitions, "partitions")
print(dict(described.dtypes.astype(str)))

# ---- A local cluster, and computing the result ----
from dask.distributed import Client, LocalCluster

cluster = LocalCluster(n_workers=1, threads_per_worker=4, processes=False)
client = Client(cluster)
shutil.rmtree("work/described", ignore_errors=True)  # old files would be read back with the new
described.to_parquet("work/described", write_index=False)

result = dd.read_parquet("work/described")
summary = result.groupby("vendor").agg({"id": "count", "mw": "mean", "bits_on": "mean"})
print(summary.compute().round(2).sort_index().to_string())
client.close()
cluster.close()
first_file = pd.read_parquet(folder / "part-00.parquet")
direct = workers.describe(list(first_file["smiles"]))
from_dask = pd.read_parquet("work/described").set_index("id").loc[first_file["id"]]
rows = list(from_dask[list(workers.COLUMNS)].itertuples(index=False, name=None))
print(len(rows), "rows; Dask matches a direct call:", rows == direct)
