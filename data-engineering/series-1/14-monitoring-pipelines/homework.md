# Homework: Monitoring pipelines

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

Run the whole lesson first, from the top, so its functions and settings exist. The lesson's last
cell closes the run history, so start your first homework cell with
`db = duckdb.connect(str(HISTORY_DB))` to open it again. Every run in the run history needs its own
run id, so give each of yours a new one (for example `"hw-1"`, `"hw-2"`).

1. **Running and reconciling (Sections 3 and 4).** Make a night's file with
   `batch = chemlib.add_defects(chemlib.library(2000, seed=7), rate=0.06, seed=7)` and run it
   through the lesson's four steps with
   `run_pipeline("hw-1", batch, STEPS, np.random.default_rng(1))`. How many rows does each step
   take in and pass on (query the `steps` table, as the lesson does), and does the run reconcile
   (`reconcile("hw-1")` raises a `ReconciliationError` if it does not)?
2. **A step that loses rows (Section 4).** Write a fifth step in the same shape as `describe`: a
   function that takes a table and returns the rows it keeps, `NO_ROWS` and 0. Make it keep only the
   molecules with `mw` of 450 or less, without reporting the ones it drops. Add it after `describe`
   in a new list of steps and run question 1's batch again under a new run id. What does
   `reconcile` report? Then rewrite the step so that it returns the dropped molecules as quarantined
   rows (columns `id`, `smiles` and `reason`, with a reason such as `"MW above 450"`), and show that
   the counts now add up.
3. **Keeping secrets out of the log (Section 2).** Write a log line whose source is
   `https://api.example.org/v1/compounds?token=abc123&page=2`, for example
   `pipeline_log.warning("run started", extra={"fields": {"source": source}})`. What does the
   formatter write? (The last line of the log file is `LOG_FILE.read_text().splitlines()[-1]`.)
   Then add `secret` to the field names in the `SECRET_FIELD` pattern, next to `password`, `token`
   and `api_key`, run that line again, and test `redact` on a string of your own, such as
   `"secret=hunter2"`.
4. **Drift (Section 6).** Compute the PSI and the KS statistic for molecular weight and logP of
   `chemlib.library(1500, seed=300)` against the lesson's `reference`, with `properties`, `psi` and
   `ks` as the lesson does. Then do the same for a batch that starts at molecule number 113,400:
   `next(chemlib.stream(1500, batch=1500, start=113_400))`. For each property, which way has the
   second batch moved (compare the medians with `np.median`)? Which property would set off an alert
   first?
5. **How far to trust a threshold (Section 6).** PSI depends on how it is measured. For the first
   batch in question 4, compute the PSI for molecular weight with 5, 10, 20 and 50 bins (the `bins`
   argument of `psi`). Then compute it with 10 bins for ordinary batches of 200, 1,500 and 10,000
   molecules (`chemlib.library(n, seed=300)`). How do the values change, and what does that mean
   for a fixed threshold of 0.1?
6. **To think about (Section 7).** Your team runs ten pipelines and gets about forty alerts a week,
   most of which nobody acts on. Which alerts would you keep as pages (wake someone now), which
   would you turn into tickets (deal with in working hours) or a weekly report, and which would you
   delete? What would you measure to know the change worked?
