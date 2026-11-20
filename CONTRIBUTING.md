# Contributing

Thank you for helping make these courses better. The most useful contributions are:

- **Reporting an error** in a lesson: a wrong statement, a broken example, a confusing sentence.
  Open an issue with the "Error in a lesson" template, or write to
  [contact@monstrous.com.ng](mailto:contact@monstrous.com.ng).
- **Suggesting an improvement**: a clearer explanation, a better example, a missing topic. Use the
  "Suggestion" template.
- **Fixing something yourself**: open a pull request (see below).

Questions about the course material are best asked in the Discord community, where other learners
can help and benefit from the answer.

## How the lessons are built

Each module lives in `<track>/<series>/NN-name/`:

- `lesson.md`: the lesson. Every ```` ```python ```` block may be followed by an ```` ```output ````
  block showing what it prints.
- `figures.py` and `figures/`: the figures, drawn from the same molecules as the code.
- `homework.md`: the homework questions (answers are not kept in this repository).

The rule that keeps the lessons trustworthy: **every output shown in a lesson is what its code really
prints**. The tests run every code block and compare. If you change code in a lesson, refresh the
outputs and run the tests:

```bash
cd data-engineering/series-1-cheminformatics-data-engineering
uv sync
uv run python lessonkit.py 01-graphs-and-matrices --write   # refresh the outputs
uv run pytest                                               # every lesson, every output
```

And for the course site (from the repository root):

```bash
uv sync
uv run pytest
uv run python -m shared.site.build
```

## Pull requests

- Keep each pull request to one change, and say why it is needed.
- Every lesson must still pass its tests; the automatic checks run on every pull request.
- Every reference in "Further reading" must be real and checked (a DOI that resolves, or a page that
  exists).
- Lessons use plain, precise English and British spelling. Claims must be supported by the code or
  a reference.
- By contributing, you agree that your code is released under the MIT licence and your lesson text
  under CC BY 4.0, as described in `LICENSE` and `LICENSE-content`.

Everyone taking part agrees to follow the [code of conduct](CODE_OF_CONDUCT.md).
