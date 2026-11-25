# Homework: Continuous integration for data

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that the
lab's repository (`work/lab-repo`, with `ci.py`), the `pull_request` and `run_ci` functions and the
two CI runs exist. If you are in a cohort, you will be told where to send your answers; everyone
can check theirs against the answers published after the cohort's deadline.

1. *(Builds on section 1.)* Run `ci.py` with the same project as base and head
   (`run_ci(REPO / "lab_dbt", "no-change")`). What does the report say the change touches, and how
   do the contents differ? Why is that the right answer, and why is it a useful run to keep in a
   CI's own tests?
2. *(Builds on section 2.)* Open the two warehouses of the `add-tpsa` run (`work/ci/add-tpsa/base`
   and `.../head`) with DuckDB and confirm the report by hand: the new column's values for five
   compounds, and a query that shows the two `fact_measurement` tables are the same apart from
   `load_id`.
3. *(Builds on section 2.)* Change `ci.py` so that the report also lists the tests that ran on the
   models the change touches, with their results (the results of `build` carry each node's name and
   status; `dbt ls --select state:modified+ --resource-type test` names the tests). Rerun the
   `round-pic50` pull request.
4. *(Builds on section 3.)* Make a third pull request that renames the column `heavy_atoms` to
   `n_heavy_atoms` in `dim_compound`. Does CI pass? What does the diff report, and which readers of
   the warehouse would this change break although every test passed? How could the project make
   such a change fail CI? (Think of Module 5, section 3.)
5. *(Builds on section 3.)* Make a pull request that changes the potency cut-off for the panel in
   a new mart of your own, `marts.panel_candidates` (compounds with a mean measured EGFR pIC50 of
   at least 7.5). What does the diff say about a model that does not exist on `main`? Change
   `diff` so that a new model is reported as new instead.
6. *(Builds on section 4.)* The workflow runs only when files under `lab_dbt/` or `ci.py` change.
   Give one change that would break the warehouse but would not start the workflow, and change
   `paths` so that it would. What is the cost of running CI on every change?
7. **To think about** *(no code; builds on sections 1 and 4)*: CI builds on eight weeks of
   synthetic data. Name one kind of problem it can never catch, because the test data cannot
   contain it, and say which module's tool would catch it instead, after the change is merged.
