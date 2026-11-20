"""Build the course pages for monstrous.com.ng/learn/ from the catalogue.

Usage (from the repository root):
    uv run python -m shared.site.build          # writes dist/learn/
    uv run python -m shared.site.build --zip    # and dist/learn.zip (unpack as public_html/learn/)

The courses are grouped in tracks (Data Engineering for Chemistry first; MLOps for Chemists and
Agentic AI in Chemistry later), each with its series. Every page is made from catalogue.json and
templates/frame.html (the website's own header and footer, and a bar linking every track), so a
new track or course is one entry in the catalogue. Pages: /learn/ (all tracks), /learn/<track>/ and
/learn/<track>/<series>/. The pages are static files, hosted beside WordPress like the 2027 by the
Numbers articles. The stylesheet's address carries a hash of its contents, so Cloudflare's cache
never serves an old one after an update. The builder also writes each track's and series' README
from the catalogue, so the two never disagree.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import zipfile
from html import escape
from pathlib import Path

from . import lessons


def setup_html(series_folder: str, meta: dict, folder: str) -> str:
    """A lesson's "Get set up" box, from its series' own lessonkit (the same text as the notebook
    and the module README), with download links to the notebook and the code beside the page.

    Args:
        series_folder: The series' folder, which holds its lessonkit.py.
        meta: The lesson's front matter.
        folder: The module's folder name.

    Returns:
        The box's HTML.
    """
    spec = importlib.util.spec_from_file_location("lessonkit", Path(series_folder, "lessonkit.py"))
    kit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kit)
    lines = kit.setup_lines(meta, folder)[1:]  # without its own heading
    body = lessons.markdown.markdown(
        "\n".join(lines),
        extensions=["fenced_code", "codehilite"],
        extension_configs={"codehilite": {"css_class": "hl"}},
    )
    return (
        '<section class="setup" id="get-set-up"><h2>Get set up</h2>'
        f"{body}"
        '<p class="downloads"><a class="btn ghost" href="notebook.ipynb" download>'
        "Download the notebook</a>"
        '<a class="btn ghost" href="code.py" download>Download the code</a></p></section>'
    )


HERE = Path(__file__).parent
CATALOGUE = HERE / "catalogue.json"
FRAME = HERE / "templates" / "frame.html"
STATIC = HERE / "static"
DIST = Path("dist")
WAITLIST = "mailto:contact@monstrous.com.ng?subject=Waitlist%3A%20Learn%20with%20Monstrous%20Data"
ICONS = {
    "read": '<path d="M4 5a2 2 0 012-2h12v16H6a2 2 0 00-2 2zM4 21V5M8 7h6M8 11h6"/>',
    "run": '<path d="M4 4h16v12H4zM8 20h8M12 16v4M8 9l2 2-2 2M12 13h4"/>',
    "check": '<path d="M9 12l2 2 4-4M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/>',
    "team": '<path d="M8 7a3 3 0 106 0 3 3 0 00-6 0M3 21v-2a4 4 0 014-4h8a4 4 0 014 4v2"/>',
    "calendar": '<path d="M4 6h16v14H4zM4 10h16M8 3v4M16 3v4"/>',
    "task": '<path d="M9 5h10M9 12h10M9 19h10M4 5l1 1 2-2M4 12l1 1 2-2M4 19l1 1 2-2"/>',
    "chat": '<path d="M4 5h16v11H9l-5 4zM8 9h8M8 12h5"/>',
    "award": '<path d="M12 3a6 6 0 100 12 6 6 0 000-12zM8.5 14L7 21l5-3 5 3-1.5-7"/>',
    "data": (
        '<path d="M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8'
        ' 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>'
    ),
    "model": (
        '<path d="M5 6a2 2 0 104 0 2 2 0 00-4 0M15 6a2 2 0 104 0 2 2'
        ' 0 00-4 0M10 18a2 2 0 104 0 2 2 0 00-4 0M8 7.5l3 8.6M16 7.5l-3 8.6M9 6h6"/>'
    ),
    "agent": (
        '<path d="M12 2v3M8 5h8a3 3 0 013 3v7a3 3 0 01-3 3H8a3 3 0'
        ' 01-3-3V8a3 3 0 013-3zM9 11h.01M15 11h.01M9 15h6M2 11h3M19 11h3"/>'
    ),
}
TRACK_ICON = {"data-engineering": "data", "mlops": "model", "agentic-ai": "agent"}


def load(path: Path = CATALOGUE) -> dict:
    """The catalogue of tracks and courses.

    Args:
        path: The catalogue file.

    Returns:
        The parsed catalogue.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def url(cat: dict, track: dict, series: dict | None = None) -> str:
    """The address of a track's page, or of one of its series.

    Args:
        cat: The catalogue.
        track: The track.
        series: One of its series, or None for the track itself.

    Returns:
        The address, e.g. "/learn/data-engineering/series-1/".
    """
    tail = f"{series['slug']}/" if series else ""
    return f"{cat['base']}{track['slug']}/{tail}"


def icon(name: str) -> str:
    """An inline line icon.

    Args:
        name: One of the keys of ICONS.

    Returns:
        The SVG markup.
    """
    return f'<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def status_chip(item: dict) -> str:
    """The status of a track or course as a chip: when it opens, "Planned" or "Coming later".

    Args:
        item: A track or a course from the catalogue.

    Returns:
        The chip markup.
    """
    if item["status"] in ("Planned", "Coming later"):
        return f'<span class="chip planned">{escape(item["status"])}</span>'
    return f'<span class="chip status">Starts {escape(item["status"])}</span>'


def frame(cat: dict, path: str, title: str, description: str, body: str, current: str) -> str:
    """Put a page's body inside the website's header and footer and the courses' bar.

    Args:
        cat: The catalogue.
        path: The page's address on the site, e.g. "/learn/data-engineering/series-1/".
        title: The page title.
        description: The page description (search results and link previews).
        body: The page's main content.
        current: The address of the page shown, to mark its track in the bar.

    Returns:
        The whole page.
    """
    base = cat["base"]

    def link(href: str, label: str) -> str:
        # a track stays marked on its own page and on every course page inside it
        on = ' class="on"' if current.startswith(href) else ""
        return f'      <a{on} href="{href}">{label}</a>'

    links, foot = [], []
    for t in cat["tracks"]:
        links.append(link(url(cat, t), escape(t["title"])))
        foot.append(f'        <a href="{url(cat, t)}">{escape(t["title"])}</a>')
    page = FRAME.read_text(encoding="utf-8")
    for key, value in {
        "title": escape(title),
        "description": escape(description),
        "base": base,
        "path": path,
        "home_on": "on" if current == base else "",
        "course_links": "\n".join(links),
        "footer_links": "\n".join(foot),
        "body": body,
    }.items():
        page = page.replace("{{" + key + "}}", value)
    return page


def course_card(cat: dict, t: dict, s: dict) -> str:
    """One course as a card.

    Args:
        cat: The catalogue.
        t: The course's track.
        s: The course.

    Returns:
        The card markup.
    """
    return f"""      <a class="card course" href="{url(cat, t, s)}">
        <div class="row"><span class="num">{s["number"]}</span>{status_chip(s)}</div>
        <h3>{escape(s["title"])}</h3>
        <p>{escape(s["tagline"])}</p>
        <p class="small">{len(s["modules"])} modules · {escape(s["level"])}</p>
        <span class="go">View the course →</span>
      </a>"""


def track_card(cat: dict, t: dict) -> str:
    """One track as a card on the home page.

    Args:
        cat: The catalogue.
        t: The track.

    Returns:
        The card markup.
    """
    count = f"{len(t['series'])} series" if t["series"] else "Outline to follow"
    return f"""      <a class="card course track-card" href="{url(cat, t)}">
        <div class="row">{icon(TRACK_ICON.get(t["slug"], "read"))}{status_chip(t)}</div>
        <h3>{escape(t["title"])}</h3>
        <p>{escape(t["tagline"])}</p>
        <p class="small">{count}</p>
        <span class="go">View the track →</span>
      </a>"""


def how_and_cohort(cat: dict) -> str:
    """The sections every track shares: how the lessons work, and how a cohort runs.

    Args:
        cat: The catalogue.

    Returns:
        The two sections' markup.
    """
    cohort = cat["cohort"]
    unit = cohort["cadence"].removesuffix("ly")
    return f"""    <section class="wrap" id="how">
      <p class="eyebrow">How it works</p>
      <h2>Read, run, check</h2>
      <div class="grid">
        <div class="card">{icon("read")}<h3>Read</h3><p>Each module is one page: the problem,
          the idea, and the code, with diagrams where they help.</p></div>
        <div class="card">{icon("run")}<h3>Run, on any device</h3><p>Read on a phone, tablet or
          laptop. Code in the browser, with the whole setup (database included) running online, or
          on your own Windows, macOS or Linux computer. Nothing to buy.</p></div>
        <div class="card">{icon("check")}<h3>Check</h3><p>Every example is tested before it is
          published, and all the code is open: compare your results with ours.</p></div>
      </div>
    </section>

    <section class="wrap" id="cohort">
      <p class="eyebrow">Learn together</p>
      <h2>How the cohort works</h2>
      <p>Each course runs once as a group, starting on a set date, and then stays open to follow
        at your own pace.</p>
      <div class="grid four">
        <div class="card">{icon("calendar")}<h3>One module a {unit}</h3>
          <p>From the start, a new module every {unit}, so the group moves together.</p></div>
        <div class="card">{icon("task")}<h3>Homework</h3><p>A few questions per module, answered by
          running the code. The answers are published after each deadline.</p></div>
        <div class="card">{icon("chat")}<h3>{escape(cohort["community"])} community</h3><p>Ask
          questions, help others and share your progress. The invitation comes with the waitlist
          email.</p></div>
        <div class="card">{icon("award")}<h3>Certificate</h3><p>Finish the capstone during a cohort;
          three fellow learners review it, and a pass earns a certificate.</p></div>
      </div>
      <p class="note">Joining later? Every module stays open. Take the capstone with the next
        cohort to earn the certificate.</p>
    </section>
"""


def home(cat: dict) -> str:
    """The home page of all the courses: the tracks, the first courses, and how it all works.

    Args:
        cat: The catalogue.

    Returns:
        The page body.
    """
    first_track = cat["tracks"][0]
    first = first_track["series"][0]
    tracks = "\n".join(track_card(cat, t) for t in cat["tracks"])
    cards = "\n".join(course_card(cat, first_track, s) for s in first_track["series"])
    return f"""    <section class="wrap hero">
      <p class="eyebrow">Monstrous Data · Learn</p>
      <h1>{escape(cat["title"])}</h1>
      <p class="lede">Free, practical courses in data engineering and AI for chemists who know
        some Python, with code you can run and every example tested before it is published.
        We start with the data: databases, pipelines and checks you can trust. MLOps and
        agentic AI follow, each built on the one before.</p>
      <div class="meta"><span class="chip">Free</span><span class="chip">Any device</span>
        <span class="chip status">First course: {escape(cat["opens"])}</span></div>
      <div class="actions">
        <a class="btn primary" href="{url(cat, first_track, first)}">
          Start with {escape(first_track["short"])}, Series {first["number"]}</a>
        <a class="btn ghost" href="{WAITLIST}">Join the waitlist</a>
      </div>
    </section>

    <section class="wrap" id="tracks">
      <p class="eyebrow">Tracks</p>
      <h2>Choose a track</h2>
      <div class="grid">
{tracks}
      </div>
    </section>

    <section class="wrap" id="courses">
      <p class="eyebrow">{escape(first_track["title"])}</p>
      <h2>Start here</h2>
      <p>Series 1 comes first; the later series build on it.</p>
      <div class="grid">
{cards}
      </div>
    </section>

{how_and_cohort(cat)}
    <section class="wrap" id="who">
      <p class="eyebrow">Who it is for</p>
      <h2>Chemists who work with data</h2>
      <div class="grid">
        <div class="card"><h3>You will get most from it if you</h3><p>are a chemist, student or
          researcher who has written some Python (loops, functions, pandas) and wants your data to
          be organised, searchable and trustworthy.</p></div>
        <div class="card"><h3>You do not need</h3><p>a computer science degree, a server, or
          paid software. Everything used is open source, and every module runs in a browser
          or on an ordinary laptop.</p></div>
        <div class="card">{icon("team")}<h3>For teams</h3><p>Workshops for research groups and
          R&amp;D teams, and help with your own lab data.
          <a href="https://monstrous.com.ng/contact/">Discuss a project</a>.</p></div>
      </div>
    </section>
"""


def track_page(cat: dict, i: int) -> str:
    """A track's page: what it covers and its series, or a note that it is coming.

    Args:
        cat: The catalogue.
        i: The track's position in the catalogue.

    Returns:
        The page body.
    """
    t = cat["tracks"][i]
    if t["series"]:
        inner = f"""      <h2>Courses</h2>
      <div class="grid">
{chr(10).join(course_card(cat, t, s) for s in t["series"])}
      </div>"""
    else:
        inner = """      <div class="card soon"><h3>The outline is on its way</h3>
        <p>Join the waitlist to hear first when this track opens, and to help shape it: tell us
        what you would most
        like this track to cover.</p></div>"""
    others = "".join(
        f'<a href="{url(cat, o)}">{escape(o["title"])} →</a>' for o in cat["tracks"] if o is not t
    )
    return f"""    <section class="wrap hero">
      <p class="crumbs"><a href="{cat["base"]}">All courses</a> / {escape(t["short"])}</p>
      <p class="eyebrow">Track</p>
      <h1>{escape(t["title"])}</h1>
      <p class="lede">{escape(t["tagline"])}</p>
      <div class="meta">{status_chip(t)}<span class="chip">Free</span></div>
      <div class="actions"><a class="btn ghost" href="{WAITLIST}">Join the waitlist</a></div>
    </section>

    <section class="wrap">
      <p>{escape(t["summary"])}</p>
{inner}
      <nav class="next" aria-label="Other tracks">
        <a href="{cat["base"]}">← All courses</a>{others}</nav>
    </section>
"""


def course(cat: dict, i: int, k: int) -> str:
    """A course's page: what it covers, its modules, how to follow it, and the other courses.

    Args:
        cat: The catalogue.
        i: The track's position in the catalogue.
        k: The course's position in its track.

    Returns:
        The page body.
    """
    t = cat["tracks"][i]
    s = t["series"][k]
    planned = s["status"] == "Planned"
    mods = []
    part = None
    for m in s["modules"]:
        # a heading wherever the course moves to a new part (foundations, scale, ...)
        if m.get("part") and m["part"] != part:
            part = m["part"]
            mods.append(f'        <li class="part">{escape(part)}</li>')
        when = "Planned" if planned else (s["status"] if m["number"] == 1 else "To follow")
        tools = "".join(f'<span class="chip">{escape(x)}</span>' for x in m["tools"])
        lesson = lessons.folder(s["folder"], m["number"])
        title = escape(m["title"])
        if lesson:
            title = f'<a href="{url(cat, t, s)}{lesson.name}/">{title}</a>'
        read = (
            f'<a class="read" href="{url(cat, t, s)}{lesson.name}/">Read the lesson →</a>'
            if lesson
            else ""
        )
        mods.append(f"""        <li class="module{" ready" if lesson else ""}">
          <span class="mn">{m["number"]}</span>
          <div><h3>{title}</h3><p>{escape(m["what"])}</p>
            <div class="tools">{tools}</div>{read}</div>
          <span class="when">{escape(when)}</span>
        </li>""")
    tools = "".join(f"<li>{escape(x)}</li>" for x in s["tools"])
    others = t["series"]
    prev = (
        f'<a href="{url(cat, t, others[k - 1])}">← Series {others[k - 1]["number"]}: '
        f"{escape(others[k - 1]['title'])}</a>"
        if k > 0
        else f'<a href="{url(cat, t)}">← {escape(t["title"])}</a>'
    )
    nxt = (
        f'<a href="{url(cat, t, others[k + 1])}">Series {others[k + 1]["number"]}: '
        f"{escape(others[k + 1]['title'])} →</a>"
        if k + 1 < len(others)
        else f'<a href="{cat["base"]}">All courses →</a>'
    )
    cadence = (
        "This course is planned: the outline may change. Join the waitlist to hear when it opens."
        if planned
        else f"Module 1 opens in {escape(s['status'])}, then one a week: join the cohort or "
        "follow at your own pace."
    )
    return f"""    <section class="wrap hero">
      <p class="crumbs"><a href="{cat["base"]}">All courses</a> /
        <a href="{url(cat, t)}">{escape(t["short"])}</a> / Series {s["number"]}</p>
      <p class="eyebrow">{escape(t["title"])} · Series {s["number"]}</p>
      <h1>{escape(s["title"])}</h1>
      <p class="lede">{escape(s["tagline"])}</p>
      <div class="meta">{status_chip(s)}<span class="chip">{len(s["modules"])} modules</span>
        <span class="chip">{escape(s["level"])}</span><span class="chip">Free</span></div>
    </section>

    <section class="wrap">
      <div class="split">
        <div>
          <p>{escape(s["summary"])}</p>
          <p>{cadence}</p>
          <h2>Modules</h2>
          <ol class="modules">
{chr(10).join(mods)}
          </ol>
        </div>
        <aside class="aside">
          <h3>What you will use</h3>
          <ul>{tools}</ul>
          <h3>How to follow</h3>
          <ul><li>In the browser, on any device: the full setup runs online</li><li>On your own
            computer: Windows, macOS or Linux</li><li>Large runs (optional): a server or cloud
            machine</li></ul>
          <h3>Learn together</h3>
          <ul><li>A cohort, one module a week</li><li>Homework and a Discord community</li>
            <li>A certificate for the capstone</li></ul>
          <a class="btn primary" href="{WAITLIST}">Join the waitlist</a>
        </aside>
      </div>
      <nav class="next" aria-label="Other courses">{prev}{nxt}</nav>
    </section>
"""


def lesson_page(
    cat: dict, t: dict, s: dict, m: dict, html: str, toc: list, summary: str, setup: str = ""
) -> str:
    """A module's lesson page: the lesson, a contents panel, and the modules either side.

    Args:
        cat: The catalogue.
        t: The track.
        s: The series.
        m: The module.
        html: The lesson as HTML.
        toc: The lesson's sections, as (anchor, heading).
        summary: The lesson's one-line summary.
        setup: The "Get set up" box, shown before the lesson.

    Returns:
        The page body.
    """
    here = url(cat, t, s)
    mods = s["modules"]
    k = mods.index(m)

    def neighbour(j: int, before: bool) -> str:
        """A link to the module before or after this one (or back to the series)."""
        left, right = ("← ", "") if before else ("", " →")
        if not 0 <= j < len(mods):
            return f'<a href="{here}">{left}Series {s["number"]}{right}</a>'
        other = mods[j]
        target = lessons.folder(s["folder"], other["number"])
        label = f"Module {other['number']}: {escape(other['title'])}"
        if target is None:
            return f'<span class="soon">{label} (to follow)</span>'
        return f'<a href="{here}{target.name}/">{left}{label}{right}</a>'

    toc = [("get-set-up", "Get set up"), *toc] if setup else toc
    contents = "".join(f'<li><a href="#{a}">{escape(h)}</a></li>' for a, h in toc)
    tools = "".join(f'<span class="chip">{escape(x)}</span>' for x in m["tools"])
    return f"""    <section class="wrap hero lesson-hero">
      <p class="crumbs"><a href="{cat["base"]}">All courses</a> /
        <a href="{url(cat, t)}">{escape(t["short"])}</a> /
        <a href="{here}">Series {s["number"]}</a> / Module {m["number"]}</p>
      <p class="eyebrow">Series {s["number"]} · Module {m["number"]} ·
        {escape(m.get("part", ""))}</p>
      <h1>{escape(m["title"])}</h1>
      <p class="lede">{escape(summary)}</p>
      <div class="meta">{tools}</div>
    </section>

    <section class="wrap">
      <div class="split lesson-split">
        <article class="lesson">
{setup}
{html}
        </article>
        <aside class="aside toc">
          <h3>In this lesson</h3>
          <ul class="contents">{contents}</ul>
          <h3>Practise</h3>
          <ul><li>Homework: <code>homework.md</code> in the module's folder</li>
            <li>Ask in the Discord community</li></ul>
          <a class="btn primary" href="{WAITLIST}">Join the waitlist</a>
        </aside>
      </div>
      <nav class="next" aria-label="Other modules">
        {neighbour(k - 1, True)}{neighbour(k + 1, False)}</nav>
    </section>
"""


def readme(cat: dict, t: dict, s: dict) -> str:
    """A course folder's README, written from the catalogue so the two never disagree.

    Args:
        cat: The catalogue.
        t: The course's track.
        s: The course.

    Returns:
        The README text.
    """
    status = s["status"] if s["status"] == "Planned" else f"opens {s['status']}"
    lines = [
        f"# Series {s['number']}: {s['title']}",
        "",
        f"Track: {t['title']}. {s['tagline']}",
        "",
        f"**Status:** {status} · **Level:** {s['level']}",
        "",
        s["summary"],
        "",
        "## Modules",
    ]
    part = None
    for m in s["modules"]:
        if m.get("part") and m["part"] != part:
            part = m["part"]
            lines += ["", f"### {part}", ""]
        elif part is None and m is s["modules"][0]:
            lines.append("")
        tools = f" ({', '.join(m['tools'])})" if m["tools"] else ""
        lines.append(f"{m['number']}. **{m['title']}.** {m['what']}{tools}")
    lines += [
        "",
        "Each module will have its own folder here (`01-…`, `02-…`) with its code, tests, lesson",
        "and notebook. This file is written from `shared/site/catalogue.json` by",
        "`python -m shared.site.build`; the course page is",
        f"https://monstrous.com.ng{url(cat, t, s)}.",
    ]
    return "\n".join(lines) + "\n"


def track_readme(cat: dict, t: dict) -> str:
    """A track folder's README, written from the catalogue.

    Args:
        cat: The catalogue.
        t: The track.

    Returns:
        The README text.
    """
    lines = [f"# {t['title']}", "", t["tagline"], "", f"**Status:** {t['status']}", "",
             t["summary"]]  # fmt: skip
    if t["series"]:
        lines += ["", "## Series", ""]
        for s in t["series"]:
            folder = Path(s["folder"]).name
            lines.append(f"{s['number']}. [{s['title']}]({folder}/): {s['tagline']}")
    lines += [
        "",
        "This file is written from `shared/site/catalogue.json` by `python -m shared.site.build`;",
        f"the track's page is https://monstrous.com.ng{url(cat, t)}.",
    ]
    return "\n".join(lines) + "\n"


def readmes(cat: dict) -> dict[Path, str]:
    """Every README the catalogue defines: one per track and one per course.

    Args:
        cat: The catalogue.

    Returns:
        Each README's path and text.
    """
    out = {}
    for t in cat["tracks"]:
        out[Path(t["folder"], "README.md")] = track_readme(cat, t)
        for s in t["series"]:
            out[Path(s["folder"], "README.md")] = readme(cat, t, s)
    return out


def build(out: Path = DIST) -> list[Path]:
    """Write every page and the assets under out/learn/, and the READMEs.

    Args:
        out: The output folder.

    Returns:
        The pages written.
    """
    cat = load()
    root = out / "learn"
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(STATIC, root / "assets")
    css = (root / "assets/css/learn.css").read_bytes() + lessons.code_css().encode()
    stamp = hashlib.sha256(css).hexdigest()[:10]
    base = cat["base"]
    pages = {
        root / "index.html": frame(
            cat,
            base,
            "Learn with Monstrous Data: data engineering and AI for chemists",
            "Free, practical courses in data engineering and AI for chemists who know some "
            "Python, with code you can run on any device.",
            home(cat),
            base,
        )
    }
    for i, t in enumerate(cat["tracks"]):
        pages[root / t["slug"] / "index.html"] = frame(
            cat,
            url(cat, t),
            f"{t['title']} · Learn · Monstrous Data",
            f"{t['tagline']} {t['summary']}",
            track_page(cat, i),
            url(cat, t),
        )
        for k, s in enumerate(t["series"]):
            pages[root / t["slug"] / s["slug"] / "index.html"] = frame(
                cat,
                url(cat, t, s),
                f"Series {s['number']}: {s['title']} · Learn · Monstrous Data",
                f"{s['tagline']} {s['summary']}",
                course(cat, i, k),
                url(cat, t, s),
            )
    (root / "assets/css/code.css").write_text(lessons.code_css(), encoding="utf-8")
    for t in cat["tracks"]:
        for s in t["series"]:
            for m in s["modules"]:
                src = lessons.folder(s["folder"], m["number"])
                if src is None:
                    continue
                meta, html, toc = lessons.render((src / "lesson.md").read_text(encoding="utf-8"))
                dest = root / t["slug"] / s["slug"] / src.name
                if (src / "figures").is_dir():
                    shutil.copytree(src / "figures", dest / "figures")
                dest.mkdir(parents=True, exist_ok=True)
                for name in ("notebook.ipynb", "code.py"):
                    if (src / name).exists():
                        shutil.copy2(src / name, dest / name)
                setup = setup_html(s["folder"], meta, src.name)
                pages[dest / "index.html"] = frame(
                    cat,
                    f"{url(cat, t, s)}{src.name}/",
                    f"{m['title']} · Series {s['number']} · Learn · Monstrous Data",
                    meta.get("summary", m["what"]),
                    lesson_page(cat, t, s, m, html, toc, meta.get("summary", m["what"]), setup),
                    f"{url(cat, t, s)}{src.name}/",
                )
    for path, text in readmes(cat).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    for path, html in pages.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        html = html.replace("assets/css/learn.css", f"assets/css/learn.css?v={stamp}")
        html = html.replace("assets/css/code.css", f"assets/css/code.css?v={stamp}")
        path.write_text(html, encoding="utf-8", newline="\n")
    return list(pages)


def zip_site(out: Path = DIST) -> Path:
    """Zip out/learn/ for upload, to be unpacked as public_html/learn/.

    Args:
        out: The folder build() wrote to.

    Returns:
        The zip file.
    """
    root = out / "learn"
    zpath = out / "learn.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(root))
    return zpath


def main() -> None:
    """Build the pages, and the zip when asked."""
    pages = build()
    print(f"{len(pages)} pages in {DIST / 'learn'}")
    if "--zip" in sys.argv:
        print(f"-> {zip_site()}")


if __name__ == "__main__":
    main()
