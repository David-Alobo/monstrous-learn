# Series 1: Data Engineering for Cheminformatics

From SDF files to chemical data pipelines that scale to millions of molecules, survive failures and can be trusted.

**Status:** opens January 2027 · **Level:** For chemists who know some Python

Eleven modules on the engineering that sits between raw chemical files and machine learning. Structures go into a real database; then the course turns to what breaks in practice: libraries too big for memory, jobs that need many cores, pipelines that fail halfway, data that drifts, and results nobody can reproduce. Each idea is built by hand first, so you understand it before Series 2 hands it to industry tools.

## Modules

### Foundations

1. **Chemical data as data.** File formats (SDF, SMILES, CSV, Parquet), what each costs in space and time, and a stable identity for every molecule (InChIKey) so duplicates can be found. (RDKit, PyArrow, Parquet)
2. **A chemical database.** Load a library into PostgreSQL with the RDKit cartridge, index it, search by substructure and similarity, read query plans, and use DuckDB for fast analysis. (PostgreSQL, RDKit cartridge, DuckDB)
3. **Standardisation as a tested transformation.** Strip salts, neutralise charges and choose one tautomer as a pure, deterministic function with versioned rules and unit tests. (RDKit MolStandardize, pytest)

### Scale

4. **Libraries larger than memory.** Stream molecules in batches instead of loading them all, write partitioned Parquet, and query far more rows than fit in memory; measure memory and throughput as you go. (PyArrow, Parquet, DuckDB)
5. **Parallel and distributed processing.** Spread standardisation and fingerprints across cores and machines: chunk sizes, passing SMILES instead of molecule objects, when parallel work stops helping, and a scaling curve. (multiprocessing, Dask)

### Reliability

6. **Pipelines that survive failure.** Idempotent steps, checkpoints, resuming from the last good batch, retries with back-off, atomic writes, and quarantining bad molecules instead of crashing. (Python, PostgreSQL)
7. **Incremental ingestion from ChEMBL and PubChem.** Fetch only what changed, page through APIs within their rate limits, cache responses, and run backfills safely. (ChEMBL and PubChem APIs, Parquet)
8. **Data contracts and quality checks.** Check every batch against a contract (valid structures, sensible properties, units) and stop or quarantine when a batch fails. (Pandera, RDKit)
9. **Versioning everything.** Version code, environments, database schemas, standardisation rules, datasets and results, so any number can be traced back and rebuilt exactly. (Git, uv, Docker, SQL migrations, DVC)
10. **Monitoring pipelines.** Structured logs, run history, counts in and out that must reconcile, throughput and error rates, freshness, drift in molecular properties, and alerts when something goes wrong. (Python logging, PostgreSQL, alerts)

### Capstone

11. **Capstone: a resumable, monitored pipeline over a large library.** Standardise, deduplicate, filter and fingerprint millions of molecules end to end; stop it halfway, resume it, version the output and show that every count reconciles. (Everything above)

Each module will have its own folder here (`01-…`, `02-…`) with its code, tests, lesson and
notebook. The outline is kept in step with `shared/site/catalogue.json`, which builds the course
page at https://monstrous.com.ng/learn/series-1/.
