# Maintaining the courses

Notes for whoever builds and publishes the course site. Learners do not need any of this; see the
[README](README.md) instead.

## How the repository is organised

```
<track>/           one folder per track (data-engineering, mlops, agentic-ai)
  series-N/        one folder per course: its own environment (pyproject.toml + uv.lock)
    NN-…/          one folder per module: code, tests, the lesson text and a notebook
shared/
  site/            builds the pages at monstrous.com.ng/learn/ from site/catalogue.json
  docker/          the PostgreSQL + RDKit and Neo4j stack the courses use
data/              download scripts only: no data files are committed
tests/             tests of the shared code and the site
```

Each series has its own environment so that the tools of one (say, dbt and Prefect) never clash
with another's. Every code example in a lesson is run by the tests before it is published.
Releases are tagged per series (`series1-v1.0`), and each lesson points to its tag.

## Generated files

Some files are written by the build and must not be edited by hand:

- each track's and course's `README.md`, from `shared/site/catalogue.json`;
- the module table in the root `README.md`, between the `modules:start` and `modules:end` markers;
- each module's `README.md`, `notebook.ipynb` and `code.py`, from its `lesson.md`
  (`lessonkit.py --export`).

The tests fail if any of them is out of date.

## Building the pages

```bash
uv sync
uv run pytest
uv run python -m shared.site.build --zip   # dist/learn/ and dist/learn.zip
```

`dist/learn.zip` is unpacked on the web host inside `public_html/learn/`. To add a track or a
course, add it to `shared/site/catalogue.json`; its page, links and README follow.

Settings such as passwords live in `.env` (copied from `.env.example`), which Git ignores.

## Before publishing

Before any release, run:

```bash
uv run python tools/prepublish.py
```

It scans every version of every file for credentials, private details, homework answers, data files
and large files. Homework answers and cohort records are never kept here: they live in a separate
private repository.
