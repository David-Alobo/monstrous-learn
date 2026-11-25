# Series 2: The Modern Data Stack for Chemistry

Track: Data Engineering for Chemistry. The industry tools that run chemical data pipelines: ingestion, warehousing, transformation, testing, orchestration and dashboards.

**Status:** Planned · **Level:** After Series 1 · **[Read it online](https://monstrous.com.ng/learn/data-engineering/series-2/)**

Series 1 built each piece of a chemical data pipeline by hand. Series 2 hands those pieces to the open-source tools data teams use in industry, one by one: declarative ingestion with dlt, a DuckDB warehouse modelled for compounds and assays, transformations, tests and history with dbt, orchestration with Prefect, observability, continuous integration, and structure-activity dashboards in Streamlit. Every module says which Series 1 module it replaces, and everything runs in the browser as well as on your own computer.

## Modules

### Foundations

1. **[Designing a lab data architecture](01-lab-data-architecture/)**. From folders and spreadsheets to layers a team can trust: raw, staging and marts; extract-load-transform; and where each piece of Series 1 goes in a modern data stack.

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/01-lab-data-architecture/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/01-lab-data-architecture/notebook.ipynb)

2. **[Declarative ingestion](02-declarative-ingestion/)**. Load the lab's instrument files and ChEMBL's API by declaring what to load, not how: schema inference, incremental loading, duplicates absorbed by a primary key, and schema changes followed or refused by a contract, compared with Series 1's hand-written loader. *dlt*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/02-declarative-ingestion/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/02-declarative-ingestion/notebook.ipynb)

3. **[Modelling the warehouse](03-modelling-the-warehouse/)**. Compounds, targets, dates and measurements as a star schema in DuckDB: the grain, dimensions that work out chemistry once, keys the database enforces, which potencies can be averaged, and why analysts and dashboards need this shape. *DuckDB*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/03-modelling-the-warehouse/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/03-modelling-the-warehouse/notebook.ipynb)


### Transformation

4. **Transformations with lineage.** Turn raw tables into clean ones with SQL models that reference each other; dbt builds them in order, draws the lineage graph and writes the documentation. *dbt*
5. **Tests and contracts in the warehouse.** Check every build: dbt tests for keys, values and relationships, model contracts, and chemistry checks on structures with pandera-chem. *dbt, pandera-chem*
6. **History and corrections.** Assays are corrected and compounds re-registered: keep every version with snapshots, and rebuild only what changed with incremental models. *dbt*

### Operations

7. **Orchestration.** Run the whole pipeline as a flow: tasks, retries, caching, schedules, and runs triggered when new data arrives. *Prefect*
8. **Observability.** Know when something is wrong before the chemists do: freshness, row counts, schema changes and drift in molecular properties, with alerts. *Prefect, dbt*
9. **Continuous integration for data.** Test every change before it reaches the warehouse: dbt builds and checks on each pull request, in GitHub Actions. *GitHub Actions, dbt*

### Serving

10. **Structure-activity dashboards.** Give medicinal chemists interactive views of their series: structures, potencies and trends, served from the warehouse. *Streamlit*

### Capstone

11. **Capstone: a running data stack for a small lab.** Ingest, model, test, schedule, monitor and serve one lab's chemistry data end to end, and hand it over with its documentation. *Everything above*

Each module folder holds the lesson (`lesson.md`), a notebook, the code on its own
and the homework. New to notebooks?
[Start here](https://monstrous.com.ng/learn/start/) shows every step.

*This file is written from `shared/site/catalogue.json` by `python -m shared.site.build`;
the course page is https://monstrous.com.ng/learn/data-engineering/series-2/.*
