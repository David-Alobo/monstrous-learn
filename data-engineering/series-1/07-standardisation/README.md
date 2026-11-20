# Standardisation as a tested transformation

One canonical form per compound, made by one pure, versioned function (clean up, choose the parent, neutralise, optionally choose one tautomer) and tested like any other software.

- **Read the lesson:** [https://monstrous.com.ng/learn/data-engineering/series-1/07-standardisation/](https://monstrous.com.ng/learn/data-engineering/series-1/07-standardisation/)
- **Run it as a notebook:** [`notebook.ipynb`](notebook.ipynb)
- **The code on its own:** [`code.py`](code.py)
- **Homework:** [`homework.md`](homework.md)
- **The lesson's source:** [`lesson.md`](lesson.md); every output in it is checked by the tests

## Get set up

**In the browser, on any device:** [open this lesson as a notebook in Google Colab](https://colab.research.google.com/github/David-Alobo/monstrous-learn/blob/main/data-engineering/series-1/07-standardisation/notebook.ipynb) and run the first cell, which installs everything it needs.

**On your own computer (Windows, macOS or Linux):** with [uv](https://docs.astral.sh/uv/) installed,

```bash
git clone https://github.com/David-Alobo/monstrous-learn.git
cd monstrous-learn/data-engineering/series-1
uv sync
uv run python 07-standardisation/code.py
```

or with pip only, in any Python 3.11+ environment: `python -m pip install rdkit pandas pyarrow`.

*On Windows*, clone into a short folder (for example `C:\code`): Windows limits paths to 260 characters unless [long paths are enabled](https://learn.microsoft.com/windows/win32/fileio/maximum-file-path-limitation), and some packages install deep inside the environment.

*This README, the notebook and `code.py` are made from `lesson.md` by `lessonkit.py --export`; edit the lesson, not them.*
