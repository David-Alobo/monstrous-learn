# Homework: Pipelines that survive failure

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so the functions
it defines (`prepare_batch`, `run_pipeline` and so on) exist. If you are in a cohort, you will be
told where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

1. *(Builds on section 3.)* Build a library with
   `add_defects(library(8_000, seed=21), rate=0.05, seed=22)`, which gives 8,000 molecules with
   faults added to 5% of them, and sort it by `id` as the lesson does. Run `prepare_batch` over all
   of it. How many records are quarantined (set aside with a reason), and how many for each reason?
   Which reason does chemlib's `salt` fault end up under, and why?
2. *(Builds on section 2.)* Set `CHEMRUN_MAX_ATTEMPTS` to `"0"` and `CHEMRUN_FIRST_DELAY_S` to `"60"`
   in the environment (`os.environ`, as the lesson does with the batch size), leave everything else
   unchanged, and start `RunSettings()`. Which problems are reported? Remove the two values again
   afterwards. Then write a new version of `RunSettings` with one more `@model_validator` check:
   `batch_size` must be no larger than `n_molecules`. Show it refusing a bad pair of values.
3. *(Builds on section 6.)* Run the library from question 1 through `run_pipeline` with batches of
   500 and `crash_at=9`, on a new database file. How many rows are in the tables `molecules`,
   `quarantine` and `checkpoints` after the crash? Resume it by calling `run_pipeline` again
   without `crash_at`: which batches does the second call run? Then run the same library into a
   second new database without a crash, and show with `pd.testing.assert_frame_equal` that the two
   give identical tables.
4. *(Builds on section 5.)* Write a copy of `save_batch` that uses a plain `INSERT` (the same SQL
   without its `ON CONFLICT ... DO UPDATE` part, so it is no longer an upsert), and repeat question 3
   with it. Pass your copy in place of the lesson's by redefining `save_batch` in a new cell, and
   redefine it back afterwards. What happens when the resumed run reaches the batch that crashed,
   and why is this failure better than the one in the lesson's pandas `to_sql` example?
5. *(Builds on section 4.)* Call `with_retries` with `FlakyService(failures=4)`, `max_attempts=5`,
   `rng=random.Random(7)` and `sleep=waits.append` (with `waits = []` first), as the lesson does.
   How long does it wait in all? Repeat it 1,000 times with seeds 0 to 999 and report the mean and
   the largest total wait. What would the total be without jitter, that is, if each wait were the
   full ceiling?
6. **To think about.** *(Builds on sections 5 to 7.)* Your pipeline writes each batch's results as a
   Parquet file (`batch-0007.parquet`) to a shared folder, and a second team's pipeline picks up
   every new file in that folder. Design how the files are written and how the checkpoint is
   recorded so that the second team never reads a half-written file and never processes a batch
   twice, even when your run crashes and is resumed. Which of the ideas in this module do you need,
   and what is left that the second team has to do on their side?
7. **To think about.** *(Builds on section 9; no code needed.)* You start a run of two million
   molecules on your group's server, inside tmux and under a 32 GB memory limit, and go home. Next
   morning the session is gone and the log ends at batch 1,412 with no error message. List the
   likely causes, and say which line of which log would tell them apart: your own `work/run.log`,
   or the system's log, which on Linux with systemd you read on the server with
   `journalctl --user`. Then write the exact commands you would type to carry on, so the final
   tables equal those of a run that never stopped.
