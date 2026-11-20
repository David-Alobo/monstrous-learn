# Monstrous Data · Learn

[![tests](https://github.com/David-Alobo/monstrous-learn/actions/workflows/ci.yml/badge.svg)](https://github.com/David-Alobo/monstrous-learn/actions/workflows/ci.yml)

Free, practical courses in data engineering for chemists, from
[Monstrous Data](https://monstrous.com.ng). The lessons are published at
[monstrous.com.ng/learn](https://monstrous.com.ng/learn/); this repository holds their code, tests
and the pages themselves.

| Track | Courses | Status |
|---|---|---|
| [Data Engineering for Chemistry](data-engineering/) | Series 1: Data Engineering for Cheminformatics · Series 2: The Modern Data Stack for Chemistry · Series 3: Data Pipelines for Digital and Autonomous Chemistry | Series 1 opens January 2027 |
| [MLOps for Chemists](mlops/) | Outline to follow | Coming later |
| [Agentic AI in Chemistry](agentic-ai/) | Outline to follow | Coming later |

We start with the data, because models and agents are only as good as the data behind them.

## Any device

Every lesson reads well on a phone, tablet or laptop, and every module can be run in a browser
(the whole setup, database included, runs online) or on Windows, macOS or Linux. Nothing in a
module may depend on one operating system, a paid tool or a powerful computer; the larger runs are
optional and say so.

## How the course runs

A cohort starts on a set date and takes one module a week, with homework, a Discord community and
a peer-reviewed capstone that earns a certificate. Afterwards every module stays open to follow at
your own pace.

## How the repository is organised

```
<track>/           one folder per track (data-engineering, mlops, agentic-ai)
  series-N-…/      one folder per course: its own environment (pyproject.toml + uv.lock)
    NN-…/          one folder per module: code, tests, the lesson text and a notebook
shared/
  site/            builds the pages at monstrous.com.ng/learn/ from site/catalogue.json
  docker/          the PostgreSQL + RDKit stack every course uses (from Series 1, Module 1)
data/              download scripts only: no data files are committed
tests/             tests of the shared code and the site
```

Each series has its own environment so that the tools of one (say, dbt and Prefect) never clash
with another's. Every code example in a lesson is run by the tests before it is published.
Releases are tagged per series (`series1-v1.0`), and each lesson points to its tag.

## Before publishing

The whole history becomes public with the repository, so before any release run:

```bash
uv run python tools/prepublish.py
```

It scans every version of every file for credentials, private details, homework answers, data files
and large files. Homework answers and cohort records are never kept here: they live in a separate
private repository.

## Building the pages

```bash
uv sync
uv run pytest
uv run python -m shared.site.build --zip   # dist/learn/ and dist/learn.zip
```

`dist/learn.zip` is unpacked on the web host as `public_html/learn/`. To add a track or a course, add
it to `shared/site/catalogue.json`; its page, links and README follow.

## Licences

- Code: MIT ([LICENSE](LICENSE)).
- Lesson text and figures: Creative Commons Attribution 4.0 ([LICENSE-content](LICENSE-content)).
- Datasets keep their own licences, named in each module.

Found an error, or want to help? See [CONTRIBUTING.md](CONTRIBUTING.md); everyone taking part follows
the [code of conduct](CODE_OF_CONDUCT.md). Questions and corrections: [contact@monstrous.com.ng](mailto:contact@monstrous.com.ng), or open an
issue.
