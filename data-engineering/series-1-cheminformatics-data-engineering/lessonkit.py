"""Run a lesson's code and keep its printed outputs honest.

A lesson (NN-…/lesson.md) is Markdown in which every ```python block may be followed directly by an
```output block: what that code prints. The blocks run in order, in one namespace, from the module's
folder, exactly as a learner would run them. The tests compare every output block with what the code
really prints, so a lesson can never show a result its code does not give.

Usage (from the series folder):
    uv run python lessonkit.py 01-graphs-and-matrices           # check
    uv run python lessonkit.py 01-graphs-and-matrices --write   # rewrite the output blocks
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import sys
from pathlib import Path

FENCE = re.compile(r"```(python|output)\n(.*?)```\n", re.S)


def blocks(text: str) -> list[tuple[str, str, int, int]]:
    """The fenced python and output blocks of a lesson, in order.

    Args:
        text: The lesson's Markdown.

    Returns:
        For each block: its kind, its body, and where it starts and ends in the text.
    """
    return [(m.group(1), m.group(2), m.start(), m.end()) for m in FENCE.finditer(text)]


def run(text: str, folder: Path) -> list[tuple[str, str | None]]:
    """Run every python block in order and capture what each prints.

    Args:
        text: The lesson's Markdown.
        folder: The module's folder, the working directory while the code runs.

    Returns:
        For each python block: what it printed, and the output block shown after it (or None).
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
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                exec(compile(body, f"{folder.name}/lesson.md block {i + 1}", "exec"), namespace)
            nxt = found[i + 1] if i + 1 < len(found) else None
            shown = nxt[1] if nxt and nxt[0] == "output" and nxt[2] == end else None
            results.append((out.getvalue(), shown))
    finally:
        os.chdir(here)
    return results


def write(path: Path) -> None:
    """Rewrite a lesson's output blocks with what its code prints now.

    Args:
        path: The lesson file.
    """
    text = path.read_text(encoding="utf-8")
    printed = iter(r[0] for r in run(text, path.parent))
    parts, last = [], 0
    for kind, _body, _start, end in blocks(text):
        if kind == "python":
            parts.append(text[last:end])
            out = next(printed)
            following = text[end:]
            if following.startswith("```output\n"):
                # replace the existing output block
                close = following.index("```\n", len("```output\n")) + 4
                last = end + close
            else:
                last = end
            if out:
                parts.append(f"```output\n{out}```\n")
    parts.append(text[last:])
    path.write_text("".join(parts), encoding="utf-8", newline="\n")


def main() -> None:
    """Check a module's lesson, or rewrite its outputs with --write."""
    path = Path(sys.argv[1]) / "lesson.md"
    if "--write" in sys.argv:
        write(path)
        print(f"rewrote the outputs in {path}")
        return
    bad = [i for i, (out, shown) in enumerate(run(path.read_text(encoding="utf-8"), path.parent))
           if shown is not None and out != shown]  # fmt: skip
    print(f"{path}: {'all outputs match' if not bad else f'outputs differ in blocks {bad}'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
