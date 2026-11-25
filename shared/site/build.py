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
import json
import os
import shutil
import sys
import zipfile
from html import escape
from pathlib import Path

from .. import lessonkit
from . import lessons


def setup_html(series_folder: str, meta: dict, folder: str) -> str:
    """A lesson's "Get set up" box, from the shared lessonkit (the same text as the notebook
    and the module README), with download links to the notebook and the code beside the page.

    Args:
        series_folder: The series' folder in the repository, e.g. data-engineering/series-1.
        meta: The lesson's front matter.
        folder: The module's folder name.

    Returns:
        The box's HTML.
    """
    lines = lessonkit.setup_lines(meta, folder, series_folder)[1:]  # without its own heading
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
JOURNEY = HERE / "journey.json"
START = HERE / "start.md"  # the "Start here" page
DOCKER_GUIDE = HERE.parent / "docker" / "README.md"  # the database guide, also a page
STATIC = HERE / "static"
DIST = Path("dist")
# the waitlist form, a page of this site (/learn/waitlist/): it sends each sign-up to FluentCRM on
# monstrous.com.ng, which keeps the list and emails people to confirm their address
WAITLIST = "/learn/waitlist/"
# where the form sends sign-ups: the Monstrous Waitlist plugin on the same site (WordPress), which
# adds them to FluentCRM; WAITLIST_ENDPOINT in the environment or .env overrides it (for testing)
WAITLIST_ENDPOINT = "/wp-json/monstrous/v1/waitlist"
COUNTRIES = HERE / "countries.json"  # every country's English name, for the form's country list
# the waitlist's questions with a fixed list of answers; FluentCRM stores the answer as written here
COURSE_CHOICES = ["Data Engineering", "MLOps for Chemists", "Agentic AI in Chemistry"]
ROLES = ["Undergraduate student", "MSc student", "PhD student", "Postdoctoral researcher",
         "Academic staff", "Scientist in industry", "Data professional", "Other"]  # fmt: skip
FIELDS_OF_STUDY = ["Chemistry", "Biochemistry", "Pharmacy or pharmacology", "Materials science",
                   "Chemical engineering", "Other"]  # fmt: skip
PYTHON_LEVELS = ["None yet", "A little", "Comfortable"]
HEARD_FROM = ["LinkedIn", "Facebook", "A colleague or friend", "A search engine", "Other"]
GOALS_MAX = 300  # characters; the same limit as waitlist.js
# the course's repository on GitHub, where readers can give it a star
REPO_URL = "https://github.com/David-Alobo/monstrous-learn"
# where the rating box at the end of a lesson sends its rating (the same plugin as the waitlist);
# FEEDBACK_ENDPOINT in the environment or .env overrides it (for testing)
FEEDBACK_ENDPOINT = "/wp-json/monstrous/v1/feedback"
# the waitlist offer in the side panel of lessons and guides: its own labelled box, so it is not
# read as the answer to whatever is listed above it
UPDATES = f"""          <div class="updates">
            <h3>Course updates</h3>
            <p>Hear when a course opens. Free, and you can unsubscribe at any time.</p>
            <a class="btn primary" href="{WAITLIST}">Join the waitlist</a>
            <p class="star"><a href="{REPO_URL}">&#9733; Star the course on GitHub</a></p>
          </div>"""
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
    """A track or course's status as a chip: when it opens, "Open", "Planned" or "Coming later".

    Args:
        item: A track or a course from the catalogue.

    Returns:
        The chip markup.
    """
    if item["status"] in ("Planned", "Coming later"):
        return f'<span class="chip planned">{escape(item["status"])}</span>'
    if item["status"] == "Open":  # every module can be read now; no cohort date yet
        return '<span class="chip status">Open to read</span>'
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


def journeys(path: Path = JOURNEY) -> dict:
    """The "big picture" diagrams, one per course that has one, keyed by the course's folder.

    Args:
        path: The diagrams' data file.

    Returns:
        The parsed diagrams.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def module_link(cat: dict, t: dict, s: dict, number: int) -> str:
    """A link to a module's lesson, or its name marked "to follow" if not yet written.

    Args:
        cat: The catalogue.
        t: The track.
        s: The series.
        number: The module's number.

    Returns:
        The link (or label) as HTML.
    """
    m = s["modules"][number - 1]
    label = f"Module {number}: {escape(m['title'])}"
    lesson = lessons.folder(s["folder"], number)
    if lesson is None:
        return f'<span class="soon">{label} (to follow)</span>'
    return f'<a href="{url(cat, t, s)}{lesson.name}/">{label}</a>'


def journey_step(cat: dict, t: dict, s: dict, step: dict, number: int | None) -> tuple[str, str]:
    """One step of the big-picture diagram: its button and its details panel.

    Args:
        cat: The catalogue.
        t: The track.
        s: The series.
        step: The step's data.
        number: Its position in the main flow (None for a lane that runs alongside every step).

    Returns:
        The button and the panel, as HTML.
    """
    sid = escape(step["id"])
    badge = f'<span class="jn">{number}</span>' if number else ""
    button = (
        f'<button type="button" class="jstep" id="step-{sid}" data-step="{sid}" '
        f'aria-pressed="false" aria-controls="jp-{sid}">{badge}'
        f'<span class="jl">{escape(step["label"])}</span>'
        f'<span class="jq">{escape(step["asks"])}</span></button>'
    )
    how = "".join(f"<li>{escape(x)}</li>" for x in step["how"])
    where = "".join(f"<li>{module_link(cat, t, s, n)}</li>" for n in step["modules"])
    nxt = f'<p class="jnext">{escape(step["next"])}</p>' if step.get("next") else ""
    panel = f"""        <div class="jpanel" id="jp-{sid}" data-panel="{sid}" role="region"
          aria-label="{escape(step["label"])}">
          <h3>{badge}{escape(step["label"])}</h3>
          <div class="jvoices">
            <p class="jchemist"><span>The chemist asks</span>{escape(step["asks"])}</p>
            <p class="jengineer"><span>The data engineer answers</span>{escape(step["answer"])}</p>
          </div>
          <dl class="jfacts">
            <div><dt>Why</dt><dd>{escape(step["why"])}</dd></div>
            <div><dt>How</dt><dd><ul>{how}</ul></dd></div>
            <div><dt>Where in the course</dt><dd><ul>{where}</ul></dd></div>
            <div><dt>When</dt><dd>{escape(step["when"])}</dd></div>
          </dl>{nxt}
        </div>"""
    return button, panel


def journey(cat: dict, t: dict, s: dict) -> str:
    """A course's interactive big-picture diagram, or nothing if the course has none.

    The steps of the main flow run in order, with the lanes (reliability, versioning, ...)
    beneath them because they apply at every step. Every step's details are in the page, so it
    reads without JavaScript; journey.js shows one at a time.

    Args:
        cat: The catalogue.
        t: The track.
        s: The series.

    Returns:
        The diagram's section, as HTML.
    """
    data = journeys().get(s["folder"])
    if data is None:
        return ""
    flow = [journey_step(cat, t, s, st, n) for n, st in enumerate(data["stages"], start=1)]
    lanes = [journey_step(cat, t, s, st, None) for st in data["lanes"]]
    # the steps in rows by phase (bring it in, make it right, put it to use), kept in order
    rows: list[tuple[str, list[str]]] = []
    for st, (b, _) in zip(data["stages"], flow, strict=True):
        if not rows or rows[-1][0] != st["phase"]:
            rows.append((st["phase"], []))
        rows[-1][1].append(f"<li>{b}</li>")
    steps = "\n".join(
        f'          <li class="jphase"><p class="jphase-name">{escape(name)}</p>'
        f'<ol class="jrow">{"".join(items)}</ol></li>'
        for name, items in rows
    )
    lane_buttons = "\n".join(f"          <li>{b}</li>" for b, _ in lanes)
    panels = "\n".join(p for _, p in flow + lanes)
    return f"""    <section class="wrap journey" id="big-picture" aria-labelledby="big-picture-h">
      <h2 id="big-picture-h">{escape(data["title"])}</h2>
      <div class="jproblem">
        <p class="jtag">The problem</p>
        <p>{escape(data["problem"])}</p>
        <p class="jask">{escape(data["question"])}</p>
      </div>
      <p class="jintro">{escape(data["intro"])}</p>
      <div class="jdiagram">
        <p class="jtag">The path of the data</p>
        <ol class="jflow">
{steps}
        </ol>
        <p class="jtag">At every step</p>
        <ul class="jlanes">
{lane_buttons}
        </ul>
      </div>
      <div class="jpanels" aria-live="polite">
{panels}
      </div>
    </section>
    <script type="module" src="{cat["base"]}assets/js/journey.js"></script>
"""


def where_it_fits(cat: dict, t: dict, s: dict, m: dict) -> str:
    """A strip on a lesson page showing which steps of the big picture this module teaches.

    Args:
        cat: The catalogue.
        t: The track.
        s: The series.
        m: The module.

    Returns:
        The strip as HTML, or nothing if the course has no diagram.
    """
    data = journeys().get(s["folder"])
    if data is None:
        return ""
    here = url(cat, t, s)
    items = []
    for st in data["stages"] + data["lanes"]:
        on = m["number"] in st["modules"]
        cls = ' class="on"' if on else ""
        current = ' aria-current="true"' if on else ""
        items.append(
            f'<li{cls}><a href="{here}#step-{escape(st["id"])}"{current}>'
            f"{escape(st['label'])}</a></li>"
        )
    return f"""      <nav class="fits" aria-label="Where this module fits">
        <p>Where this module fits in <a href="{here}#big-picture">the big picture</a></p>
        <ol>{"".join(items)}</ol>
      </nav>"""


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
      <p class="lede">Free, practical courses for chemists who want to handle chemical data the
        way software engineers do: reliably, at any size, and traceable to its source. That work
        is called data engineering, and it is where we start; MLOps and agentic AI follow.</p>
      <p>If you have run a few cells of Python in a notebook, you can start: every tool, from Git
        to databases, is taught as you go, with code you can run on any device and every example
        tested before it is published.</p>
      <div class="meta"><span class="chip">Free</span><span class="chip">Any device</span>
        <span class="chip status">First course: {escape(cat["opens"])}</span></div>
      <div class="actions">
        <a class="btn primary" href="{url(cat, first_track, first)}">
          Start with {escape(first_track["short"])}, Series {first["number"]}</a>
        <a class="btn ghost" href="{cat["base"]}start/">New here? Start here</a>
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
    # the other tracks, as small cards: what each is, and when it opens
    others = "\n".join(
        f"""        <a class="card course" href="{url(cat, o)}">
          <div class="row"><h3>{escape(o["title"])}</h3>{status_chip(o)}</div>
          <p>{escape(o["tagline"])}</p>
          <span class="go">View the track →</span>
        </a>"""
        for o in cat["tracks"]
        if o is not t
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
      <nav class="other-tracks" aria-label="Other tracks">
        <h2>Other tracks</h2>
        <div class="grid">
{others}
        </div>
        <p class="back"><a href="{cat["base"]}">← All courses</a></p>
      </nav>
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
        lesson = lessons.folder(s["folder"], m["number"])
        # one status per module: written lessons can be read now, the others are still to come
        when = "Planned" if planned else ("Open to read" if lesson else "To follow")
        tools = "".join(f'<span class="chip">{escape(x)}</span>' for x in m["tools"])
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
        else "Every module is open now: you can read and run them today, on your own. A cohort "
        "date will be announced; join the waitlist to hear when."
        if s["status"] == "Open"
        else f"The cohort starts in {escape(s['status'])}, with one module a week. The modules "
        "already written are open now: you can start reading and running them today, on your own."
    )
    first = lessons.folder(s["folder"], 1)
    start_box = (
        ""
        if planned or first is None
        else f"""    <section class="wrap">
      <div class="start-box">
        <h2>Start here</h2>
        <ol><li>Open <a href="{url(cat, t, s)}{first.name}/">Module 1</a> and read it on any
          device.</li>
          <li>To run its code, click <b>Open this lesson in Google Colab</b> in its Get set up box:
          you need only a free Google account, nothing to install.</li>
          <li>New to notebooks? <a href="{cat["base"]}start/">Start here</a> shows every step,
          and what each word means.</li></ol>
      </div>
    </section>
"""
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
{start_box}{journey(cat, t, s)}
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
          <h3>What you need</h3>
          <ul><li>A web browser, on any device</li><li>A free Google account, to run the code
            in Google Colab</li><li>A little Python: loops and functions</li></ul>
          <h3>What you will learn to use</h3>
          <p class="note">Each of these is taught in the course: none is needed to start.</p>
          <ul>{tools}</ul>
          <h3>How to follow</h3>
          <ul><li>In the browser, on any device: the full setup runs online</li><li>On your own
            computer: Windows, macOS or Linux</li><li>Large runs (optional): a server or cloud
            machine</li></ul>
          <h3>Learn together</h3>
          <ul><li>A cohort, one module a week</li><li>Homework and a Discord community</li>
            <li>A certificate for the capstone</li></ul>
          <a class="btn primary" href="{WAITLIST}">Join the waitlist</a>
          <p class="star"><a href="{REPO_URL}">&#9733; Star the course on GitHub</a>: it helps
            other chemists find it.</p>
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
{where_it_fits(cat, t, s, m)}
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
          <ul><li><a href="#homework">Homework</a>, at the end of this page</li>
            <li>Ask in the Discord community</li></ul>
          <h3>New here?</h3>
          <ul><li><a href="{cat["base"]}start/">Start here</a>: how to run a lesson, and what
            each word means</li></ul>
{UPDATES}
        </aside>
      </div>
      <nav class="next" aria-label="Other modules">
        {neighbour(k - 1, True)}{neighbour(k + 1, False)}</nav>
    </section>
"""


def homework_html(src: Path) -> str:
    """A module's homework, shown at the end of its lesson page.

    Args:
        src: The module's folder, which may hold homework.md.

    Returns:
        The homework as an HTML section, or "" if the module has none.
    """
    path = src / "homework.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("# "))  # own title
    body = lessons.markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])
    return f'<section class="homework" id="homework"><h2>Homework</h2>{body}</section>'


def rating_box(cat: dict, module: str, endpoint: str) -> str:
    """The "How was this module?" box at the end of a lesson, and a line asking for a star.

    Args:
        cat: The catalogue.
        module: The lesson's address on the site, e.g. data-engineering/series-1/01-graphs-...
        endpoint: Where the rating is sent (the Monstrous Waitlist plugin's feedback address).

    Returns:
        The box's HTML.
    """
    stars = "".join(
        f'<input type="radio" id="rate-{n}" name="rating" value="{n}">'
        f'<label for="rate-{n}" title="{n} out of 5"><span aria-hidden="true">&#9733;</span>'
        f'<span class="sr">{n} star{"s" if n > 1 else ""}</span></label>'
        for n in range(
            5, 0, -1
        )  # written 5 to 1, shown 1 to 5: hovering lights the stars before it
    )
    return f"""<section class="rate-box" id="rate">
  <h2>How was this module?</h2>
  <form class="rate" data-endpoint="{escape(endpoint)}" data-module="{escape(module)}" novalidate>
    <fieldset class="stars">
      <legend>Your rating, from 1 (poor) to 5 (excellent)</legend>
      <span class="row">{stars}</span></fieldset>
    <label class="comment"><span>What would have made it clearer? (optional)</span>
      <textarea name="comment" rows="3" maxlength="1000"></textarea></label>
    <div class="trap" aria-hidden="true"><label>Leave this empty
      <input name="website" tabindex="-1" autocomplete="off"></label></div>
    <button class="btn ghost" type="submit">Send rating</button>
    <div class="form-status" role="status" aria-live="polite"></div>
    <p class="note">Anonymous: we keep only the rating and your comment, never your name, email or
      address, and nothing is saved in your browser.</p>
  </form>
  <p class="star">Found this module useful? <a href="{REPO_URL}">&#9733; Star the course on
    GitHub</a>: it helps other chemists find it.</p>
</section>
<script type="module" src="{cat["base"]}assets/js/feedback.js"></script>
"""


def guide(cat: dict, title: str, summary: str, html: str, toc: list) -> str:
    """A guide's page (Start here, the database guide): its text and a contents panel.

    Args:
        cat: The catalogue.
        title: The guide's title.
        summary: Its one-line summary.
        html: The guide as HTML.
        toc: Its sections, as (anchor, heading).

    Returns:
        The page body.
    """
    contents = "".join(f'<li><a href="#{a}">{escape(h)}</a></li>' for a, h in toc)
    return f"""    <section class="wrap hero lesson-hero">
      <p class="crumbs"><a href="{cat["base"]}">All courses</a> / {escape(title)}</p>
      <h1>{escape(title)}</h1>
      <p class="lede">{escape(summary)}</p>
    </section>

    <section class="wrap">
      <div class="split lesson-split">
        <article class="lesson">
{html}
        </article>
        <aside class="aside toc">
          <h3>On this page</h3>
          <ul class="contents">{contents}</ul>
{UPDATES}
        </aside>
      </div>
    </section>
"""


def setting(name: str) -> str:
    """A setting of the site build: from the environment, or else from the .env file it runs beside.

    Used to point the waitlist form at a test receiver while developing.

    Args:
        name: The setting's name, e.g. WAITLIST_ENDPOINT.

    Returns:
        Its value, or "" if it is not set.
    """
    if os.environ.get(name):
        return os.environ[name]
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    return ""


def choices(name: str, options: list[str], label: str) -> str:
    """A drop-down list for an optional question, starting with "Choose".

    Args:
        name: The field's name (the FluentCRM field it fills).
        options: The answers offered.
        label: The question.

    Returns:
        The labelled list's HTML.
    """
    items = "".join(f'<option value="{escape(o)}">{escape(o)}</option>' for o in options)
    return (f'<label class="field"><span>{escape(label)}</span><select name="{name}">'
            f'<option value="">Choose (optional)</option>{items}</select></label>')  # fmt: skip


def waitlist_page(cat: dict, endpoint: str) -> str:
    """The waitlist page: what joining means, why we ask, and the form.

    Args:
        cat: The catalogue.
        endpoint: The address the form sends sign-ups to (the Monstrous Waitlist plugin); "" makes
            the form say sign-ups open soon.

    Returns:
        The page body.
    """
    base = cat["base"]
    countries = json.loads(COUNTRIES.read_text(encoding="utf-8"))
    country_list = "".join(f'<option value="{escape(c)}"></option>' for c in countries)
    courses = "".join(
        f'<label class="check"><input type="checkbox" name="courses" value="{escape(c)}"'
        f"{' checked' if k == 0 else ''}> {escape(c)}</label>"
        for k, c in enumerate(COURSE_CHOICES)
    )
    levels = "".join(
        f'<label class="check"><input type="radio" name="python_level" value="{escape(v)}">'
        f" {escape(v)}</label>"
        for v in PYTHON_LEVELS
    )
    return f"""    <section class="wrap hero lesson-hero">
      <p class="crumbs"><a href="{base}">All courses</a> / Join the waitlist</p>
      <h1>Join the course waitlist</h1>
      <p class="lede">Free courses in data engineering for chemists. Join the waitlist and we will
        email you when a course you choose opens.</p>
    </section>

    <section class="wrap">
      <div class="split waitlist-split">
        <div>
          <h2>What joining means</h2>
          <ol class="steps">
            <li>We email you when a course you chose opens. The first, Data Engineering for
              Cheminformatics, starts in {escape(cat["opens"])}.</li>
            <li>Occasional course news, and nothing else. Every email has a link to
              unsubscribe.</li>
            <li>You confirm your email first, so nobody can sign you up but you.</li>
          </ol>
          <h3>Why we ask the other questions</h3>
          <p>They are all optional. They help us plan the course for the people who take it: cohort
            times across time zones, examples from your field, and how much Python to assume. We
            look only at totals, never at one person's answers, and never share them. Our
            <a href="https://monstrous.com.ng/privacy-policy/">privacy policy</a> says how we look
            after them.</p>
          <p>The first course's lessons are already open to read.
            <a href="{base}start/">Start here</a>.</p>
        </div>
        <form class="waitlist panel" data-endpoint="{escape(endpoint)}" novalidate>
          <h2>Join the waitlist</h2>
          <label class="field"><span>First name</span>
            <input name="first_name" autocomplete="given-name" maxlength="60" required></label>
          <label class="field"><span>Email address</span>
            <input name="email" type="email" autocomplete="email" required></label>
          <fieldset class="field" name="courses">
            <legend>Which courses would you like to hear about?</legend>
            {courses}</fieldset>
          <p class="optional">Optional, to help us plan the courses:</p>
          <label class="field"><span>Country</span>
            <input name="country" list="countries" autocomplete="country-name"
              placeholder="Start typing, then choose"></label>
          <datalist id="countries">{country_list}</datalist>
          {choices("role", ROLES, "Which best describes you?")}
          <label class="field"><span>Position or job title</span>
            <input name="position" autocomplete="organization-title" maxlength="100"
              placeholder="e.g. Research Scientist, Lab Manager"></label>
          {choices("field_of_study", FIELDS_OF_STUDY, "Your field")}
          <fieldset class="field"><legend>Your Python experience</legend>{levels}</fieldset>
          {choices("heard_from", HEARD_FROM, "How did you hear about the course?")}
          <label class="field"><span>What do you hope to do with it?</span>
            <textarea name="goals" rows="3" maxlength="{GOALS_MAX}"
              placeholder="A sentence or two"></textarea></label>
          <div class="trap" aria-hidden="true"><label>Leave this empty
            <input name="website" tabindex="-1" autocomplete="off"></label></div>
          <label class="check consent"><input type="checkbox" name="consent" value="yes" required>
            <span>I agree to Monstrous Data storing my answers to send me news of the courses I
            chose. I can unsubscribe at any time with the link in every email. See the
            <a href="https://monstrous.com.ng/privacy-policy/">privacy policy</a>.</span></label>
          <button class="btn primary" type="submit">Join the waitlist</button>
          <div class="form-status" role="status" aria-live="polite"></div>
        </form>
      </div>
    </section>
    <script type="module" src="{base}assets/js/waitlist.js"></script>
"""


def guide_pages(cat: dict, root: Path) -> dict[Path, str]:
    """The guides' pages: Start here (/learn/start/) and the database guide (/learn/databases/).

    Args:
        cat: The catalogue.
        root: The site's folder (out/learn).

    Returns:
        Each page's path and HTML.
    """
    base = cat["base"]
    pages = {}
    meta, html, toc = lessons.render(START.read_text(encoding="utf-8").replace("{base}", base))
    pages[root / "start" / "index.html"] = frame(
        cat, f"{base}start/", "Start here · Learn · Monstrous Data", meta["summary"],
        guide(cat, meta["title"], meta["summary"], html, toc), f"{base}start/",
    )  # fmt: skip
    text = DOCKER_GUIDE.read_text(encoding="utf-8")
    title = text.splitlines()[0].lstrip("# ").strip()
    text = "\n".join(text.splitlines()[1:])
    summary = "Install Docker, start the courses' PostgreSQL and Neo4j databases, and log in."
    _, html, toc = lessons.render(text)
    if (DOCKER_GUIDE.parent / "images").is_dir():
        shutil.copytree(DOCKER_GUIDE.parent / "images", root / "databases" / "images")
    pages[root / "databases" / "index.html"] = frame(
        cat, f"{base}databases/", "The databases, in Docker · Learn · Monstrous Data", summary,
        guide(cat, title, summary, html, toc), f"{base}databases/",
    )  # fmt: skip
    return pages


COLAB_BADGE = "https://colab.research.google.com/assets/colab-badge.svg"
GITHUB_REPO = REPO_URL.removeprefix("https://github.com/")


def module_links(cat: dict, t: dict, s: dict, src: Path) -> str:
    """One module's links for a README: the lesson online, the notebook in Colab, its folder.

    Args:
        cat: The catalogue.
        t: The module's track.
        s: The module's course.
        src: The module's folder in the repository.

    Returns:
        The links, as one line of Markdown.
    """
    page = f"https://monstrous.com.ng{url(cat, t, s)}{src.name}/"
    colab = (
        f"https://colab.research.google.com/github/{GITHUB_REPO}/blob/main/"
        f"{s['folder']}/{src.name}/notebook.ipynb"
    )
    return f"[Read the lesson]({page}) · [![Open in Colab]({COLAB_BADGE})]({colab})"


def readme(cat: dict, t: dict, s: dict) -> str:
    """A course folder's README, written from the catalogue so the two never disagree.

    Args:
        cat: The catalogue.
        t: The course's track.
        s: The course.

    Returns:
        The README text.
    """
    status = {"Planned": "Planned", "Open": "Open to read"}.get(s["status"], f"opens {s['status']}")
    lines = [
        f"# Series {s['number']}: {s['title']}",
        "",
        f"Track: {t['title']}. {s['tagline']}",
        "",
        f"**Status:** {status} · **Level:** {s['level']} · "
        f"**[Read it online](https://monstrous.com.ng{url(cat, t, s)})**",
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
        tools = f" *{', '.join(m['tools'])}*" if m["tools"] else ""
        src = lessons.folder(s["folder"], m["number"])
        if src is None:
            lines.append(f"{m['number']}. **{m['title']}.** {m['what']}{tools}")
            continue
        lines += [
            f"{m['number']}. **[{m['title']}]({src.name}/)**. {m['what']}{tools}",
            "",
            f"   {module_links(cat, t, s, src)}",
            "",
        ]
    if any(lessons.folder(s["folder"], m["number"]) for m in s["modules"]):
        lines += [
            "",
            "Each module folder holds the lesson (`lesson.md`), a notebook, the code on its own",
            "and the homework. New to notebooks?",
            "[Start here](https://monstrous.com.ng/learn/start/) shows every step.",
        ]
    else:
        lines += ["", "Each module will have its own folder here, with its lesson and notebook."]
    lines += [
        "",
        "*This file is written from `shared/site/catalogue.json` by `python -m shared.site.build`;",
        f"the course page is https://monstrous.com.ng{url(cat, t, s)}.*",
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


MODULES_START = "<!-- modules:start (written by python -m shared.site.build) -->"
MODULES_END = "<!-- modules:end -->"


def root_readme(cat: dict, text: str) -> str:
    """The repository's front page with its table of written modules brought up to date.

    The front page is written by hand, except the part between MODULES_START and MODULES_END,
    which lists every written module with its lesson and notebook links.

    Args:
        cat: The catalogue.
        text: The README as it stands.

    Returns:
        The README with that part rewritten (unchanged if it has no markers).
    """
    if MODULES_START not in text:
        return text
    rows = []
    for t in cat["tracks"]:
        for s in t["series"]:
            written = [(m, lessons.folder(s["folder"], m["number"])) for m in s["modules"]]
            written = [(m, src) for m, src in written if src is not None]
            if not written:
                continue
            rows += [
                f"**Series {s['number']}: {s['title']}**",
                "",
                "| # | Module | Read or run it |",
                "|---|---|---|",
            ]
            for m, src in written:
                title = f"[{m['title']}]({s['folder']}/{src.name}/)"
                rows.append(f"| {m['number']} | {title} | {module_links(cat, t, s, src)} |")
            rows.append("")
    head, rest = text.split(MODULES_START, 1)
    _, tail = rest.split(MODULES_END, 1)
    return head + MODULES_START + "\n\n" + "\n".join(rows) + "\n" + MODULES_END + tail


def readmes(cat: dict) -> dict[Path, str]:
    """Every README the catalogue defines: one per track and one per course.

    Args:
        cat: The catalogue.

    Returns:
        Each README's path and text.
    """
    out = {}
    root = Path("README.md")
    if root.exists():
        out[root] = root_readme(cat, root.read_text(encoding="utf-8"))
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
    css = (
        (root / "assets/css/learn.css").read_bytes()
        + lessons.code_css().encode()
        + (root / "assets/js/journey.js").read_bytes()
        + (root / "assets/js/waitlist.js").read_bytes()
        + (root / "assets/js/totop.js").read_bytes()
        + (root / "assets/js/toc.js").read_bytes()
        + (root / "assets/js/feedback.js").read_bytes()
    )
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
                homework = homework_html(src)
                if homework:
                    html += homework
                    toc = [*toc, ("homework", "Homework")]
                module = f"{t['slug']}/{s['slug']}/{src.name}"
                html += rating_box(cat, module, setting("FEEDBACK_ENDPOINT") or FEEDBACK_ENDPOINT)
                toc = [*toc, ("rate", "Rate this module")]
                pages[dest / "index.html"] = frame(
                    cat,
                    f"{url(cat, t, s)}{src.name}/",
                    f"{m['title']} · Series {s['number']} · Learn · Monstrous Data",
                    meta.get("summary", m["what"]),
                    lesson_page(cat, t, s, m, html, toc, meta.get("summary", m["what"]), setup),
                    f"{url(cat, t, s)}{src.name}/",
                )
    pages.update(guide_pages(cat, root))
    pages[root / "waitlist" / "index.html"] = frame(
        cat, WAITLIST, "Join the waitlist · Learn · Monstrous Data",
        "Free courses in data engineering for chemists. Join the waitlist to hear when a course "
        "opens; the first starts in " + cat["opens"] + ".",
        waitlist_page(cat, setting("WAITLIST_ENDPOINT") or WAITLIST_ENDPOINT), WAITLIST,
    )  # fmt: skip
    for path, text in readmes(cat).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    for path, html in pages.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        html = html.replace("assets/css/learn.css", f"assets/css/learn.css?v={stamp}")
        html = html.replace("assets/css/code.css", f"assets/css/code.css?v={stamp}")
        html = html.replace("assets/js/journey.js", f"assets/js/journey.js?v={stamp}")
        html = html.replace("assets/js/waitlist.js", f"assets/js/waitlist.js?v={stamp}")
        html = html.replace("assets/js/totop.js", f"assets/js/totop.js?v={stamp}")
        html = html.replace("assets/js/toc.js", f"assets/js/toc.js?v={stamp}")
        html = html.replace("assets/js/feedback.js", f"assets/js/feedback.js?v={stamp}")
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
