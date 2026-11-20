"""Run a lesson's code, keep its printed outputs honest, and export it as a notebook and a script.

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
import os
import re
import sys
from pathlib import Path

FENCE = re.compile(r"```(python|output varies|output)\n(.*?)```\n", re.S)
NEEDS = re.compile(r"\A# needs: (\w+)")
SERVICE_ENV = {"postgres": "DATABASE_URL", "neo4j": "NEO4J_URI"}
REPO = "David-Alobo/monstrous-learn"
SITE = "https://monstrous.com.ng/learn/data-engineering/series-1"
SERIES_PATH = "data-engineering/series-1"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/{SERIES_PATH}"


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
    namespace: dict = {"__name__": "__lesson__"}
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
            with contextlib.redirect_stdout(out):
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


def setup_lines(meta: dict[str, str], folder: str) -> list[str]:
    """A lesson's setup guide, in Markdown (for the notebook, the module README and the page).

    Args:
        meta: The lesson's front matter.
        folder: The module's folder name.

    Returns:
        The guide's lines.
    """
    pkgs = " ".join(listed(meta, "requires"))
    colab = (
        f"https://colab.research.google.com/github/{REPO}/blob/main/{SERIES_PATH}/{folder}"
        "/notebook.ipynb"
    )
    lines = [
        "## Get set up",
        "",
        "**In the browser, on any device:** [open this lesson as a notebook in Google Colab]"
        f"({colab})"
        " and run the first cell, which installs everything it needs.",
        "",
        "**On your own computer (Windows, macOS or Linux):** with"
        " [uv](https://docs.astral.sh/uv/) installed,",
        "",
        "```bash",
        f"git clone https://github.com/{REPO}.git",
        f"cd monstrous-learn/{SERIES_PATH}",
        "uv sync",
        f"uv run python {folder}/code.py",
        "```",
        "",
        f"or with pip only, in any Python 3.11+ environment: `python -m pip install {pkgs}`.",
        "",
        "*On Windows*, clone into a short folder (for example `C:\code`): Windows limits paths to"
        " 260 characters unless [long paths are enabled]"
        "(https://learn.microsoft.com/windows/win32/fileio/maximum-file-path-limitation), and"
        " some packages install deep inside the environment.",
    ]
    services = listed(meta, "services")
    if services:
        lines += [
            "",
            f"**This lesson also needs {' and '.join(services)}**, which runs in Docker on any"
            " computer (Docker Desktop on Windows and macOS). From the repository's root:",
            "",
            "```bash",
            f"docker compose -f shared/docker/compose.yml up -d {' '.join(services)}",
            "```",
        ]
    return lines


def helpers(folder: Path, body: str) -> list[tuple[str, str]]:
    """The repository's own Python files a lesson imports, with where to download each.

    Args:
        folder: The module's folder.
        body: The lesson's Markdown.

    Returns:
        (module name, download address) for each: the series' helpers (e.g. chemlib) and the
        module's own files (e.g. workers.py), in that order.
    """
    imported = set(re.findall(r"^\s*(?:from|import) (\w+)", body, re.M))
    tools = ("lessonkit", "figurekit")  # the course's own tooling, not lesson code
    series = [(n, f"{RAW}/{n}.py") for n in sorted(imported)
              if (folder.parent / f"{n}.py").exists() and n not in tools]  # fmt: skip
    own = [(n, f"{RAW}/{folder.name}/{n}.py") for n in sorted(imported)
           if (folder / f"{n}.py").exists() and n not in ("code", "figures")]  # fmt: skip
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
    page = f"{SITE}/{folder.name}/"

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
    if local:
        install += "\n\nimport pathlib\nimport urllib.request\n"
        for name, url in local:
            install += (
                f'if not pathlib.Path("{name}.py").exists():\n'
                f'    urllib.request.urlretrieve("{url}", "{name}.py")\n'
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
        text = re.sub(r"\]\((figures/[^)]+)\)", lambda m: f"]({RAW}/{folder.name}/{m.group(1)})",
                      body[last:start])  # fmt: skip
        if text.strip():
            cells.append(md_cell(text))
        nxt = found[i + 1] if i + 1 < len(found) else None
        follows = nxt is not None and nxt[0] != "python" and nxt[2] == end
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
        *setup_lines(meta, folder.name),
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
