# Homework: Pipelines that survive failure

Answer each question by running code like the code in the lesson. Submit your answers through the
cohort's form; the answers are published after the deadline.

1. Build a library with `add_defects(library(8_000, seed=21), rate=0.05, seed=22)`, sorted by `id`,
   and run `prepare_batch` over all of it. How many records are quarantined, and how many for each
   reason? Which reason does chemlib's `salt` fault end up under, and why?
2. Start `RunSettings` with `CHEMRUN_MAX_ATTEMPTS=0` and `CHEMRUN_FIRST_DELAY_S=60` set in the
   environment (and nothing else changed). Which problems are reported? Then add a check that
   `batch_size` is no larger than `n_molecules`, and show it refusing a bad pair of values.
3. Run the library from question 1 through `run_pipeline` with batches of 500, crashing at batch 9.
   How many rows are in `molecules`, `quarantine` and `checkpoints` after the crash? Resume it: which
   batches does the second call run? Show with `pd.testing.assert_frame_equal` that the result equals
   an uninterrupted run.
4. Replace the upsert in `save_batch` with a plain `INSERT` (no `ON CONFLICT`) and repeat question 3.
   What happens when the resumed run reaches the batch that crashed, and why is this failure better
   than the one in the lesson's pandas `to_sql` example?
5. Use `with_retries` with `FlakyService(failures=4)`, `max_attempts=5` and `random.Random(7)`.
   How long does it wait in all? Run it 1,000 times with seeds 0 to 999 and report the mean and the
   largest total wait. What would the total be without jitter?
6. **To think about.** Your pipeline writes each batch's results as a Parquet file
   (`batch-0007.parquet`) to a shared folder, and a second team's pipeline picks up every new file in
   that folder. Design how the files are written and how the checkpoint is recorded so that the
   second team never reads a half-written file and never processes a batch twice, even when your
   run crashes and is resumed. Which of the ideas in this module do you need, and what is left that
   the second team has to do on their side?
