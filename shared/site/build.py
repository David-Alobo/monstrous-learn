"""Build the course pages for monstrous.com.ng/learn/ from the catalogue.

Usage (from the repository root):
    uv run python -m shared.site.build          # writes dist/learn/
    uv run python -m shared.site.build --zip    # and dist/learn.zip (unpack as public_html/learn/)

Every page is made from catalogue.json (the courses and their modules) and templates/frame.html (the
website's own header and footer, and a bar linking every course), so a new course is one entry in
the catalogue. The pages are static files, hosted beside WordPress like the 2027 by the Numbers
articles. The stylesheet's address carries a hash of its contents, so Cloudflare's cache never
serves an old one after an update.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from html import escape
from pathlib import Path

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
}


def load(path: Path = CATALOGUE) -> dict:
    """The catalogue of courses.

    Args:
        path: The catalogue file.

    Returns:
        The parsed catalogue.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def icon(name: str) -> str:
    """An inline line icon.

    Args:
        name: One of the keys of ICONS.

    Returns:
        The SVG markup.
    """
    return f'<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def status_chip(series: dict) -> str:
    """The status of a course as a chip: when it opens, or "Planned".

    Args:
        series: One course from the catalogue.

    Returns:
        The chip markup.
    """
    if series["status"] == "Planned":
        return '<span class="chip planned">Planned</span>'
    return f'<span class="chip status">Starts {escape(series["status"])}</span>'


def frame(cat: dict, path: str, title: str, description: str, body: str, current: str) -> str:
    """Put a page's body inside the website's header and footer and the courses' bar.

    Args:
        cat: The catalogue.
        path: The page's address on the site, e.g. "/learn/series-1/".
        title: The page title.
        description: The page description (search results and link previews).
        body: The page's main content.
        current: The slug of the course shown, or "" for the introductory page.

    Returns:
        The whole page.
    """
    base = cat["base"]
    on = ' class="on"'
    links = "\n".join(
        f'      <a{on if s["slug"] == current else ""} href="{base}{s["slug"]}/">'
        f'<span class="n">{s["number"]}</span>{escape(s["title"])}</a>'
        for s in cat["series"]
    )
    foot = "\n".join(
        f'        <a href="{base}{s["slug"]}/">Series {s["number"]}: {escape(s["title"])}</a>'
        for s in cat["series"]
    )
    page = FRAME.read_text(encoding="utf-8")
    for key, value in {
        "title": escape(title),
        "description": escape(description),
        "base": base,
        "path": path,
        "home_on": "" if current else "on",
        "course_links": links,
        "footer_links": foot,
        "body": body,
    }.items():
        page = page.replace("{{" + key + "}}", value)
    return page


def course_card(cat: dict, s: dict) -> str:
    """One course as a card on the introductory page.

    Args:
        cat: The catalogue.
        s: The course.

    Returns:
        The card markup.
    """
    return f"""      <a class="card course" href="{cat["base"]}{s["slug"]}/">
        <div class="row"><span class="num">{s["number"]}</span>{status_chip(s)}</div>
        <h3>{escape(s["title"])}</h3>
        <p>{escape(s["tagline"])}</p>
        <p class="small">{len(s["modules"])} modules · {escape(s["level"])}</p>
        <span class="go">View the course →</span>
      </a>"""


def intro(cat: dict) -> str:
    """The introductory page: what the courses are, how they work, and every course.

    Args:
        cat: The catalogue.

    Returns:
        The page body.
    """
    first = cat["series"][0]
    cards = "\n".join(course_card(cat, s) for s in cat["series"])
    return f"""    <section class="wrap hero">
      <p class="eyebrow">Monstrous Data · Learn</p>
      <h1>Data engineering for chemists</h1>
      <p class="lede">Free, practical courses for chemists who know some Python. Move from
        spreadsheets and SDF files to databases, pipelines and checked data, with code you can run
        and every example tested before it is published.</p>
      <div class="meta"><span class="chip">Free</span><span class="chip">Code you can run</span>
        <span class="chip status">First course: {escape(cat["opens"])}</span></div>
      <div class="actions">
        <a class="btn primary" href="{cat["base"]}{first["slug"]}/">
          Start with Series {first["number"]}</a>
        <a class="btn ghost" href="{WAITLIST}">Join the waitlist</a>
      </div>
    </section>

    <section class="wrap" id="how">
      <p class="eyebrow">How it works</p>
      <h2>Read, run, check</h2>
      <div class="grid">
        <div class="card">{icon("read")}<h3>Read</h3><p>Each module is one page: the problem,
          the idea, and the code, with diagrams where they help.</p></div>
        <div class="card">{icon("run")}<h3>Run</h3><p>Three ways to follow: a ready-made Docker
          setup, a notebook that runs online with nothing to install, or small exercises in the
          browser.</p></div>
        <div class="card">{icon("check")}<h3>Check</h3><p>Every example is tested before it is
          published, and all the code is open: compare your results with ours.</p></div>
      </div>
    </section>

    <section class="wrap" id="courses">
      <p class="eyebrow">Courses</p>
      <h2>Choose a course</h2>
      <p>Start with Series 1; the later series build on it.</p>
      <div class="grid">
{cards}
      </div>
    </section>

    <section class="wrap" id="who">
      <p class="eyebrow">Who it is for</p>
      <h2>Chemists who work with data</h2>
      <div class="grid">
        <div class="card"><h3>You will get most from it if you</h3><p>are a chemist, student or
          researcher who has written some Python (loops, functions, pandas) and wants your data to
          be organised, searchable and trustworthy.</p></div>
        <div class="card"><h3>You do not need</h3><p>a computer science degree, a server, or
          paid software. Everything used is open source, and the first modules run on a
          laptop.</p></div>
        <div class="card">{icon("team")}<h3>For teams</h3><p>Workshops for research groups and
          R&amp;D teams, and help with your own lab data.
          <a href="https://monstrous.com.ng/contact/">Discuss a project</a>.</p></div>
      </div>
    </section>
"""


def course(cat: dict, k: int) -> str:
    """A course's page: what it covers, its modules, how to follow it, and the other courses.

    Args:
        cat: The catalogue.
        k: The course's position in the catalogue.

    Returns:
        The page body.
    """
    s = cat["series"][k]
    planned = s["status"] == "Planned"
    mods = []
    for m in s["modules"]:
        when = "Planned" if planned else (s["status"] if m["number"] == 1 else "To follow")
        tools = "".join(f'<span class="chip">{escape(t)}</span>' for t in m["tools"])
        mods.append(f"""        <li class="module">
          <span class="mn">{m["number"]}</span>
          <div><h3>{escape(m["title"])}</h3><p>{escape(m["what"])}</p>
            <div class="tools">{tools}</div></div>
          <span class="when">{escape(when)}</span>
        </li>""")
    tools = "".join(f"<li>{escape(t)}</li>" for t in s["tools"])
    others = cat["series"]
    prev = (
        f'<a href="{cat["base"]}{others[k - 1]["slug"]}/">← Series {others[k - 1]["number"]}: '
        f"{escape(others[k - 1]['title'])}</a>"
        if k > 0
        else f'<a href="{cat["base"]}">← All courses</a>'
    )
    nxt = (
        f'<a href="{cat["base"]}{others[k + 1]["slug"]}/">Series {others[k + 1]["number"]}: '
        f"{escape(others[k + 1]['title'])} →</a>"
        if k + 1 < len(others)
        else f'<a href="{cat["base"]}">All courses →</a>'
    )
    cadence = (
        "This course is planned: the outline may change. Join the waitlist to hear when it opens."
        if planned
        else f"Module 1 opens in {escape(s['status'])}; a new module follows every two weeks."
    )
    return f"""    <section class="wrap hero">
      <p class="crumbs"><a href="{cat["base"]}">All courses</a> / Series {s["number"]}</p>
      <p class="eyebrow">Series {s["number"]}</p>
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
          <ul><li>Docker: the full setup on your computer</li><li>Online notebook: nothing to
            install</li><li>Small exercises in the browser</li></ul>
          <a class="btn primary" href="{WAITLIST}">Join the waitlist</a>
        </aside>
      </div>
      <nav class="next" aria-label="Other courses">{prev}{nxt}</nav>
    </section>
"""


def build(out: Path = DIST) -> list[Path]:
    """Write every page and the assets under out/learn/.

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
    css = (root / "assets/css/learn.css").read_bytes()
    stamp = hashlib.sha256(css).hexdigest()[:10]
    pages = {
        root / "index.html": frame(
            cat,
            cat["base"],
            "Learn: data engineering for chemists · Monstrous Data",
            "Free, practical courses for chemists who know some Python: chemical databases, "
            "pipelines and checked data, with code you can run.",
            intro(cat),
            "",
        )
    }
    for k, s in enumerate(cat["series"]):
        pages[root / s["slug"] / "index.html"] = frame(
            cat,
            f"{cat['base']}{s['slug']}/",
            f"Series {s['number']}: {s['title']} · Learn · Monstrous Data",
            s["tagline"] + " " + s["summary"],
            course(cat, k),
            s["slug"],
        )
    for path, html in pages.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        html = html.replace("assets/css/learn.css", f"assets/css/learn.css?v={stamp}")
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
