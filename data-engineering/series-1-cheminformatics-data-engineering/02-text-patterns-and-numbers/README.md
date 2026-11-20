# Molecules as text, patterns and numbers

SMILES, InChI, molfiles, conformers, SMARTS, fingerprints and descriptors: what each keeps and loses, and which to store for which job.

- **Read the lesson:** [https://monstrous.com.ng/learn/data-engineering/series-1/02-text-patterns-and-numbers/](https://monstrous.com.ng/learn/data-engineering/series-1/02-text-patterns-and-numbers/)
- **Run it as a notebook:** [`notebook.ipynb`](notebook.ipynb)
- **The code on its own:** [`code.py`](code.py)
- **Homework:** [`homework.md`](homework.md)
- **The lesson's source:** [`lesson.md`](lesson.md); every output in it is checked by the tests

## Get set up

**In the browser, on any device:** [open this lesson as a notebook in Google Colab](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1-cheminformatics-data-engineering/02-text-patterns-and-numbers/notebook.ipynb) and run the first cell, which installs everything it needs.

**On your own computer (Windows, macOS or Linux):** with [uv](https://docs.astral.sh/uv/) installed,

```bash
git clone https://github.com/David-Alobo/monstrous-learn.git
cd monstrous-learn/data-engineering/series-1-cheminformatics-data-engineering
uv sync
uv run python 02-text-patterns-and-numbers/code.py
```

or with pip only, in any Python 3.11+ environment: `python -m pip install rdkit pandas`.

*This README, the notebook and `code.py` are made from `lesson.md` by `lessonkit.py --export`; edit the lesson, not them.*
