# Homework: Designing a lab data architecture

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
database (`work/lab.duckdb`), its inbox and the `lab` object exist; reopen the database with
`db = duckdb.connect(str(WAREHOUSE))`, because the lesson closes it at the end. If you are in a
cohort, you will be told where to send your answers; everyone can check theirs against the answers
published after the cohort's deadline.

1. *(Builds on section 1.)* Using only the stacked pandas table of section 1 (`stacked`), work out
   how many measurements of `LAB-0057` on EGFR are really there, and its mean pIC50, by removing
   the duplicates yourself and converting the units yourself. How many lines of pandas did it
   take, and what would another person need to know to get the same answer?
2. *(Builds on section 3.)* Write weeks 7 and 8 into the inbox with `lab.write_week`, then run
   `load_raw(db)` again. What does `DESCRIBE raw.assay` show now that it did not before, and why
   did the load still work? Which week's file brought the new column?
3. *(Builds on section 4.)* After loading weeks 7 and 8, look at `staging.results` for plate
   `P08-01`. Week 8's file has a `status` column: what are its values, and what does the staging
   view do with the rows marked `superseded`? Write the line of SQL you would add to the view so
   that a superseded result no longer reaches the marts, and say in one sentence why that fix
   belongs in staging and not in a mart. (Module 6 handles this properly, with history.)
4. *(Builds on section 5.)* Write a third mart, `marts.series_summary`, with one row per chemical
   series (the `series` of each compound is in `lab.compounds`; load it into DuckDB first, as a
   table in the staging layer): the number of compounds tested on EGFR, their median EGFR pIC50,
   and how many reached the selectivity panel. Which series looks most promising?
5. *(Builds on section 6.)* Make the reconciliation check of section 6 fail on purpose: delete one
   row from a copy of the raw table, rebuild the views on the copy, and run the check. Then write
   a second check that compares the number of compounds in `staging.compounds` with the number of
   rows in the latest registry file. Why does a team run checks like these after every load?
6. **To think about** *(no code; builds on sections 2 and 7)*: a colleague proposes saving time by
   cleaning the files as they arrive (fixing units and removing duplicates in Python) and loading
   only the cleaned data into the warehouse. Using the idea of ELT, explain what the lab would
   lose. Then think of one situation in which cleaning before loading would be the right choice.
