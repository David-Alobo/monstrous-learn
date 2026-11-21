# Molecules as graphs, and graph databases

Work with molecules as graphs (rings, paths, substructure as graph matching, the largest shared substructure), then store chemistry that is all about links, synthesis routes and drug targets, in a Neo4j graph database and query it with Cypher.

- **Read the lesson:** [https://monstrous.com.ng/learn/data-engineering/series-1/05-graphs-and-graph-databases/](https://monstrous.com.ng/learn/data-engineering/series-1/05-graphs-and-graph-databases/)
- **Run it as a notebook:** [`notebook.ipynb`](notebook.ipynb)
- **The code on its own:** [`code.py`](code.py)
- **Homework:** [`homework.md`](homework.md)
- **The lesson's source:** [`lesson.md`](lesson.md); every output in it is checked by the tests

## Get set up

You can read this page without running anything. To run the code yourself, the easiest way needs nothing installed, only a web browser and a free Google account:

1. [Open this lesson in Google Colab](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/05-graphs-and-graph-databases/notebook.ipynb). Colab is Google's free service for running Python notebooks in the browser; sign in with your Google account if asked.
2. Run the cells in order, from the top: click the ▶ button at the left of a cell, or click inside it and press Shift+Enter. The first cell installs what the lesson needs and takes a minute or two.
3. If Colab warns "This notebook was not authored by Google", click **Run anyway**: the notebook comes from this course's own repository.
4. Under each cell you should see what the box labelled **Output** under the same code on the lesson's page shows (the notebook opens with our outputs already in place; running a cell replaces them with yours). Boxes labelled **Example output** show timings or memory, so your numbers will differ a little.

New to notebooks, or want to run the lessons on your own computer instead (with Jupyter, Anaconda or a terminal)? [Start here](https://monstrous.com.ng/learn/start/) shows every step.

If you already work in a terminal, the short version, with [uv](https://docs.astral.sh/uv/) and Git installed:

```bash
git clone https://github.com/David-Alobo/monstrous-learn.git
cd monstrous-learn/data-engineering/series-1
uv sync
uv run python 05-graphs-and-graph-databases/code.py
```

or, in any Python 3.11+ environment: `python -m pip install rdkit networkx pandas duckdb neo4j`.

**This lesson also needs Neo4j**, a database that runs in Docker on your own computer (Colab cannot run it; the rest of the lesson runs there). [The database guide](https://monstrous.com.ng/learn/databases/) shows how to install Docker and start it, step by step.

*This README, the notebook and `code.py` are made from `lesson.md` by `lessonkit.py --export`; edit the lesson, not them.*
