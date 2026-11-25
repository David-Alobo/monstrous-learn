# Homework: Modelling the warehouse

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
warehouse (`work/lab.duckdb`) and the `lab` object exist; reopen the database with
`db = duckdb.connect(str(WAREHOUSE))`, because the lesson closes it at the end. If you are in a
cohort, you will be told where to send your answers; everyone can check theirs against the answers
published after the cohort's deadline.

1. *(Builds on section 2.)* Suppose the lab had chosen a coarser grain: one row per compound and
   target, with the replicates averaged. Build that table from `marts.fact_measurement` (call it
   `marts.fact_potency`). Which of the four questions of section 1 can it still answer, and which
   question about the plates can it no longer answer? Give one example of such a question.
2. *(Builds on section 3.)* `lab.compounds` holds each compound's true series (column `series`), as
   the lab's chemists planned it. Compare it with the series the dimension worked out by
   substructure. Do they agree for every compound except LAB-0042? Then add a property of your
   choice to `describe` (for example the topological polar surface area,
   `rdkit.Chem.rdMolDescriptors.CalcTPSA`) and rebuild the dimension with it.
3. *(Builds on section 4.)* Use the date dimension in its registration role to count how many
   compounds were registered in each project week. Then use it in its run-date role to count the
   measurements by `weekday`. What do you notice about the weekdays, and how could that column
   help someone spot a file whose dates were written wrongly?
4. *(Builds on section 5.)* Try to insert into `marts.fact_measurement` a row with an unknown
   target key, then one with a `result_id` that is already there, then one whose `relation` is
   `NULL`. Which constraint refuses each, and what does each error message say?
5. *(Builds on section 6.)* For each target, compare the plain mean of `ic50_nm` with the geometric
   mean (as in section 6), over measured results only. On which target is the difference largest,
   and why might that be? Then write one sentence for the warehouse's documentation that tells an
   analyst how to average potencies.
6. *(Builds on section 7.)* Answer question 4 of section 1 from the star: for every compound tested
   on the panel, its mean EGFR pIC50, its best pIC50 on another kinase (measured values only) and
   how many panel kinases reported it as too weak to measure. Which five compounds would you
   recommend, and why does the count of bounds matter for your choice?
7. **To think about** *(no code; builds on sections 3 and 8)*: a colleague suggests skipping the
   star and loading only `measurements_wide`, as a table, "because that is all the dashboards
   read". What goes wrong when LAB-0042's structure is corrected, or when a series is renamed?
   When is a wide table on its own a reasonable choice?
