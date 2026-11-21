"""Capstone: a resumable, monitored pipeline over a large library: the code of the lesson, in order.

Ingest, validate, standardise, deduplicate, filter and fingerprint a compound library end to end, stop it halfway, resume it, and show that the output is versioned and every count reconciles.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/15-capstone/
Run it from anywhere, e.g. from the series folder: uv run python 15-capstone/code.py
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
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from pydantic import ValidationError

sys.path.insert(0, ".")  # this module's folder, where pipeline.py lives, so Python can find it
import pipeline  # noqa: E402  (after the path is set)

# log lines: level and message only, so the lesson's outputs are the same on every run
# (a real job would add "%(asctime)s" to the format)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)

# where the lesson's runs write: data, run record (DuckDB), log and manifest
WORK = Path("work")
OUT_DIR = WORK / "capstone"  # the run that crashes and resumes
OUT_DIR_AGAIN = WORK / "capstone-again"  # the uninterrupted run of Section 9
DATABASE = OUT_DIR / "pipeline.duckdb"
MANIFEST = OUT_DIR / "manifest.json"

RETRY_WAIT_S = 0.01  # seconds before the first retry; short, so the lesson runs quickly
START = datetime(2027, 1, 18, 2, 0)  # the injected clock starts at 02:00 UTC
FLAKY_READS = {3: 2}  # injected fault: batch 3's first two reads fail
CRASH_IN_BATCH = 12  # injected fault: the process "dies" in batch 12, before its checkpoint
MOVED_BATCH = 7  # the batch whose compounds file is moved away in Section 7

WORK.mkdir(exist_ok=True)
for old in (OUT_DIR, OUT_DIR_AGAIN):  # start the lesson from nothing
    shutil.rmtree(old, ignore_errors=True)
print(f"molecules the library generator can make: {pipeline.chemlib.size():,}")

# ---- 2. Settings ----
settings = pipeline.Settings(out_dir=OUT_DIR, retry_wait_s=RETRY_WAIT_S)
for name, value in settings.model_dump(exclude={"out_dir"}).items():
    print(f"{name:14} {value}")
try:
    pipeline.Settings(batch_size=0, defect_rate=2, n_molecules=5_000_000)
except ValidationError as err:
    for problem in err.errors():
        print(f"{problem['loc'][0]}: {problem['msg']}")

# ---- 3. Ingest, with retries ----
batch = pipeline.read_batch(settings, 0)
print(len(batch), "records in batch 0")
print(batch["defect"].replace("", "(clean)").value_counts().to_string())
print("the same rows when read again:", batch.equals(pipeline.read_batch(settings, 0)))
class Tick:
    """A clock for repeatable run records: each reading is one second after the last."""

    def __init__(self, start):
        self.time = start

    def __call__(self):
        """The next time."""
        self.time += timedelta(seconds=1)
        return self.time


screen = logging.StreamHandler()
screen.setFormatter(pipeline.JsonFormatter(Tick(START)))
pipeline.log.addHandler(screen)  # run() replaces it with the run's log file
pipeline.log.propagate = False
flaky = pipeline.Faults(flaky_reads=FLAKY_READS)
batch, attempts = pipeline.read_with_retries(settings, 3, flaky)
print("batch 3 read after", attempts, "attempts:", len(batch), "records")

# ---- 4. Validate and standardise ----
examples = pd.DataFrame(
    {
        "id": [f"EX-{k}" for k in range(1, 9)],
        "smiles": [
            "CC(=O)Oc1ccccc1C(=O)[O-].[Na+]",  # aspirin, as its sodium salt
            "CC(=O)Oc1ccccc1C(=O)O",  # aspirin
            "c1ccccc1C(=O)NCc1ccc(cc1",  # a ring that never closes
            "C(C)(C)(C)(C)c1ccccc1",  # a carbon with five bonds
            "C[Se]c1ccc(cc1)C(=O)N",  # selenium
            "S=C1SC(=Cc2ccccc2)C(=O)N1",  # a benzylidene rhodanine
            "CCCCCCCCCCCCCCCCCCCC(=O)NCc1ccccc1",  # a long fatty amide
            "O=C(NCc1ccccc1)c1ccc(F)cc1",  # an ordinary benzamide
        ],
        "defect": "",
    }
)
rows, quarantined = pipeline.process_batch(examples)
print(quarantined[["id", "stage", "reason"]].to_string(index=False))
print()
print(rows[["id", "smiles", "mw", "logp", "pains"]].to_string(index=False))
for key, value in pipeline.RULES.items():
    print(f"{key:17} {value}")
print("rules hash:", pipeline.rules_hash())

# ---- 5. Deduplicate, filter, describe ----
unique, duplicates = pipeline.deduplicate(rows, seen={})
print(duplicates[["id", "reason", "detail"]].to_string(index=False))
kept, filtered = pipeline.apply_filters(unique, settings)
print(filtered[["id", "reason", "detail"]].to_string(index=False))
print("kept:", kept["id"].tolist())
fingerprint = kept["morgan2"].iloc[0]
bits = np.unpackbits(np.frombuffer(fingerprint, dtype=np.uint8))
print(f"{len(fingerprint)} bytes, {len(bits)} bits, {bits.sum()} set")
print(kept[["id", "mw", "logp", "tpsa", "hbd", "hba", "heavy_atoms"]].to_string(index=False))

# ---- 6. A crash halfway, and a resume ----
clock = Tick(START)
faults = pipeline.Faults(flaky_reads=FLAKY_READS, crash_in_batch=CRASH_IN_BATCH)
started = time.perf_counter()
try:
    pipeline.run(settings, clock, faults)
except pipeline.SimulatedCrash as crash:
    log.error("crashed: %s", crash)
seconds = {"crashed run": time.perf_counter() - started}

with duckdb.connect(str(DATABASE), read_only=True) as db:
    print(db.sql("SELECT run_id, status FROM runs").df().to_string(index=False))
    done = db.sql("SELECT count(*), max(batch) FROM batches").fetchall()[0]
print(f"checkpointed: {done[0]} batches (0 to {done[1]}) of {pipeline.n_batches(settings)}")
print(f"batch {CRASH_IN_BATCH}'s files are on disk:",
      pipeline.partition(settings, "compounds", CRASH_IN_BATCH).exists())
started = time.perf_counter()
manifest = pipeline.run(settings, clock)
seconds["resumed run"] = time.perf_counter() - started

with duckdb.connect(str(DATABASE), read_only=True) as db:
    print(db.sql("SELECT run_id, status, batches FROM runs ORDER BY run_id").df()
          .to_string(index=False))
    print(db.sql("SELECT run_id, count(*) AS batches, min(batch) AS first, max(batch) AS last, "
                 "sum(attempts)::INTEGER AS reads FROM batches GROUP BY run_id ORDER BY run_id").df()
          .to_string(index=False))

# ---- 7. Counts that reconcile ----
counts = manifest["counts"]
for stage, count in counts.items():
    print(f"{stage:24} {count:>7,}")
accounted = sum(count for stage, count in counts.items() if stage not in ("batches", "rows_in"))
print("in = quarantined + duplicates + filtered + out:", counts["rows_in"] == accounted)
moved = pipeline.partition(settings, "compounds", MOVED_BATCH)
moved.rename(moved.with_suffix(".bak"))
with duckdb.connect(str(DATABASE)) as db:
    try:
        pipeline.reconcile(db, settings)
    except pipeline.ReconciliationError as err:
        print("ReconciliationError:", err)
moved.with_suffix(".bak").rename(moved)
with duckdb.connect(str(DATABASE), read_only=True) as db:
    truth = db.sql("""
        SELECT defect, 'quarantine: ' || reason AS outcome, count(*) AS records
        FROM quarantine GROUP BY ALL
        UNION ALL
        SELECT defect, 'removed: ' || reason, count(*) FROM removed
        WHERE defect <> '' GROUP BY ALL
        UNION ALL
        SELECT defect, 'kept', count(*) FROM compounds WHERE defect <> '' GROUP BY ALL
        ORDER BY defect, outcome
    """).df()
print(truth.to_string(index=False))

# ---- 8. The provenance manifest ----
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
print("runs:", manifest["runs"])
print("input:", manifest["input"]["source"], manifest["input"]["n_molecules"], "molecules, seed",
      manifest["input"]["seed"], "defect rate", manifest["input"]["defect_rate"])
print("rules hash:", manifest["rules_hash"])
print("versions recorded:", ", ".join(manifest["versions"]))
print("output files:", len(manifest["outputs"]))
print("data sha256:", manifest["data_sha256"][:16], "...")

# ---- 9. The same answer without the crash ----
again_settings = settings.model_copy(update={"out_dir": OUT_DIR_AGAIN})
started = time.perf_counter()
again = pipeline.run(again_settings, Tick(START))
seconds["uninterrupted run"] = time.perf_counter() - started
print("same counts:", again["counts"] == manifest["counts"])
print("same files, byte for byte:", again["outputs"] == manifest["outputs"])
print("same data hash:", again["data_sha256"] == manifest["data_sha256"])
for name, value in seconds.items():
    print(f"{name:18} {value:5.1f} s")
rate = counts["rows_in"] / seconds["uninterrupted run"]
print(f"about {rate:,.0f} records per second with {settings.workers} workers")
print(f"the whole library at that rate: about {pipeline.chemlib.size() / rate / 3600:.1f} hours")

# ---- 10. Querying the result ----
with duckdb.connect(str(DATABASE), read_only=True) as db:
    print(db.sql("""
        SELECT reason, count(*) AS records FROM removed
        WHERE reason <> 'PAINS' GROUP BY reason
        UNION ALL
        SELECT 'PAINS: ' || regexp_replace(detail, '\\(\\d+\\)$', ''), count(*) FROM removed
        WHERE reason = 'PAINS' GROUP BY ALL
        ORDER BY records DESC
    """).df().to_string(index=False))
    print()
    print(db.sql("""
        SELECT count(*) AS compounds, round(median(mw), 1) AS median_mw,
               round(median(logp), 2) AS median_logp, round(median(tpsa), 1) AS median_tpsa,
               count(DISTINCT rules_hash) AS rule_sets
        FROM compounds
    """).df().to_string(index=False))
