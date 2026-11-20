# Homework: Incremental ingestion from ChEMBL and PubChem

Answer each question by running code like the code in the lesson. Submit your answers through the
cohort's form; the answers are published after the deadline.

1. With `LIVE = True` (this question needs the internet), load the activities into a fresh DuckDB
   database with the first run cut off at activity id 16,354,699 instead of the lesson's cut-off.
   How many records does each of the three runs fetch, and in how many pages? Run it again: how
   many requests reach ChEMBL the second time, and why?
2. Which molecule has the highest pChEMBL value for IKK-epsilon in your database, how many IC50
   values does it have, and from how many documents? Write the query in SQL against DuckDB.
3. Load the same pages a second time in a different order (last page first). Show with a query that
   the table is identical to a load in the normal order. What property of the load makes this so,
   and what would break it?
4. Add a `standard_relation` check to the `Activity` model: only `=`, `<`, `>`, `<=` and `>=` are
   allowed. Show a record with `"~"` being rejected. Then explain why a pChEMBL value is only
   meaningful for records whose relation is `=`.
5. Using the `RateLimiter` and `PretendClock` from the lesson, how long do 50 PubChem requests take
   at the policy's limit? Write a second limiter that also allows at most 400 requests per minute
   (keep both limits), and report how long 1,000 requests take with it.
6. **To think about.** Your company wants a nightly table of every ChEMBL IC50 value for 200
   kinases, kept up to date. Between ChEMBL releases nothing changes; at a release, records are
   added, some are corrected and a few are removed. Design the loading: what you use for the first
   load and for later ones, what your load-state table records (think about the release number and
   the retrieval date), how you notice corrections and removals, and how the licence and attribution
   reach the people who use the table.
