# Series 1: Data Engineering for Cheminformatics

From SDF files to chemical data pipelines that scale to millions of molecules, survive failures and can be trusted.

**Status:** opens January 2027 · **Level:** For chemists who know some Python

Thirteen modules on the engineering that sits between raw chemical files and machine learning. It starts with how molecules are represented and stored in a real database; then the course turns to what breaks in practice: libraries too big for memory, jobs that need many cores, pipelines that fail halfway, data that drifts, and results nobody can reproduce. Each idea is built by hand first, so you understand it before Series 2 hands it to industry tools.

## Modules

### Foundations

1. **Representing molecules.** How a computer holds a molecule: SMILES (canonical and isomeric), InChI and InChIKey, connection tables in molfiles and SDF, molecular graphs, 3D conformers, SMARTS patterns, fingerprints and descriptors; what each keeps, what each loses (stereochemistry, tautomers, aromaticity), and which to store for which job. (RDKit)
2. **Chemical files and identity.** The files molecules travel in (SDF, SMILES, CSV, Parquet), what each costs in space and time, and a stable identity for every molecule (InChIKey) so duplicates can be found. (RDKit, PyArrow, Parquet)
3. **A chemical database.** Load a library into PostgreSQL with the RDKit cartridge, index it, search by substructure and similarity, read query plans, and use DuckDB for fast analysis. (PostgreSQL, RDKit cartridge, DuckDB)
4. **Validating molecules.** Catch broken structures before they spread: parsing and sanitisation errors, impossible valences, unexpected elements and charges, missing or contradictory stereochemistry, size limits; decide what to fix, what to reject and how to record why. (RDKit)
5. **Standardisation as a tested transformation.** Strip salts, neutralise charges and choose one tautomer as a pure, deterministic function with versioned rules and unit tests. (RDKit MolStandardize, pytest)

### Scale

6. **Libraries larger than memory.** Stream molecules in batches instead of loading them all, write partitioned Parquet, and query far more rows than fit in memory; measure memory and throughput as you go. (PyArrow, Parquet, DuckDB)
7. **Parallel and distributed processing.** Spread standardisation and fingerprints across cores with joblib, then across memory and machines with Dask: chunk sizes, passing SMILES instead of molecule objects, when parallel work stops helping, and a scaling curve; the same code on Windows, macOS and Linux. (joblib, Dask)

### Reliability

8. **Pipelines that survive failure.** Idempotent steps, checkpoints and cached results, resuming from the last good batch, retries with back-off, atomic writes, and quarantining bad molecules instead of crashing. (Python, joblib.Memory, PostgreSQL)
9. **Incremental ingestion from ChEMBL and PubChem.** Fetch only what changed, page through APIs within their rate limits, cache responses, and run backfills safely. (ChEMBL and PubChem APIs, Parquet)
10. **Validating data: contracts and quality checks.** Check every batch against a written contract: column types, required fields, value ranges, units (nM, µM, pIC50), duplicates, links between tables, and counts that agree across sources; stop or quarantine a batch that fails, and report why. (Pandera, RDKit, PostgreSQL)
11. **Versioning everything.** Version code, environments, database schemas, standardisation rules, datasets and results, so any number can be traced back and rebuilt exactly. (Git, uv, Docker, SQL migrations, DVC)
12. **Monitoring pipelines.** Structured logs, run history, counts in and out that must reconcile, throughput and error rates, freshness, drift in molecular properties, and alerts when something goes wrong. (Python logging, PostgreSQL, alerts)

### Capstone

13. **Capstone: a resumable, monitored pipeline over a large library.** Standardise, deduplicate, filter and fingerprint millions of molecules end to end; stop it halfway, resume it, version the output and show that every count reconciles. (Everything above)

Each module will have its own folder here (`01-…`, `02-…`) with its code, tests, lesson
and notebook. This file is written from `shared/site/catalogue.json` by
`python -m shared.site.build`; the course page is
https://monstrous.com.ng/learn/series-1/.
