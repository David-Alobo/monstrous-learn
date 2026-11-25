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

4. **[Transformations with lineage](04-transformations-with-lineage/)**. Turn raw tables into clean ones with SQL models that reference each other; dbt builds them in order, draws the lineage graph and writes the documentation. *dbt*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/04-transformations-with-lineage/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/04-transformations-with-lineage/notebook.ipynb)

5. **[Tests and contracts in the warehouse](05-tests-and-contracts/)**. Check every build: dbt tests for keys, values and relationships, model contracts, and chemistry checks on structures with pandera-chem. *dbt, pandera-chem*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/05-tests-and-contracts/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/05-tests-and-contracts/notebook.ipynb)

6. **[History and corrections](06-history-and-corrections/)**. Assays are corrected and compounds re-registered: keep every version with snapshots, and rebuild only what changed with incremental models. *dbt*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/06-history-and-corrections/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/06-history-and-corrections/notebook.ipynb)


### Operations

7. **[Orchestration](07-orchestration/)**. Run the lab's weekly pipeline as a flow: tasks, retries for the failures that pass, caching, a failed build that stops before publishing, the record of every run, schedules, and the ways new data can start a run. *Prefect*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/07-orchestration/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/07-orchestration/notebook.ipynb)

8. **[Observability](08-observability/)**. Know when something is wrong before the chemists do: freshness, row counts, schema changes and drift in molecular properties, with alerts. *Prefect, dbt*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/08-observability/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/08-observability/notebook.ipynb)

9. **[Continuous integration for data](09-continuous-integration/)**. Test every change before it reaches the warehouse: dbt builds and checks on each pull request, in GitHub Actions. *GitHub Actions, dbt*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/09-continuous-integration/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/09-continuous-integration/notebook.ipynb)


### Serving

10. **[Structure-activity dashboards](10-structure-activity-dashboards/)**. Give medicinal chemists interactive views of their series: structures, potencies and trends, served from the warehouse. *Streamlit*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/10-structure-activity-dashboards/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/10-structure-activity-dashboards/notebook.ipynb)


### Capstone

11. **[Capstone: a running data stack for a small lab](11-capstone/)**. Ingest, model, test, schedule, monitor and serve one lab's chemistry data end to end, and hand it over with its documentation. *Everything above*

   [Read the lesson](https://monstrous.com.ng/learn/data-engineering/series-2/11-capstone/) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-2/11-capstone/notebook.ipynb)


Each module folder holds the lesson (`lesson.md`), a notebook, the code on its own
and the homework. New to notebooks?
[Start here](https://monstrous.com.ng/learn/start/) shows every step.

*This file is written from `shared/site/catalogue.json` by `python -m shared.site.build`;
the course page is https://monstrous.com.ng/learn/data-engineering/series-2/.*
