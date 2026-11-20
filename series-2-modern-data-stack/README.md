# Series 2: The Modern Data Stack for Chemistry

Production tools for lab data: ingestion, warehousing, transformation and scheduling.

**Status:** Planned · **Level:** After Series 1

The tools data teams use in industry, applied to chemistry: declarative ingestion, a fast local warehouse, version-controlled transformations with lineage, scheduled pipelines and dashboards for medicinal chemists.

## Modules

1. **Designing a lab data architecture.** From folders and spreadsheets to a modular open-source stack.
2. **Declarative ingestion.** Load chemical APIs and lab exports incrementally, coping with changing schemas. (dlt)
3. **A fast analytical warehouse.** Query millions of descriptors locally with DuckDB and Parquet. (DuckDB, Parquet)
4. **Transformations with lineage.** Version-controlled models joining structures with assay results. (dbt)
5. **Scheduled pipelines.** Run standardisation and fingerprint updates automatically when new data arrives. (Prefect)
6. **Structure-activity dashboards.** Interactive views of structure-activity relationships for medicinal chemists.

Each module will have its own folder here (`01-…`, `02-…`) with its code, tests, lesson
and notebook. This file is written from `shared/site/catalogue.json` by
`python -m shared.site.build`; the course page is
https://monstrous.com.ng/learn/series-2/.
