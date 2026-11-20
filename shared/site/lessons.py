"""Turn a module's lesson.md into the body of its page on the course site.

A lesson is Markdown with a short front matter (title, summary), fenced ```python blocks, ```output
blocks (what the code prints, kept honest by each series' lessonkit), figures written as
![caption](figures/name.svg), tables and a "Further reading" section. Code is coloured by Pygments;
outputs are shown as plain text under an "Output" label; each figure gets its caption.
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

STYLE = "github-dark"
OUTPUT = re.compile(r"```(output varies|output)\n(.*?)```\n", re.S)
FIGURE = re.compile(r'<p><img alt="([^"]*)" src="([^"]+)" ?/?></p>')


def folder(series_folder: str, number: int) -> Path | None:
    """The folder of a module that has a lesson, or None while it is still to be written.

    Args:
        series_folder: The series' folder in the repository.
        number: The module's number.

    Returns:
        The module's folder (NN-…), if it holds a lesson.md.
    """
    found = sorted(Path(series_folder).glob(f"{number:02d}-*/lesson.md"))
    return found[0].parent if found else None


def front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split a lesson into its front matter and its Markdown.

    Args:
        text: The lesson file's text.

    Returns:
        The front matter (title, summary) and the rest of the text.
    """
    if not text.startswith("---\n"):
        return {}, text
    head, body = text[4:].split("\n---\n", 1)
    meta = dict(line.split(": ", 1) for line in head.splitlines() if ": " in line)
    return meta, body


def render(text: str) -> tuple[dict[str, str], str, list[tuple[str, str]]]:
    """A lesson as HTML, with its front matter and its table of contents.

    Args:
        text: The lesson file's text.

    Returns:
        The front matter, the HTML body, and the (anchor, heading) of each section.
    """
    meta, body = front_matter(text)

    # outputs become plain blocks under a label, before Markdown sees them; an output that changes
    # from run to run (timings, memory) is labelled as an example
    def output(m: re.Match) -> str:
        label = "Example output: yours will differ" if m.group(1) == "output varies" else "Output"
        return (
            f'\n<div class="output"><span>{label}</span><pre>{escape(m.group(2))}</pre></div>\n\n'
        )

    body = OUTPUT.sub(output, body)
    md = markdown.Markdown(
        extensions=["fenced_code", "codehilite", "tables", "toc", "sane_lists"],
        extension_configs={"codehilite": {"css_class": "hl", "guess_lang": False}},
    )
    html = md.convert(body)
    html = FIGURE.sub(
        lambda m: (
            f'<figure><img alt="{m.group(1)}" src="{m.group(2)}">'
            f"<figcaption>{m.group(1)}</figcaption></figure>"
        ),
        html,
    )
    toc = [(t["id"], t["name"]) for t in md.toc_tokens if t["level"] == 2]
    return meta, html, toc


def code_css() -> str:
    """The colours of the code blocks (Pygments, dark), scoped to the lessons.

    Returns:
        The stylesheet.
    """
    return HtmlFormatter(style=STYLE).get_style_defs(".lesson .hl")
