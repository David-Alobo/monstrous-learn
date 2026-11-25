# Homework: Capstone: a running data stack for a small lab

The main homework of this module is the capstone brief at the end of the lesson. These warm-up
questions get you used to `stack.py` before you start. Answer them by running code like the code in
the lesson: add a new cell at the end of the lesson's notebook (in Colab, **+ Code**) and work there.
Run the whole lesson first, so that the stack's warehouse, its published copy, Prefect's record and
the `settings` exist. If you are in a cohort, you will be told where to send your answers; everyone
can check theirs against the answers published after the cohort's deadline.

1. *(Builds on section 7.)* Add descriptions for `dim_target`, `dim_date` and
   `dim_compound_history` (and their columns) to the project's YAML files in `work/lab_dbt`, run
   `dbt docs generate` again, and check that every model now has one.
2. *(Builds on sections 2 and 4.)* Run the stack for a third lab: `stack.Settings(work="work3",
   seed=3)`, with `stack.prepare` and `stack.run_weeks`. (Prefect's record is shared, so the
   lesson's flow runs stay in it.) Which alerts are the same as for seed 2, which differ, and why?
   Is there a planted problem that one of the checks missed for this lab?
3. *(Builds on section 3.)* `publish` writes the new copy under another name and then renames it
   over the old one. Explain what a dashboard reading the copy at the wrong moment would see if
   `publish` copied straight onto the old file instead. Why does renaming not have that problem?
4. *(Builds on section 4.)* Make week 6 fail: before running it, change a model in the stack's dbt
   project so that it cannot be built, run `stack.run_weeks(settings, range(6, 7))` in a fresh copy
   of the lesson that stopped after week 5, then fix the model and run week 6 again. What did the
   dashboard's copy hold between the failed run and the rerun?
5. *(Builds on section 5.)* Back up the one table that cannot be made again: write a function that
   exports `snapshots.registry_history` from the published copy to a dated Parquet file
   (`COPY ... TO '...parquet' (FORMAT parquet)`), and another that restores it into an empty
   warehouse. Test the pair.
6. *(Builds on the brief.)* Choose your capstone's lab and write the first paragraph of its README:
   which lab, which weeks, and which of the six requirements you expect to be hardest, and why.
