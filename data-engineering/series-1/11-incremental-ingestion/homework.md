# Homework: Incremental ingestion from ChEMBL and PubChem

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so the functions
it defines (`load_increment`, `fetch_json` and so on) exist. The lesson closes its database
connection at the end of section 9, so open a new one where a question needs it, for example
`con = duckdb.connect(str(DB_PATH))`. If you are in a cohort, you will be told where to send your
answers; everyone can check theirs against the answers published after the cohort's deadline.

1. *(Builds on sections 3 and 6; needs the internet.)* Set `LIVE = True`, so `fetch_json` asks
   ChEMBL itself instead of replaying the recorded answers (Colab has internet access, so this works
   there). Load the activities into a fresh DuckDB database, as section 6 does, but with the first
   run cut off at activity id 16,354,699 (`until=16354699`) instead of the lesson's
   `FIRST_RUN_CUTOFF`, then run `load_increment(con)` twice more. How many records does each of
   the three runs fetch, and in how many pages? Run all three again on a new database: how many
   requests reach ChEMBL the second time (look at `work/http-cache/`), and why?
2. *(Builds on section 6.)* Which molecule has the highest pChEMBL value for IKK-epsilon in your
   database, how many IC50 values does it have, and from how many documents (different
   `document_chembl_id` values)? Write the query in SQL against DuckDB, with `con.execute(...)`.
3. *(Builds on sections 4 and 6.)* Load the same pages a second time, into a new database, in a
   different order: last page first. (Collect the pages with `list(pages(...))`, then go through
   the list backwards with `reversed(...)`, upserting each.) Show with a query that the table is
   identical to a load in the normal order. What property of the load makes this so, and what
   would break it?
4. *(Builds on section 5.)* Add a `standard_relation` check to the `Activity` model: only `=`, `<`,
   `>`, `<=` and `>=` are allowed. (The relation says whether the reported value is exact or only a
   bound: `>` 10000 nM means "less active than we could measure".) Show a record with `"~"` being
   rejected. Then explain why a pChEMBL value is only meaningful for records whose relation is `=`.
5. *(Builds on section 2.)* Using the `RateLimiter` and `PretendClock` from the lesson, how long do
   50 PubChem requests take at the policy's limit of five per second? Write a second limiter that
   also allows at most 400 requests per minute (keep both limits), and report how long 1,000
   requests take with it.
6. **To think about.** *(Builds on sections 6, 7 and 9; no code needed.)* Your company wants a
   nightly table of every ChEMBL IC50 value for 200 kinases, kept up to date. Between ChEMBL
   releases nothing changes; at a release, records are added, some are corrected and a few are
   removed. Design the loading: what you use for the first load and for later ones, what your
   load-state table records (think about the release number and the retrieval date), how you notice
   corrections and removals, and how the licence and attribution reach the people who use the
   table.
