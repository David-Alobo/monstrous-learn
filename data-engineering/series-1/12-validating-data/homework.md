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
6. *(Builds on section 2, "Letting a library check the units"; optional, like that part.)* A
   supplier reports three IC50 values as a mass per volume: paracetamol
   (`CC(=O)Nc1ccc(O)cc1`), 1.5 µg/mL; caffeine (`Cn1cnc2c1c(=O)n(C)c(=O)n2C`), 250 ng/mL; and
   diphenhydramine supplied as its hydrochloride salt (`CN(C)CCOC(c1ccccc1)c1ccccc1.Cl`), 2 µg/mL.
   Use pint and RDKit, as the lesson does, to give each value in nM and as a pIC50. For
   diphenhydramine, work it out twice: with the molecular weight of the salt as written, and with
   that of the parent molecule alone (drop the `.Cl`). How far apart are the two pIC50 values, and
   which one is right if the 2 µg/mL was weighed out as the salt? Finally, what does
   `is_concentration` say for a units column that holds `ng/mL`, and what would you do with such
   rows in a pipeline that expects molar units?
7. *(Builds on section 2, "Letting a library check the units"; optional.)* A lab notebook records
   reaction times typed by different people: `1min`, `1 min`, `1 minute`, `1minute`, `1mins`,
   `1minutes`, `1 Min`, `1m`, `~1 min`, `1-2 min`, `90 s` and `1h30`. Read each with
   `ureg.Quantity(text)` (inside `try`/`except`, as `is_concentration` does) and convert it to
   seconds. Which become 60 seconds? Which fail with an error, and which are read *wrongly without
   an error* (check what pint thinks `1 Min` and `1m` are, and what happens to the `~`)? Then write
   a function `to_seconds(text)` that returns the time in seconds, or `None` with the reason, by:
   trimming and lower-casing the text (and say why lower-casing is safe here but would be wrong for
   a concentration column); refusing text that starts with `~`, `<` or `>` (that belongs in its own
   column, like ChEMBL's `standard_relation`); applying a small written table of local shorthand
   (for example `1h30` meaning 90 minutes); checking that the result is a time; and refusing
   anything over 7 days. Show the result for every string above.
8. **To think about** *(no code; builds on section 4, "Stop the batch, or let it through?")*: the
   lesson quarantines a row that fails any check, and stops a batch when more than 5% of rows fail.
   For a nightly load of new ChEMBL activities into a team's database, which checks would you treat
   as "quarantine the row", which as "stop the batch", and which as "load it but warn"? What would
   you put in the alert (the message the pipeline sends to a person when something goes wrong),
   and who should receive it?
