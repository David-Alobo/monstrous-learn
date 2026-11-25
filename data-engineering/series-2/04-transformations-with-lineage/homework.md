# Homework: Transformations with lineage

Answer each question by running code like the code in the lesson: add a new cell at the end of the
lesson's notebook (in Colab, **+ Code**) and work there. Run the whole lesson first, so that its
warehouse, its dbt project (`work/lab_dbt`) and the `write`, `dbt` and `query` functions exist. If
you are in a cohort, you will be told where to send your answers; everyone can check theirs
against the answers published after the cohort's deadline.

1. *(Builds on section 2.)* A new plate reader writes micromolar as `umol/L`. Add that spelling to
   the `unit_to_nm` seed, run `dbt("build", "--select", "unit_to_nm+")`, and list what was
   rebuilt. Why did changing a CSV file rebuild models? Which models would have been wrong if you
   had loaded the seed but not rebuilt them?
2. *(Builds on section 3.)* Open the compiled SQL of `dim_target`
   (`target/compiled/lab/models/marts/dim_target.sql`) and of `stg_compounds`. What did each `ref`
   and `source` become? Then change `materialized` for the staging folder in `dbt_project.yml`
   from `view` to `table`, rebuild, and use `information_schema.tables` to show what changed in the
   warehouse.
3. *(Builds on section 4.)* Write a new mart, `marts.series_potency`, with one row per series and
   target: the number of compounds, the number of measured results and the mean pIC50 (measured
   values only). Build it with `dbt("build", "--select", "series_potency")`. Which models does it
   need, and how did dbt know to build them first?
4. *(Builds on section 4.)* Add the topological polar surface area
   (`rdkit.Chem.rdMolDescriptors.CalcTPSA`) to the Python model `dim_compound` as a column `tpsa`.
   Rebuild only what that change affects, using a selection with `+`. Which models were rebuilt,
   and why was `measurements_wide` among them although it does not show `tpsa`?
5. *(Builds on section 5.)* Use `dbt ls` with `--select` to answer, without building anything:
   (a) everything `measurements_wide` is built from; (b) everything that would need rebuilding if
   the raw `registry` table changed (`source:raw.registry+`); (c) the models in the `marts` folder
   only. Explain the difference between (a) and (b).
6. *(Builds on section 6.)* Add descriptions for `dim_target`, `dim_date` and every column of
   `stg_results` to the YAML files, run `dbt docs generate`, and print, from `manifest.json`, every
   model that still has no description. Why is that list worth checking on every change?
7. **To think about** *(no code; builds on sections 1 and 5)*: a colleague writes a model that
   reads `marts.fact_measurement` by its table name instead of with `ref`. The build still works.
   What has the team lost? Describe a change elsewhere in the project after which their model
   would silently show old or wrong data.
