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

# ---- Setup ----
import logging
import pickle
import shutil
import sys
import time
from pathlib import Path

import dask.dataframe as dd
import pandas as pd
from dask.distributed import Client, LocalCluster
from joblib import Parallel, delayed
from rdkit import Chem

import chemlib

# Worker processes must import the functions they run by name, so those functions live in a file
# of their own, workers.py, in this folder. Putting the folder first on the import path lets this
# process, and the worker processes it starts (they copy the path), import it.
sys.path.insert(0, str(Path().resolve()))
import workers  # noqa: E402  (after the path is set)

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

WORK = Path("work")  # where the lesson writes its files (git-ignored)
N_MOLECULES = 12_000  # molecules described with joblib; any number up to chemlib.size()
SEED = 9  # which molecules; change it for a different sample
CHUNK = 1_500  # molecules per chunk sent to a worker
N_JOBS = 4  # worker processes; at most the number of cores your computer has
WORKER_COUNTS = [2, 4]  # the numbers of workers timed in section 2
WARM_UP_SMILES, WARM_UP_CHUNK = 40, 10  # a small first call that starts the workers
CHUNK_SIZES = [5, CHUNK, 6_000]  # the chunk sizes timed in section 4
N_LOOK_UPS = 40  # stand-in web requests in section 5
N_THREADS = 8  # threads for work that mostly waits
DASK_MOLECULES = 24_000  # molecules in the Parquet folder Dask works on
DASK_PARTITION = 4_000  # molecules per Parquet file (one Dask partition each)
DASK_START = 1_200_000  # the number of the first of those molecules
DASK_THREADS = 4  # threads in the local Dask cluster
MOLECULES = WORK / "molecules"  # Dask's input folder
DESCRIBED = WORK / "described"  # ... and its output folder

WORK.mkdir(exist_ok=True)

# ---- The worker function ----
library = chemlib.library(N_MOLECULES, seed=SEED)
smiles = list(library["smiles"])
print(len(smiles), "molecules; the first:", smiles[0])
for row in workers.describe(smiles[:2]):
    print(row)

# ---- The serial run ----
start = time.perf_counter()
serial = workers.describe(smiles)
serial_seconds = time.perf_counter() - start
per_molecule = serial_seconds / len(smiles)
log.info("%s molecules in %.1f s, %.0f µs each", f"{len(smiles):,}", serial_seconds,
         per_molecule * 1e6)
log.info("all %s would take about %.0f minutes", f"{chemlib.size():,}",
         chemlib.size() * per_molecule / 60)

# ---- Chunks and workers ----
def chunked(items: list, size: int) -> list[list]:
    """Split a list into consecutive chunks of at most `size` items."""
    return [items[i : i + size] for i in range(0, len(items), size)]


chunks = chunked(smiles, CHUNK)
parts = Parallel(n_jobs=N_JOBS)(delayed(workers.describe)(chunk) for chunk in chunks)
in_parallel = [row for part in parts for row in part]
log.info("%d chunks of %d -> %d rows", len(chunks), len(chunks[0]), len(in_parallel))
print("identical to the serial run:", in_parallel == serial)

# ---- The speed-up ----
warm_up = chunked(smiles[:WARM_UP_SMILES], WARM_UP_CHUNK)
speed_up = {1: 1.0}
for n_jobs in WORKER_COUNTS:
    Parallel(n_jobs=n_jobs)(delayed(workers.describe)(c) for c in warm_up)
    start = time.perf_counter()
    Parallel(n_jobs=n_jobs)(delayed(workers.describe)(chunk) for chunk in chunks)
    seconds = time.perf_counter() - start
    speed_up[n_jobs] = serial_seconds / seconds
    log.info("n_jobs=%d: %.1f s, %.1f times the serial speed", n_jobs, seconds, speed_up[n_jobs])

# ---- 3. What to send: SMILES, not molecules ----
chunk = chunks[0]
as_text = pickle.dumps(chunk)
as_molecules = pickle.dumps([Chem.MolFromSmiles(s) for s in chunk])
print(f"{len(chunk):,} SMILES:   {len(as_text) / 1e3:6.0f} kB")
print(f"{len(chunk):,} molecules: {len(as_molecules) / 1e3:6.0f} kB, "
      f"{len(as_molecules) / len(as_text):.0f} times as much")

# ---- 4. Choosing a chunk size ----
for size in CHUNK_SIZES:
    pieces = chunked(smiles, size)
    start = time.perf_counter()
    Parallel(n_jobs=N_JOBS, batch_size=1)(delayed(workers.describe)(piece) for piece in pieces)
    log.info("chunks of %5s: %5s tasks, %.1f s", f"{size:,}", f"{len(pieces):,}",
             time.perf_counter() - start)

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
ids = list(library["id"][:N_LOOK_UPS])
start = time.perf_counter()
one_by_one = [workers.look_up(i) for i in ids]
waited = time.perf_counter() - start
start = time.perf_counter()
threaded = Parallel(n_jobs=N_THREADS, prefer="threads")(delayed(workers.look_up)(i) for i in ids)
log.info("%d look-ups one by one: %.1f s; with %d threads: %.1f s", len(ids), waited, N_THREADS,
         time.perf_counter() - start)
print("same results:", threaded == one_by_one)

# ---- A Parquet folder to work on ----
shutil.rmtree(MOLECULES, ignore_errors=True)
MOLECULES.mkdir(parents=True)
for k, batch in enumerate(chemlib.stream(DASK_MOLECULES, batch=DASK_PARTITION, start=DASK_START)):
    batch.to_parquet(MOLECULES / f"part-{k:02d}.parquet", index=False)
print(sorted(p.name for p in MOLECULES.iterdir()))

# ---- Lazy partitions and a task graph ----
molecules = dd.read_parquet(MOLECULES)
meta = pd.DataFrame({"id": [], "vendor": [], **{c: [] for c in workers.COLUMNS}})
meta = meta.astype({"id": "string", "vendor": "string", **workers.COLUMNS})
described = molecules.map_partitions(workers.describe_frame, meta=meta)
print(type(described).__name__, "with", described.npartitions, "partitions")
print(dict(described.dtypes.astype(str)))

# ---- A local cluster, and computing the result ----
cluster = LocalCluster(n_workers=1, threads_per_worker=DASK_THREADS, processes=False)
client = Client(cluster)
shutil.rmtree(DESCRIBED, ignore_errors=True)  # old files would be read back with the new
described.to_parquet(DESCRIBED, write_index=False)

result = dd.read_parquet(DESCRIBED)
summary = result.groupby("vendor").agg({"id": "count", "mw": "mean", "bits_on": "mean"})
print(summary.compute().round(2).sort_index().to_string())
client.close()
cluster.close()
first_file = pd.read_parquet(MOLECULES / "part-00.parquet")
direct = workers.describe(list(first_file["smiles"]))
from_dask = pd.read_parquet(DESCRIBED).set_index("id").loc[first_file["id"]]
rows = list(from_dask[list(workers.COLUMNS)].itertuples(index=False, name=None))
print(len(rows), "rows; Dask matches a direct call:", rows == direct)
