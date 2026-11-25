# Homework: Declarative ingestion

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
pipelines (`pipeline`, `strict` and `public`), its two inboxes and the `lab` object exist. If you
are in a cohort, you will be told where to send your answers; everyone can check theirs against
the answers published after the cohort's deadline.

1. *(Builds on section 2.)* Make a copy of the `registry` resource with the write disposition
   `"append"`, and load the six registry files into a new pipeline (a new `pipeline_name`, and the
   dataset `raw_append`), running once per week as section 2 did. How many rows does
   `raw_append.registry` hold, and how many distinct compounds? Explain the difference, and say
   which write disposition suits a snapshot file and which suits a file of new rows only.
2. *(Builds on section 3.)* Write weeks 7 and 8 into the first inbox with `lab.write_week`, then
   run `pipeline.run(assay())` once. How many rows were loaded? Week 8's file re-reads plate
   `P08-01`: its corrected rows have new `result_id`s (ending in `-c`), and every row has a new
   column `status`. Did the merge replace the first readings of that plate, or keep both? Why?
3. *(Builds on section 4.)* Write weeks 7 and 8 into the weekly inbox and run the strict pipeline
   for each, as section 4 did, with the same `try`/`except`. Which week stops, at which step, and
   because of which column? Then decide, as a person would: is this a change to allow, or a
   question for the lab? Allow it for one run with `apply_hints`. Is the contract frozen again for
   the run after that? (Look at which settings `assay_strict()` starts with each time it is
   called.)
4. *(Builds on section 4.)* Load the six weeks again into a new pipeline and dataset with
   `schema_contract={"columns": "discard_value"}` in place of `"freeze"`. What happens to the
   units of weeks 5 and 6, and does any error tell you so? Explain why `"discard_value"` would be a
   poor choice for this lab's assay files.
5. *(Builds on section 5.)* ChEMBL gives each activity both `standard_value` (in `standard_units`)
   and `pchembl_value`. For the EGFR activities in `raw.chembl_activities` with `standard_units`
   of `nM`, compute pIC50 yourself from `standard_value` (pIC50 = 9 − log10 of the IC50 in nM;
   DuckDB has `log10`, and `CAST(... AS DOUBLE)` turns text into a number) and compare it with
   `pchembl_value`. Do they agree? Count the rows by `standard_relation`: why are there none with
   `>` or `<`? (Look up what ChEMBL says a pChEMBL value is, and remember which filter section 5
   sent.)
6. *(Builds on section 6.)* Join `raw.assay` to `raw._dlt_loads` on the load ID
   (`_dlt_load_id` = `load_id`) and list, for each file name, the load that wrote its rows and when
   it finished (`inserted_at`). Then answer from the table alone: which files arrived in the same
   load?
7. **To think about** *(no code; builds on section 3)*: the assay resource remembers only the
   largest file name it has loaded. In week 11, week 10's late file arrives together with week
   11's, and both are loaded. But suppose the late file had arrived a week *after* week 11's file
   was loaded. What would the pipeline do with it, and would anyone notice? Suggest a different
   way for the resource to tell new files from old that would not miss it, and say what it costs.
