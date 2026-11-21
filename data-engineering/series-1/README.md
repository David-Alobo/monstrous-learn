# Series 1: Data Engineering for Cheminformatics

Track: Data Engineering for Chemistry. From SDF files to chemical data pipelines that scale to millions of molecules, survive failures and can be trusted.

**Status:** opens January 2027 · **Level:** For chemists who know some Python

Fifteen modules on the engineering that sits between raw chemical files and machine learning. It starts with how molecules are represented and stored, in relational and graph databases; then the course turns to what breaks in practice: libraries too big for memory, jobs that need many cores, pipelines that fail halfway, data that drifts, and results nobody can reproduce. Each idea is built by hand first, so you understand it before Series 2 hands it to industry tools.

## Modules

### Foundations

1. **Molecules as graphs and matrices.** A molecule is a graph: atoms are nodes, bonds are edges. Build it in NetworkX, write it as adjacency, bond-order and distance matrices, encode atom and bond properties (weights, one-hot features, bond tensors, edge lists), and compute on it with NumPy, up to one step of message passing. (RDKit, NetworkX, NumPy, pandas)
2. **Molecules as text, patterns and numbers.** SMILES (canonical and isomeric), InChI and InChIKey, molfiles and SDF, 3D conformers, SMARTS patterns, fingerprints and descriptors: what each keeps, what each loses (stereochemistry, tautomers, aromaticity), and which to store for which job. (RDKit, pandas)
3. **Chemical files and identity.** The files molecules travel in (SDF, SMILES, CSV, Parquet), what each costs in space and time, and a stable identity for every molecule (InChIKey) so duplicates can be found. (RDKit, PyArrow, Parquet)
4. **Databases, schemas and a chemical database.** Know the kinds of database and which questions each answers best: relational (SQL) and analytical columnar stores, and the NoSQL families: document (MongoDB), key-value (Redis), wide-column (Cassandra), graph (Neo4j) and vector databases, with what each gives up (joins, transactions, a fixed schema) for scale or flexibility. Model chemical data before storing it: a conceptual model (compounds, structures, batches, assays, measurements, targets and how they relate), drawn as an entity-relationship diagram, turned into a logical and then a physical schema with keys, constraints, units and indexes. Compare a normalised model for recording data with a dimensional (star) model for analysing it. Describe it with metadata (a data dictionary, column comments, provenance columns) and see where a data contract fits. Then load a library into PostgreSQL with the RDKit cartridge, search by substructure and similarity, read query plans, and use DuckDB for fast analysis. (PostgreSQL, RDKit cartridge, DuckDB, SQL)
5. **Molecules as graphs, and graph databases.** A molecule is a graph: atoms are nodes, bonds are edges. Work with it as one (rings, paths, substructure as subgraph matching, maximum common substructure), then store chemistry in a graph database: molecules linked to reactions, targets and assays, queried with Cypher. Compare it with the relational database and see where each one wins. (RDKit, NetworkX, Neo4j, Cypher)
6. **Validating molecules.** Catch broken structures before they spread: parsing and sanitisation errors, impossible valences, unexpected elements and charges, missing or contradictory stereochemistry, size limits; decide what to fix, what to reject and how to record why. (RDKit)
7. **Standardisation as a tested transformation.** Strip salts, neutralise charges and choose one tautomer as a pure, deterministic function with versioned rules and unit tests. (RDKit MolStandardize, pytest)

### Scale

8. **Libraries larger than memory.** Stream molecules in batches instead of loading them all, write partitioned Parquet, and query far more rows than fit in memory; measure memory and throughput as you go. (PyArrow, Parquet, DuckDB)
9. **Parallel and distributed processing.** Spread standardisation and fingerprints across cores with joblib, then across memory and machines with Dask: chunk sizes, passing SMILES instead of molecule objects, when parallel work stops helping, and a scaling curve; the same code on Windows, macOS and Linux. (joblib, Dask)

### Reliability

10. **Pipelines that survive failure.** Idempotent steps, checkpoints and cached results, resuming from the last good batch, retries with back-off, atomic writes, quarantining bad molecules instead of crashing, settings checked before a run starts, and running long jobs on a server or virtual machine with tmux. (Python, joblib.Memory, Pydantic settings, PostgreSQL, tmux)
11. **Incremental ingestion from ChEMBL and PubChem.** Fetch only what changed, page through APIs within their rate limits, cache responses, check every response against a model so a changed API fails loudly, and run backfills safely. (ChEMBL and PubChem APIs, Pydantic, Parquet)
12. **Validating data: records with Pydantic, tables with Pandera.** Check single records at the edges with Pydantic and whole batches in bulk with Pandera: column types, required fields, value ranges, units (nM, µM, pIC50), duplicates, links between tables, and counts that agree across sources; measure why a million rows are not checked one at a time; stop or quarantine a batch that fails, and report why. (Pydantic, Pandera, RDKit, PostgreSQL)
13. **Versioning everything.** Version code, environments, database schemas, standardisation rules, datasets and results, so any number can be traced back and rebuilt exactly. (Git, uv, Docker, SQL migrations, DVC)
14. **Monitoring pipelines.** Structured logs, run history, counts in and out that must reconcile, throughput and error rates, freshness, drift in molecular properties, and alerts when something goes wrong. (Python logging, PostgreSQL, alerts)

### Capstone

15. **Capstone: a resumable, monitored pipeline over a large library.** Standardise, deduplicate, filter and fingerprint millions of molecules end to end; stop it halfway, resume it, version the output and show that every count reconciles. (Everything above)

Each module will have its own folder here (`01-…`, `02-…`) with its code, tests, lesson
and notebook. This file is written from `shared/site/catalogue.json` by
`python -m shared.site.build`; the course page is
https://monstrous.com.ng/learn/data-engineering/series-1/.
