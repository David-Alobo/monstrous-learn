# Homework: Databases, schemas and a chemical database

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so its tables
exist. The lesson closes its DuckDB database at the end of section 6: open it again with
`db = duckdb.connect(DUCKDB_FILE)`. If you are in a cohort, you will be told where to send your
answers; everyone can check theirs against the answers published after the cohort's deadline.

1. **Spot the repeated facts** (section 2). In the spreadsheet `sheet`, how many distinct values do
   the columns `smiles`, `supplier`, `target` and `organism` hold, against 4,000 rows? Which column
   is repeated the most times per distinct value? In one sentence, what could go wrong if someone
   edits that column by hand?
2. **Add a table** (sections 2 and 3). Each measurement comes from an assay run by a lab. Add a
   `lab` table (a `lab_id` primary key, a required `name`, and a `country`) and a `lab_id` column to
   a new copy of `measurement` (call it `measurement_v2`) that must point to a real lab. Create
   both in DuckDB, add two labs, copy the measurements in with every row given lab 1, and show the
   database refusing a measurement that names lab 3, which does not exist. Then add the new table
   to the ER diagram as a sketch on paper: which side of the line is "one" and which "many"?
3. **Ask the database** (section 4). Write one SQL query that lists, for each supplier, how many
   *different* compounds it sells (`count(DISTINCT compound_id)`), the cheapest and the dearest
   batch, ordered by supplier name. Then write a second query: the ten compounds measured most often
   (on any target), with their InChIKey and the number of measurements.
4. **Describe it** (section 5). The data dictionary shows `None` for several columns. Write
   `COMMENT ON COLUMN` statements for every column of `compound` and `measurement` that has none,
   in plain words with units where there are units, and print the dictionary again. What would you
   add for a colleague who has never seen this database?
5. **Search inside PostgreSQL** (section 7; needs PostgreSQL running, see the database guide). Write
   SMARTS for an aromatic ring carrying fluorine (`c[F]`) and for a primary amide (`[NX3H2][CX3]=O`,
   a C=O on a nitrogen with two hydrogens). How many library compounds contain each? Check each
   pattern first on two molecules you know, one that should match and one that should not, as the
   lesson did for acids.
6. **To think about** (sections 1 and 8). Your group wants to (a) keep every compound and assay
   result, changed by ten chemists; (b) let a dashboard show each week's results; (c) keep raw
   instrument files with metadata that differs by instrument; (d) find compounds whose learned
   embedding is near a new hit. Which kind of database would you use for each, and what rights
   would each program or person get?
