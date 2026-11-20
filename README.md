# Monstrous Data · Learn

Free, practical courses in data engineering for chemists, from
[Monstrous Data](https://monstrous.com.ng). The lessons are published at
[monstrous.com.ng/learn](https://monstrous.com.ng/learn/); this repository holds their code, tests
and the pages themselves.

| Series | Course | Status |
|---|---|---|
| 1 | [Data Engineering for Cheminformatics](series-1-cheminformatics-data-engineering/): foundations, scale, reliability | Opens January 2027 |
| 2 | [The Modern Data Stack for Chemistry](series-2-modern-data-stack/) | Planned |
| 3 | [Data Pipelines for Digital and Autonomous Chemistry](series-3-autonomous-chemistry/) | Planned |

## How the repository is organised

```
series-N-…/        one folder per course: its own environment (pyproject.toml + uv.lock),
  NN-…/            one folder per module: code, tests, the lesson text and a notebook
shared/
  site/            builds the pages at monstrous.com.ng/learn/ from site/catalogue.json
  docker/          the PostgreSQL + RDKit stack every course uses (from Series 1, Module 1)
data/              download scripts only: no data files are committed
tests/             tests of the shared code and the site
```

Each series has its own environment so that the tools of one (say, dbt and Prefect) never clash
with another's. Every code example in a lesson is run by the tests before it is published.
Releases are tagged per series (`series1-v1.0`), and each lesson points to its tag.

## Building the pages

```bash
uv sync
uv run pytest
uv run python -m shared.site.build --zip   # dist/learn/ and dist/learn.zip
```

`dist/learn.zip` is unpacked on the web host as `public_html/learn/`. To add a course, add it to
`shared/site/catalogue.json` and give it a folder.

## Licences

- Code: MIT ([LICENSE](LICENSE)).
- Lesson text and figures: Creative Commons Attribution 4.0 ([LICENSE-content](LICENSE-content)).
- Datasets keep their own licences, named in each module.

Questions and corrections: [contact@monstrous.com.ng](mailto:contact@monstrous.com.ng), or open an
issue.
