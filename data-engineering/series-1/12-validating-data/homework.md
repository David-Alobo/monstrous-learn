# Homework: Validating data: records with Pydantic, tables with Pandera

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. If you are in a cohort, you will be told
where to send your answers; everyone can check theirs against the answers published after the
cohort's deadline.

1. A supplier sends this record: compound `ML-00054321`, SMILES `Cc1ccc(cc1)S(=O)(=O)N`, target
   `CDK2`, activity type `Ki`, value `0.0032`, units `mM`, pChEMBL `5.49`. Validate it with the
   lesson's `Measurement` model (give it the measurement id `M-000042`). Is it valid? If not, which
   rule fails, and what pChEMBL should it have?
2. Write a Pydantic model for one *assay* record: an assay id (`A-` and five digits), a target id,
   a temperature in °C between 4 and 45, and a pH between 0 and 14 that is optional. Add a model
   validator that refuses a cell-based assay (a field `format` that is `"cell"` or
   `"biochemical"`) run below 30 °C. Show one valid record and the errors for two invalid ones.
3. Build a new batch with `chemlib.library(3_000, seed=31)` as the compounds and
   `make_measurements(..., 8_000, seed=32)`, and inject faults with `seed=33`. How many rows does
   each check fail, and are all the injected faults caught?
4. Add a rule to the Pandera schema: an `EC50` must not be reported against `ABL1` (pretend this
   target only has binding assays). Write it as a table-level check, inject five rows that break
   it, and show that lazy validation reports exactly those five.
5. Repeat the timing of section 5 with the batch repeated 10, 40 and 100 times. How does the
   time per row change for each route as the table grows, and why?
6. **To think about:** the lesson quarantines a row that fails any check, and stops a batch when
   more than 5% of rows fail. For a nightly load of new ChEMBL activities into a team's database,
   which checks would you treat as "quarantine the row", which as "stop the batch", and which as
   "load it but warn"? What would you put in the alert, and who should receive it?
