# Changelog

Releases are tagged per series (`series1-v1.0`, …). Each lesson links to the release it was
published with, so learners can always reproduce what they read.

## Unreleased

### Data Engineering for Chemistry, Series 1
- Module 1, *Molecules as graphs and matrices*: lesson, figures, homework, further reading.
- Module 2, *Molecules as text, patterns and numbers*: lesson, figures, homework, further reading.

### Data Engineering for Chemistry, Series 2
- All eleven modules of *The Modern Data Stack for Chemistry*, each with its lesson, homework,
  notebook (tested as Colab runs it), script and README: lab data architecture; declarative
  ingestion (dlt, with recorded ChEMBL answers); modelling the warehouse (DuckDB star schema);
  transformations with lineage, tests and contracts, history and corrections (dbt, pandera-chem);
  orchestration (Prefect); observability; continuous integration; structure-activity dashboards
  (Streamlit, tested with AppTest); and the capstone, with its brief and peer-review rubric.
- `labdata.py`: the series' lab, twelve weeks of a kinase project with seven planted problems.
- `labstack.py` and `stages/`: what earlier modules built, so each lesson starts on its own;
  `make_stages.py` and `test_stages.py` keep the saved dbt projects in step with the lessons.

### Course site
- Home page with three tracks (Data Engineering for Chemistry; MLOps for Chemists and Agentic AI in
  Chemistry to come), track and course pages, lesson pages.
