# Series 1: Data Engineering for Cheminformatics

Track: Data Engineering for Chemistry. From SDF files to chemical data pipelines that scale to millions of molecules, survive failures and can be trusted.

**Status:** opens January 2027 · **Level:** Beginner-friendly, every term explained · **[Read it online](https://monstrous.com.ng/learn/data-engineering/series-1/)**

Fifteen modules on the engineering that sits between raw chemical files and machine learning. It starts with how molecules are represented and stored, in relational and graph databases; then the course turns to what breaks in practice: libraries too big for memory, jobs that need many cores, pipelines that fail halfway, data that drifts, and results nobody can reproduce. Each idea is built by hand first, so you understand it before Series 2 hands it to industry tools.

## Modules

### Foundations

1. **[Molecules as graphs and matrices](01-graphs-and-matrices/)**. A molecule is a graph: atoms are nodes, bonds are edges. Build it in NetworkX, write it as adjacency, bond-order and distance matrices, encode atom and bond properties (weights, one-hot features, bond tensors, edge lists), and compute on it with NumPy, up to one step of message passing. *RDKit, NetworkX, NumPy, pandas*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/01-graphs-and-matrices/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/01-graphs-and-matrices/notebook.ipynb)

2. **[Molecules as text, patterns and numbers](02-text-patterns-and-numbers/)**. SMILES (canonical and isomeric), InChI and InChIKey, molfiles and SDF, 3D conformers, SMARTS patterns, fingerprints and descriptors: what each keeps, what each loses (stereochemistry, tautomers, aromaticity), and which to store for which job. *RDKit, pandas*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/02-text-patterns-and-numbers/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/02-text-patterns-and-numbers/notebook.ipynb)

3. **[Chemical files and identity](03-files-and-identity/)**. The files molecules travel in (SDF, SMILES, CSV, Parquet), what each costs in space and time, and a stable identity for every molecule (InChIKey) so duplicates can be found. *RDKit, PyArrow, Parquet*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/03-files-and-identity/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/03-files-and-identity/notebook.ipynb)

4. **[Databases, schemas and a chemical database](04-databases-and-schemas/)**. What a database is, the main kinds (relational, and the NoSQL kinds such as MongoDB and Neo4j), and which questions each answers best. How to plan the tables for chemical data before storing anything, and how to describe them so others can use them. Then run PostgreSQL with its RDKit chemistry add-on in Docker, log in safely, search molecules by substructure and similarity, and analyse a library quickly with DuckDB. *PostgreSQL, RDKit cartridge, DuckDB, SQL, Docker*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/04-databases-and-schemas/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/04-databases-and-schemas/notebook.ipynb)

5. **[Molecules as graphs, and graph databases](05-graphs-and-graph-databases/)**. A molecule is a graph: atoms are nodes, bonds are edges. Work with it as one (rings, paths, substructure as subgraph matching, maximum common substructure), then store chemistry in a graph database: molecules linked to reactions, targets and assays, queried with Cypher. Compare it with the relational database and see where each one wins. *RDKit, NetworkX, Neo4j, Cypher*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/05-graphs-and-graph-databases/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/05-graphs-and-graph-databases/notebook.ipynb)

6. **[Validating molecules](06-validating-molecules/)**. Catch broken structures before they spread: parsing and sanitisation errors, impossible valences, unexpected elements and charges, missing or contradictory stereochemistry, size limits; decide what to fix, what to reject and how to record why. *RDKit*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/06-validating-molecules/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/06-validating-molecules/notebook.ipynb)

7. **[Standardisation as a tested transformation](07-standardisation/)**. Strip salts, neutralise charges and choose one tautomer as a pure, deterministic function with versioned rules and unit tests. *RDKit MolStandardize, pytest*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/07-standardisation/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/07-standardisation/notebook.ipynb)


### Scale

8. **[Libraries larger than memory](08-larger-than-memory/)**. Stream molecules in batches instead of loading them all, write partitioned Parquet, and query far more rows than fit in memory; measure memory and throughput as you go. *PyArrow, Parquet, DuckDB*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/08-larger-than-memory/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/08-larger-than-memory/notebook.ipynb)

9. **[Parallel and distributed processing](09-parallel-and-distributed/)**. Spread standardisation and fingerprints across cores with joblib, then across memory and machines with Dask: chunk sizes, passing SMILES instead of molecule objects, when parallel work stops helping, and a scaling curve; the same code on Windows, macOS and Linux. *joblib, Dask*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/09-parallel-and-distributed/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/09-parallel-and-distributed/notebook.ipynb)


### Reliability

10. **[Pipelines that survive failure](10-pipelines-that-survive-failure/)**. Idempotent steps, checkpoints and cached results, resuming from the last good batch, retries with back-off, atomic writes, quarantining bad molecules instead of crashing, settings checked before a run starts, and running long jobs on a server or virtual machine with tmux. *Python, joblib.Memory, Pydantic settings, PostgreSQL, tmux*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/10-pipelines-that-survive-failure/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/10-pipelines-that-survive-failure/notebook.ipynb)

11. **[Incremental ingestion from ChEMBL and PubChem](11-incremental-ingestion/)**. Fetch only what changed, page through APIs within their rate limits, cache responses, check every response against a model so a changed API fails loudly, and run backfills safely. *ChEMBL and PubChem APIs, Pydantic, Parquet*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/11-incremental-ingestion/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/11-incremental-ingestion/notebook.ipynb)

12. **[Validating data: records with Pydantic, tables with Pandera](12-validating-data/)**. Check single records at the edges with Pydantic and whole batches in bulk with Pandera: column types, required fields, value ranges, units (nM, µM, pIC50), duplicates, links between tables, and counts that agree across sources; measure why a million rows are not checked one at a time; stop or quarantine a batch that fails, and report why. *Pydantic, Pandera, RDKit, PostgreSQL*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/12-validating-data/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/12-validating-data/notebook.ipynb)

13. **[Versioning everything](13-versioning-everything/)**. Version code, environments, database schemas, standardisation rules, datasets and results, so any number can be traced back and rebuilt exactly. *Git, uv, Docker, SQL migrations, DVC*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/13-versioning-everything/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/13-versioning-everything/notebook.ipynb)

14. **[Monitoring pipelines](14-monitoring-pipelines/)**. Structured logs, run history, counts in and out that must reconcile, throughput and error rates, freshness, drift in molecular properties, and alerts when something goes wrong. *Python logging, PostgreSQL, alerts*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/14-monitoring-pipelines/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/14-monitoring-pipelines/notebook.ipynb)


### Capstone

15. **[Capstone: a resumable, monitored pipeline over a large library](15-capstone/)**. Standardise, deduplicate, filter and fingerprint millions of molecules end to end; stop it halfway, resume it, version the output and show that every count reconciles. *Everything above*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-1/15-capstone/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/15-capstone/notebook.ipynb)


Each module folder holds the lesson (`lesson.md`), a notebook, the code on its own
and the homework. New to notebooks?
[Start here](https://monstrous.com.ng/learn/start/) shows every step.

*This file is written from `shared/site/catalogue.json` by `python -m shared.site.build`;
the course page is https://monstrous.com.ng/learn/data-engineering/series-1/.*
