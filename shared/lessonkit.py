"""Run a lesson's code, keep its printed outputs honest, and export it as a notebook and a script.

Shared by every series: each series folder holds a small lessonkit.py that loads this file, and
everything that depends on the series (its site address, its GitHub folder) is worked out from
the module folder being run.

A lesson (NN-…/lesson.md) is Markdown with a front matter:

    ---
    title: …
    summary: …
    requires: rdkit, networkx, numpy, pandas      (the pip packages its code imports)
    services: postgres                             (optional: postgres, neo4j)
    ---

Every ```python block may be followed directly by an ```output block, what that code prints. The
blocks run in order, in one namespace, from the module's folder, exactly as a learner would run
them, and the tests compare every output block with what the code really prints. Two exceptions,
both visible to the reader:

- ```output varies``` marks an output that legitimately changes from run to run (timings, memory):
  the code must still run, but the output is not compared, and the page labels it as an example.
- a block whose first line is ``# needs: postgres`` (or neo4j) runs only when that service is
  available (DATABASE_URL or NEO4J_URI is set); otherwise it is skipped, and the tests say so.

Usage (from the series folder):
    uv run python lessonkit.py 01-graphs-and-matrices            # check the outputs
    uv run python lessonkit.py 01-graphs-and-matrices --write    # rewrite the outputs
    uv run python lessonkit.py 01-graphs-and-matrices --export   # notebook, code.py, README
"""

from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import re
import sys
import types
from pathlib import Path

FENCE = re.compile(r"```(python|output varies|output)\n(.*?)```\n", re.S)
NEEDS = re.compile(r"\A# needs: (\w+)")
SERVICE_ENV = {"postgres": "DATABASE_URL", "neo4j": "NEO4J_URI"}
SERVICE_NAME = {"postgres": "PostgreSQL", "neo4j": "Neo4j"}  # as the reader knows them
REPO = "David-Alobo/monstrous-learn"
REPO_ROOT = Path(__file__).resolve().parents[1]
START = "https://monstrous.com.ng/learn/start/"  # the course's "Start here" page
DOCKER_GUIDE = "https://monstrous.com.ng/learn/databases/"  # the database guide, as a page


def series_of(folder: Path) -> str:
    """The series a module belongs to, as its folder in the repository.

    Args:
        folder: The module's folder (e.g. data-engineering/series-1/01-graphs-and-matrices).

    Returns:
        The series' folder relative to the repository, e.g. "data-engineering/series-1".
    """
    return Path(folder).resolve().parent.relative_to(REPO_ROOT).as_posix()


def site_of(series: str) -> str:
    """The address of a series on the course site.

    Args:
        series: The series' folder in the repository.

    Returns:
        The address, e.g. "https://monstrous.com.ng/learn/data-engineering/series-1".
    """
    return f"https://monstrous.com.ng/learn/{series}"


def raw_of(series: str) -> str:
    """Where a series' files can be downloaded from GitHub (for Colab).

    Args:
        series: The series' folder in the repository.

    Returns:
        The address of the series' folder on raw.githubusercontent.com.
    """
    return f"https://raw.githubusercontent.com/{REPO}/main/{series}"


def front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split a lesson into its front matter and its Markdown.

    Args:
        text: The lesson file's text.

    Returns:
        The front matter and the rest of the text.
    """
    if not text.startswith("---\n"):
        return {}, text
    head, body = text[4:].split("\n---\n", 1)
    return dict(line.split(": ", 1) for line in head.splitlines() if ": " in line), body


def listed(meta: dict[str, str], key: str) -> list[str]:
    """A comma-separated front matter entry as a list (packages, services).

    Args:
        meta: The lesson's front matter.
        key: The entry, e.g. "requires".

    Returns:
        Its items.
    """
    return [p.strip() for p in meta.get(key, "").split(",") if p.strip()]


def blocks(text: str) -> list[tuple[str, str, int, int]]:
    """The fenced python and output blocks of a lesson, in order.

    Args:
        text: The lesson's Markdown.

    Returns:
        For each block: its kind, its body, and where it starts and ends in the text.
    """
    return [(m.group(1), m.group(2), m.start(), m.end()) for m in FENCE.finditer(text)]


def available(service: str) -> bool:
    """Whether a service a block needs is configured.

    Args:
        service: "postgres" or "neo4j".

    Returns:
        True if its address is set in the environment.
    """
    return bool(os.environ.get(SERVICE_ENV.get(service, ""), ""))


def _screen_handlers() -> list[logging.StreamHandler]:
    """Find every logging handler that writes to the screen (not to a file).

    Returns:
        The stream handlers of the root logger and of every named logger, without file handlers.
    """
    loggers = [logging.getLogger()] + [
        lg for lg in logging.Logger.manager.loggerDict.values() if isinstance(lg, logging.Logger)
    ]
    return [
        h
        for lg in loggers
        for h in lg.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    ]


@contextlib.contextmanager
def _capture(out: io.StringIO):
    """Send what a block prints, and what it logs to the screen, to one buffer.

    Lessons log with the standard `logging` module (a handler set up in their Setup block, writing
    to the screen); this points those handlers at the buffer while a block runs, so log lines are
    checked like printed ones, and puts them back afterwards.

    Args:
        out: The buffer to collect the block's output in.
    """
    handlers = _screen_handlers()
    before = [h.stream for h in handlers]
    for h in handlers:
        h.setStream(out)
    try:
        with contextlib.redirect_stdout(out):
            yield
    finally:
        for h, stream in zip(handlers, before, strict=True):
            h.setStream(stream)


def run(text: str, folder: Path) -> list[tuple[str | None, str | None, str]]:
    """Run every python block in order and capture what each prints.

    Args:
        text: The lesson's Markdown.
        folder: The module's folder, the working directory while the code runs.

    Returns:
        For each python block: what it printed (None if skipped), the output block shown after it
        (or None), and that block's kind ("output", "output varies", or "" if there is none).
    """
    found = blocks(text)
    # the lesson runs as a real module, registered like any imported one, so that code which looks
    # itself up (dataclasses, pickling for worker processes) works as it does in a script
    module = types.ModuleType("__lesson__")
    sys.modules["__lesson__"] = module
    namespace = module.__dict__
    # the same import path a learner's code.py sets up: the course's helpers (chemlib, in the
    # series folder) and the module's own files (e.g. workers.py)
    for path in (folder.resolve().parent, folder.resolve()):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    results = []
    here = os.getcwd()
    os.chdir(folder)
    try:
        for i, (kind, body, _, end) in enumerate(found):
            if kind != "python":
                continue
            nxt = found[i + 1] if i + 1 < len(found) else None
            follows = nxt is not None and nxt[0] != "python" and nxt[2] == end
            shown, shown_kind = (nxt[1], nxt[0]) if follows else (None, "")
            need = NEEDS.match(body)
            if need and not available(need.group(1)):
                results.append((None, shown, shown_kind))
                continue
            out = io.StringIO()
            with _capture(out):
                # dont_inherit: lesson code must not inherit this file's `from __future__`
                # imports (they would turn type hints into strings, which breaks Pydantic models)
                name = f"{folder.name}/lesson.md block {i + 1}"
                exec(compile(body, name, "exec", dont_inherit=True), namespace)
            results.append((out.getvalue(), shown, shown_kind))
    finally:
        os.chdir(here)
    return results


def write(path: Path) -> None:
    """Rewrite a lesson's output blocks with what its code prints now (skipped blocks keep theirs).

    Args:
        path: The lesson file.
    """
    text = path.read_text(encoding="utf-8")
    printed = iter(run(text, path.parent))
    parts, last = [], 0
    for kind, _body, _start, end in blocks(text):
        if kind != "python":
            continue
        parts.append(text[last:end])
        out, _shown, shown_kind = next(printed)
        if out is None:  # skipped (its service is not running): keep the output it shows
            last = end
            continue
        old = re.match(r"```(output varies|output)\n.*?```\n", text[end:], re.S)
        last = end + (old.end() if old else 0)
        if out:
            parts.append(f"```{shown_kind or 'output'}\n{out}```\n")
    parts.append(text[last:])
    path.write_text("".join(parts), encoding="utf-8", newline="\n")


def setup_lines(meta: dict[str, str], folder: str, series: str) -> list[str]:
    """A lesson's setup guide, in Markdown (for the notebook, the module README and the page).

    Args:
        meta: The lesson's front matter.
        folder: The module's folder name.
        series: The series' folder in the repository, e.g. "data-engineering/series-1".

    Returns:
        The guide's lines.
    """
    pkgs = " ".join(listed(meta, "requires"))
    colab = (
        f"https://colab.research.google.com/github/{REPO}/blob/main/{series}/{folder}"
        "/notebook.ipynb"
    )
    lines = [
        "## Get set up",
        "",
        "You can read this page without running anything. To run the code yourself, the easiest"
        " way needs nothing installed, only a web browser and a free Google account:",
        "",
        f"1. [Open this lesson in Google Colab]({colab}). Colab is Google's free service for"
        " running Python notebooks in the browser; sign in with your Google account if asked.",
        "2. Run the cells in order, from the top: click the ▶ button at the left of a cell, or"
        " click inside it and press Shift+Enter. The first cell installs what the lesson needs"
        " and takes a minute or two.",
        '3. If Colab warns "This notebook was not authored by Google", click **Run anyway**: the'
        " notebook comes from this course's own repository.",
        "4. Under each cell you should see what the box labelled **Output** under the same code"
        " on the lesson's page shows (the notebook opens with our outputs already in place;"
        " running a cell replaces them with yours). Boxes labelled **Example output** show"
        " timings or memory, so your numbers will differ a little.",
        "",
        f"New to notebooks, or want to run the lessons on your own computer instead (with"
        f" Jupyter, Anaconda or a terminal)? [Start here]({START}) shows every step.",
        "",
        "If you already work in a terminal, the short version, with"
        " [uv](https://docs.astral.sh/uv/) and Git installed:",
        "",
        "```bash",
        f"git clone https://github.com/{REPO}.git",
        f"cd monstrous-learn/{series}",
        "uv sync",
        f"uv run python {folder}/code.py",
        "```",
        "",
        f"or, in any Python 3.11+ environment: `python -m pip install {pkgs}`.",
    ]
    services = listed(meta, "services")
    if services:
        lines += [
            "",
            f"**This lesson also needs {' and '.join(SERVICE_NAME.get(s, s) for s in services)}**,"
            " a database that runs in Docker"
            f" on your own computer (Colab cannot run it; the rest of the lesson runs there)."
            f" [The database guide]({DOCKER_GUIDE}) shows how to install Docker and start it,"
            " step by step.",
        ]
    return lines


def helpers(folder: Path, body: str) -> list[tuple[str, str]]:
    """The repository's own Python files a lesson imports, with where to download each.

    Args:
        folder: The module's folder.
        body: The lesson's Markdown.

    Returns:
        (module name, download address) for each: the series' helpers (e.g. chemlib) and the
        module's own files (e.g. workers.py), in that order. Helpers imported by other helpers
        (labdata imports chemlib) are included, and a helper that is a stub loading a file from
        shared/ is downloaded from shared/ itself, under the helper's name.
    """
    raw = raw_of(series_of(folder))
    tools = ("lessonkit", "figurekit")  # the course's own tooling, not lesson code

    def imports_in(text: str) -> set[str]:
        """The top-level module names a piece of code imports.

        Args:
            text: Python code, or a lesson's Markdown.

        Returns:
            The names.
        """
        return set(re.findall(r"^\s*(?:from|import) (\w+)", text, re.M))

    def source(name: str) -> tuple[str, Path] | None:
        """Where a helper of this series or module is downloaded from, and its file here.

        Args:
            name: The module name.

        Returns:
            (download address, local file), or None if it is not one of the course's files.
        """
        if name in tools:
            return None
        if (folder / f"{name}.py").exists() and name not in ("code", "figures"):
            return f"{raw}/{folder.name}/{name}.py", folder / f"{name}.py"
        path = folder.parent / f"{name}.py"
        if not path.exists():
            return None
        shared = re.search(r'_SHARED = .*"shared" / "(\w+\.py)"', path.read_text(encoding="utf-8"))
        if shared:
            return f"{raw_of('shared')}/{shared.group(1)}", REPO_ROOT / "shared" / shared.group(1)
        return f"{raw}/{name}.py", path

    found: dict[str, tuple[str, Path]] = {}
    todo = sorted(imports_in(body))
    while todo:
        name = todo.pop(0)
        where = source(name)
        if where is None or name in found:
            continue
        found[name] = where
        todo += sorted(imports_in(where[1].read_text(encoding="utf-8")) - set(found))
    series = [
        (n, url)
        for n, (url, _) in sorted(found.items())
        if not url.startswith(f"{raw}/{folder.name}/")
    ]
    own = [
        (n, url) for n, (url, _) in sorted(found.items()) if url.startswith(f"{raw}/{folder.name}/")
    ]
    return series + own


def export(folder: Path) -> dict[Path, str]:
    """The notebook, the script and the README of a module, made from its lesson.

    Args:
        folder: The module's folder.

    Returns:
        Each file's path and contents.
    """
    meta, body = front_matter((folder / "lesson.md").read_text(encoding="utf-8"))
    title = meta.get("title", folder.name)
    summary = meta.get("summary", "")
    series = series_of(folder)
    raw = raw_of(series)
    page = f"{site_of(series)}/{folder.name}/"

    def md_cell(text: str) -> dict:
        return {
            "cell_type": "markdown",
            "metadata": {},
            "source": text.strip("\n").splitlines(True),
        }

    def code_cell(code: str, output: str | None) -> dict:
        outputs = []
        if output:
            outputs = [{"output_type": "stream", "name": "stdout", "text": output.splitlines(True)}]
        return {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": outputs,
            "source": code.rstrip("\n").splitlines(True),
        }

    install = "# Install what this lesson needs (in Colab, or any fresh environment)\n"
    install += f"%pip install -q {' '.join(listed(meta, 'requires'))}"
    # the course's own helpers (chemlib) and this module's (e.g. workers.py) come with the
    # repository; outside it (in Colab), fetch them
    local = helpers(folder, body)
    # data files the lesson reads (front matter "files:"): from its folder (recorded/*.json), or
    # from the series folder when the pattern starts with ../ (../stages/after-04/**/*); each is
    # downloaded to the same path relative to the folder it came from, next to the helpers
    data = []
    for pattern in listed(meta, "files"):
        shared = pattern.startswith("../")
        base = folder.parent if shared else folder
        for p in base.glob(pattern[3:] if shared else pattern):
            if p.is_file() and "__pycache__" not in p.parts:
                rel = p.relative_to(base).as_posix()
                data.append((rel, f"{raw}/{rel}" if shared else f"{raw}/{folder.name}/{rel}"))
    data.sort()
    services = listed(meta, "services")
    if services:
        # a cell that needs a database starts with %%needs: it runs where the database is set up
        # (on your own computer) and is skipped elsewhere (in Colab), so the rest still runs
        where = ", ".join(f"{s!r}: {SERVICE_ENV[s]!r}" for s in services)
        install += (
            "\n\n# Cells that start with %%needs use a database. They run only where it is set"
            " up (see\n# the database guide); elsewhere, such as in Colab, they are skipped and"
            " the rest of the\n# lesson still runs. Their outputs are on the lesson's page.\n"
            "import os\n"
            "from IPython.core.magic import register_cell_magic\n\n\n"
            "@register_cell_magic\n"
            "def needs(service, cell):\n"
            '    """Run this cell only if the database it needs is set up."""\n'
            f"    variable = {{{where}}}[service.strip()]\n"
            "    if os.environ.get(variable):\n"
            "        get_ipython().run_cell(cell)\n"
            "    else:\n"
            '        print(f"Skipped: this cell needs {service.strip()}, which is not set up'
            ' here."\n'
            '              " Its output is shown on the lesson\'s page.")\n'
        )
    if local or data:
        install += "\n\nimport pathlib\nimport urllib.request\n"
        for name, url in local:
            install += (
                f'if not pathlib.Path("{name}.py").exists():\n'
                f'    urllib.request.urlretrieve("{url}", "{name}.py")\n'
            )
        for rel, url in data:
            install += (
                f'if not pathlib.Path("{rel}").exists():\n'
                f'    pathlib.Path("{rel}").parent.mkdir(parents=True, exist_ok=True)\n'
                f'    urllib.request.urlretrieve("{url}", "{rel}")\n'
            )
    cells = [
        md_cell(f"# {title}\n\n{summary}\n\nThe lesson's page: {page}"),
        code_cell(install, None),
    ]
    found = blocks(body)
    last = 0
    for i, (kind, code, start, end) in enumerate(found):
        if kind != "python":
            continue
        # figures point at their copy on GitHub, so the notebook shows them anywhere
        text = re.sub(r"\]\((figures/[^)]+)\)", lambda m: f"]({raw}/{folder.name}/{m.group(1)})",
                      body[last:start])  # fmt: skip
        if text.strip():
            cells.append(md_cell(text))
        nxt = found[i + 1] if i + 1 < len(found) else None
        follows = nxt is not None and nxt[0] != "python" and nxt[2] == end
        need = NEEDS.match(code)
        if need:  # skipped in a notebook where its database is not set up (see the first cell)
            code = f"%%needs {need.group(1)}\n{code}"
        cells.append(code_cell(code, nxt[1] if follows else None))
        last = nxt[3] if follows else end
    if body[last:].strip():
        cells.append(md_cell(body[last:]))
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    script = [
        f'"""{title}: the code of the lesson, in order.\n\n{summary}\n\nLesson: {page}\n'
        f"Run it from anywhere, e.g. from the series folder: uv run python {folder.name}/code.py\n"
        '"""\n\n'
        "import os as _os\nimport sys as _sys\nfrom pathlib import Path as _Path\n\n"
        "# run as the lesson does: in this module's folder (for work/ and figures/), with the\n"
        "# course's helpers (chemlib, in the series folder) and this module's own importable\n"
        "_HERE = _Path(__file__).resolve().parent\n"
        "_os.chdir(_HERE)\n"
        "_sys.path[:0] = [str(_HERE), str(_HERE.parent)]\n"
    ]
    section = None
    for kind, code, start, _end in found:
        if kind != "python":
            continue
        headings = re.findall(r"^#{2,3} (.+)$", body[:start], re.M)
        if headings and headings[-1] != section:
            section = headings[-1]
            script.append(f"\n# ---- {section} ----\n")
        script.append(code.rstrip("\n") + "\n")

    readme = [
        f"# {title}",
        "",
        summary,
        "",
        f"- **Read the lesson:** [{page}]({page})",
        "- **Run it as a notebook:** [`notebook.ipynb`](notebook.ipynb)",
        "- **The code on its own:** [`code.py`](code.py)",
        "- **Homework:** [`homework.md`](homework.md)",
        "- **The lesson's source:** [`lesson.md`](lesson.md); every output in it is checked by the"
        " tests",
        "",
        *setup_lines(meta, folder.name, series),
        "",
        "*This README, the notebook and `code.py` are made from `lesson.md` by"
        " `lessonkit.py --export`; edit the lesson, not them.*",
    ]
    return {
        folder / "notebook.ipynb": json.dumps(notebook, indent=1, ensure_ascii=False) + "\n",
        folder / "code.py": "".join(script),
        folder / "README.md": "\n".join(readme) + "\n",
    }


def main() -> None:
    """Check a module's lesson, rewrite its outputs (--write) or export it (--export)."""
    folder = Path(sys.argv[1])
    path = folder / "lesson.md"
    if "--write" in sys.argv:
        write(path)
        print(f"rewrote the outputs in {path}")
        return
    if "--export" in sys.argv:
        for target, content in export(folder).items():
            target.write_text(content, encoding="utf-8", newline="\n")
            print(f"wrote {target}")
        return
    results = run(path.read_text(encoding="utf-8"), folder)
    bad = [k for k, (out, shown, kind) in enumerate(results, start=1)
           if out is not None and kind == "output" and out != shown]  # fmt: skip
    skipped = sum(out is None for out, _, _ in results)
    note = f" ({skipped} blocks skipped: their service is not running)" if skipped else ""
    print(f"{path}: {'all outputs match' if not bad else f'outputs differ in blocks {bad}'}{note}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
