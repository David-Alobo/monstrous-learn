# Series 1: Data Engineering for Cheminformatics

From SDF files and spreadsheets to a clean, searchable chemical database.

**Status:** opens January 2027 · **Level:** For chemists who know some Python

Six modules that take a compound library from loose files to a checked, queryable database: structures stored as molecules in PostgreSQL, cleaned and standardised, enriched from ChEMBL and PubChem, validated before use, and ready for machine learning.

## Modules

1. **From SDF files to a chemical database.** Load a compound library into PostgreSQL with the RDKit cartridge, store structures as molecules, and search them by substructure and similarity in SQL. (PostgreSQL, RDKit cartridge, SQL)
2. **Cleaning and standardising molecules.** Strip salts, neutralise charges and choose one tautomer, so the same compound is always stored the same way. (pandas, RDKit MolStandardize)
3. **Pulling data from ChEMBL and PubChem.** Fetch structures and bioactivity data through their web APIs, page by page and within their rate limits, and keep them as Parquet files. (Python, ChEMBL and PubChem APIs, Parquet)
4. **Checking data before it is used.** Write data contracts for chemical tables (valid structures, sensible molecular weights, consistent units) and set failing rows aside for review. (Pandera, RDKit)
5. **Fingerprints and descriptors at scale.** Compute Morgan fingerprints and descriptors for large libraries in parallel, and store them for fast similarity searches. (RDKit, multiprocessing, Dask)
6. **Capstone: a screening-library pipeline.** Take a raw vendor library through cleaning, PAINS filtering and checks into machine-learning-ready tables in PostgreSQL, end to end. (Everything above)

Each module will have its own folder here (`01-…`, `02-…`) with its code, tests, lesson and
notebook. The outline is kept in step with `shared/site/catalogue.json`, which builds the course
page at https://monstrous.com.ng/learn/series-1/.
