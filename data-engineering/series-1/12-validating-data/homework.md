# Homework: Validating data: records with Pydantic, tables with Pandera

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
functions and tables exist. If you are in a cohort, you will be told where to send your answers;
everyone can check theirs against the answers published after the cohort's deadline.

1. *(Builds on section 2, "Good records and bad records".)* A supplier sends this record: compound
   `ML-00054321`, SMILES `Cc1ccc(cc1)S(=O)(=O)N`, target `CDK2`, activity type `Ki`, value
   `0.0032`, units `mM`, pChEMBL `5.49`. Write it as a dictionary like the lesson's `good`, give it
   the measurement id `M-000042`, and validate it with the lesson's `Measurement` model (the
   `show_errors` helper prints the problems). Is it valid? If not, which rule fails, and what
   pChEMBL should it have? (Recall pChEMBL = 9 − log10 of the value in nM.)
2. *(Builds on section 2, "A model for one measurement".)* Write a Pydantic model for one *assay*
   record (an assay is the experiment a measurement comes from) with these fields: an assay id
   (`A-` and five digits, checked with a regular expression as `MEASUREMENT_ID` is), a target id,
   a temperature in °C between 4 and 45, a pH between 0 and 14 that is optional, and a field
   `format` that is either `"cell"` or `"biochemical"`. Add a model validator that refuses a
   cell-based assay (format `"cell"`) run below 30 °C. Show one valid record and the errors for two
   invalid ones.
3. *(Builds on sections 3 and 4.)* Build a new batch: make the compounds table as the lesson does,
   but with `chemlib.library(3_000, seed=31)`; make 8,000 measurements with
   `make_measurements(compounds, 8_000, seed=32)`; and add faults with
   `inject_faults(..., seed=33)`. Check it with the lesson's schema (build a new one with
   `measurement_schema` for the new compounds) using `lazy=True`. How many rows does each check
   fail, and are all the injected faults caught?
4. *(Builds on section 4, "A schema for the whole table".)* Add a rule to the Pandera schema: an
   `EC50` must not be reported against `ABL1` (pretend this target only has binding assays, which
   give Ki or Kd, not EC50). Write it as a table-level check, a function like
   `pchembl_matches_value` that returns `True` or `False` for every row. Change five rows of the
   clean table so that they break it, and show that lazy validation reports exactly those five.
5. *(Builds on section 5, the optional timing.)* Repeat the timing of section 5 with the batch
   repeated 10, 40 and 100 times (change `BENCHMARK_COPIES`, or the `40` in your own copy of the
   code). How does the time per row change for each route as the table grows, and why?
6. **To think about** *(no code; builds on section 4, "Stop the batch, or let it through?")*: the
   lesson quarantines a row that fails any check, and stops a batch when more than 5% of rows fail.
   For a nightly load of new ChEMBL activities into a team's database, which checks would you treat
   as "quarantine the row", which as "stop the batch", and which as "load it but warn"? What would
   you put in the alert (the message the pipeline sends to a person when something goes wrong),
   and who should receive it?
