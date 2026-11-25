# Homework: History and corrections

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
warehouse (with weeks 1 to 9), its dbt project and the `write`, `edit`, `dbt` and `query` functions
exist. If you are in a cohort, you will be told where to send your answers; everyone can check
theirs against the answers published after the cohort's deadline.

1. *(Builds on section 1.)* For each column of `dim_compound`, say which SCD type (0, 1 or 2) the
   lab should use for it, and why: `parent_smiles`, `salt`, `chemist`, `vendor`, `registered_on`,
   `series`, `clogp`. Are there columns whose history nobody will ever need?
2. *(Builds on section 2.)* Make a copy of the snapshot with `check_cols: all` (call it
   `registry_history_all`), then rerun the weekly loop of section 2 in a fresh copy of the lesson
   (or delete the warehouse and start again). How many versions does it keep, and why? What does
   that say about choosing `check_cols`?
3. *(Builds on section 3.)* Write a model `compound_as_of` that takes a date from a variable
   (`{{ var('as_of') }}`) and returns every compound as the registry described it on that date.
   Build it with `dbt("build", "--select", "compound_as_of", "--vars", "{as_of: '2026-10-01'}")`
   and compare LAB-0042 on 1 October and on 1 November.
4. *(Builds on section 4.)* Using the fact table (not the wide view), compare each well of plate
   `P08-01` before and after its correction: for every compound and target, the superseded and the
   corrected pIC50. By how much did the correction change the potencies, on average? Would any
   compound have been sent to the selectivity panel (EGFR pIC50 of 7 or more) on the first reading
   but not on the second?
5. *(Builds on section 5.)* Change the formula of `pic50` in `stg_results` (round it to two
   decimals), then run `dbt("build", "--select", "stg_results+")` without `--full-refresh`. Which
   rows of `fact_measurement` have the new rounding and which do not? Which test notices, and
   what fixes it?
6. *(Builds on sections 4 and 5.)* Suppose the lab re-reads a plate of week 6 in week 11, and
   sends only the corrected rows, with new IDs, and a separate list of the IDs they supersede. Sketch
   (in SQL, or in words) how `stg_results` and the incremental `fact_measurement` would have to
   change so that the old readings are marked `superseded`. Why is this harder than the week 8 case?
7. **To think about** *(no code; builds on section 2)*: the snapshot's dates are the times dbt ran,
   and its versions are only as fine as the snapshots: if the lab changed a structure on Tuesday
   and back again on Thursday, a weekly snapshot would never see it. What would the lab need to
   send so that the warehouse could keep its history exactly? Who should own that history, the lab's
   registry or the warehouse?
