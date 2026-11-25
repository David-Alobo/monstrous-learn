# Homework: Tests and contracts in the warehouse

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
warehouse (now holding weeks 1 to 8 in the raw layer), its dbt project and the `write`, `dbt` and
`query` functions exist. If you are in a cohort, you will be told where to send your answers;
everyone can check theirs against the answers published after the cohort's deadline.

1. *(Builds on section 1.)* Add an `accepted_values` test on `stg_results.target` with the five
   kinases of the project, and a `relationships` test from `stg_results.target` to the `targets`
   seed. Which of the two would you keep, and why? (Think about what happens when the lab adds a
   sixth kinase.)
2. *(Builds on section 2.)* dbt can save the rows a test found, so that they can be examined after
   the build: add `config: {store_failures: true}` under the grain test, run `dbt("test")`, and
   find the table it wrote (look in `information_schema.tables` for a schema whose name ends in
   `dbt_test__audit`). How many rows does it hold, and which plates appear in it?
3. *(Builds on section 2.)* Write a singular test that fails if any compound was measured on a panel
   kinase without ever being measured on EGFR (the lab's rule: the panel comes after EGFR). Does
   it pass on weeks 1 to 8? Choose its severity, and give your reason in a comment in the test.
4. *(Builds on section 3.)* Try to put an enforced contract on `dim_compound`, which is a Python
   model. Does dbt accept it, and does the build check it? Then put one on `dim_target`, and break
   it by renaming a column in the model's SQL. What does the message show?
5. *(Builds on section 4.)* Add a rule to `compound_rules` that no compound may contain a reactive
   group, using `pc.no_substructures` with at least the acyl halide and aldehyde patterns of
   pandera-chem's documentation. Run it on weeks 1 to 8. Then save the report card as a web page,
   `Path("work/compounds.html").write_text(pc.report_html(checked), encoding="utf-8")`, and open
   it in a browser (in Colab, download it from the Files panel first).
6. *(Builds on section 5.)* Without changing anything else, make the grain test a warning instead
   of an error, and run `dbt("build")` again. What does the build do now, and what does
   `marts.fact_measurement` hold? Explain in two or three sentences why that would be the wrong
   choice for this test, and name one test in the project for which a warning would be right.
7. **To think about** *(no code; builds on sections 1, 3 and 5)*: tests, contracts, pandera-chem's
   checks, and dlt's schema contract of Module 2 each stop a different kind of problem at a
   different place. Make a table with one row per problem the lab has met so far (unit spellings,
   the resent file, the renamed column, LAB-0042's structure, the re-read plate) and say which of
   them would catch it first, and where in the pipeline.
