"""The course pages: the catalogue is complete, every page is built, and every link inside the
courses leads to a page that exists."""

import re

import pytest

from shared.site import build, lessons

CAT = build.load()
TRACKS = CAT["tracks"]
SERIES = [(t, s) for t in TRACKS for s in t["series"]]


def test_catalogue_is_complete():
    slugs = [t["slug"] for t in TRACKS]
    assert len(slugs) == len(set(slugs))
    for t in TRACKS:
        for key in ("title", "short", "tagline", "status", "summary", "folder"):
            assert t[key].strip(), (t["slug"], key)
        for k, s in enumerate(t["series"], start=1):
            assert s["number"] == k
            assert s["folder"].startswith(t["folder"] + "/"), s["folder"]
            assert [m["number"] for m in s["modules"]] == list(range(1, len(s["modules"]) + 1))
            for key in ("title", "tagline", "status", "level", "summary"):
                assert s[key].strip(), (s["slug"], key)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    return out, build.build(out)


def test_one_page_per_track_and_course_and_a_home(site):
    out, pages = site
    want = {out / "learn/index.html"}
    want |= {out / f"learn/{t['slug']}/index.html" for t in TRACKS}
    want |= {out / f"learn/{t['slug']}/{s['slug']}/index.html" for t, s in SERIES}
    want |= {
        out / f"learn/{t['slug']}/{s['slug']}/{folder.name}/index.html"
        for t, s in SERIES
        for m in s["modules"]
        if (folder := lessons.folder(s["folder"], m["number"]))
    }
    want |= {out / "learn/start/index.html", out / "learn/databases/index.html"}  # the guides
    want.add(out / "learn/waitlist/index.html")
    assert set(pages) == want


def test_guides_are_linked_and_show_their_pictures(site):
    """Start here is linked from the home page and every course page, and the database guide's
    screenshots are published next to it."""
    out, _ = site
    assert 'href="/learn/start/"' in (out / "learn/index.html").read_text(encoding="utf-8")
    for _, s in SERIES:
        if s["status"] != "Planned" and lessons.folder(s["folder"], 1):
            page = next((out / "learn").glob(f"*/{s['slug']}/index.html"))
            assert 'href="/learn/start/"' in page.read_text(encoding="utf-8")
    guide = out / "learn/databases/index.html"
    for src in re.findall(r'<img[^>]+src="(images/[^"]+)"', guide.read_text(encoding="utf-8")):
        assert (guide.parent / src).exists(), src


def test_every_internal_link_and_asset_exists(site):
    out, pages = site
    for page in pages:
        html = page.read_text(encoding="utf-8")
        # an unfilled slot of the page template looks like {{title}}; lessons may show "{{" in code
        assert not re.search(r"\{\{[a-z_]+\}\}", html), f"{page}: a template slot was not filled"
        for ref in re.findall(r'(?:href|src)="(/learn/[^"#?]*)', html):
            target = out / ref.lstrip("/")
            if ref.endswith("/"):
                target = target / "index.html"
            assert target.exists(), f"{page.relative_to(out)} -> {ref}"


def test_every_page_links_every_track_and_each_track_its_courses(site):
    out, pages = site
    for page in pages:
        html = page.read_text(encoding="utf-8")
        for t in TRACKS:
            assert f'href="{build.url(CAT, t)}"' in html, (page, t["slug"])
    for t, s in SERIES:
        html = (out / f"learn/{t['slug']}/index.html").read_text(encoding="utf-8")
        assert f'href="{build.url(CAT, t, s)}"' in html, (t["slug"], s["slug"])


def test_stylesheet_address_is_versioned(site):
    out, pages = site
    for page in pages:
        assert re.search(r"learn\.css\?v=[0-9a-f]{10}", page.read_text(encoding="utf-8"))


def test_readmes_follow_the_catalogue():
    for path, text in build.readmes(CAT).items():
        assert path.read_text(encoding="utf-8") == text, path


def test_lesson_pages_show_their_figures_and_further_reading(site):
    out, pages = site
    lesson_pages = [p for p in pages if p.parent.name[:2].isdigit()]
    assert lesson_pages, "no lesson pages were built"
    for page in lesson_pages:
        html = page.read_text(encoding="utf-8")
        assert 'id="further-reading"' in html
        for src in re.findall(r'<img alt="[^"]*" src="(figures/[^"]+)"', html):
            assert (page.parent / src).exists(), (page, src)


def test_big_picture_points_at_real_modules_and_steps():
    for folder, data in build.journeys().items():
        series = [s for _, s in SERIES if s["folder"] == folder]
        assert series, f"journey.json names a course that is not in the catalogue: {folder}"
        count = len(series[0]["modules"])
        steps = data["stages"] + data["lanes"]
        ids = [st["id"] for st in steps]
        assert len(ids) == len(set(ids)), "every step needs its own id"
        for key in ("title", "problem", "question", "intro"):
            assert data[key].strip(), key
        for st in steps:
            for key in ("label", "asks", "answer", "why", "when"):
                assert st[key].strip(), (st["id"], key)
            assert st["how"] and st["modules"], st["id"]
            assert all(1 <= n <= count for n in st["modules"]), (st["id"], st["modules"])
        assert all(st.get("phase") for st in data["stages"]), "every main step has a phase"


def test_every_written_module_appears_in_the_big_picture():
    for folder, data in build.journeys().items():
        series = next(s for _, s in SERIES if s["folder"] == folder)
        covered = {n for st in data["stages"] + data["lanes"] for n in st["modules"]}
        for m in series["modules"]:
            assert m["number"] in covered, f"Module {m['number']} is in no step of the big picture"


def test_big_picture_on_its_course_page_and_lesson_pages(site):
    out, _ = site
    for t, s in SERIES:
        if s["folder"] not in build.journeys():
            continue
        page = (out / f"learn/{t['slug']}/{s['slug']}/index.html").read_text(encoding="utf-8")
        assert 'id="big-picture"' in page and "assets/js/journey.js?v=" in page
        for lesson in sorted((out / f"learn/{t['slug']}/{s['slug']}").glob("*/index.html")):
            assert 'class="fits"' in lesson.read_text(encoding="utf-8"), lesson


def test_waitlist_form_asks_what_it_should(site):
    """The waitlist page has the required questions, the optional ones, consent and a spam trap,
    and every waitlist button on the site points to it."""
    out, _ = site
    page = (out / "learn/waitlist/index.html").read_text(encoding="utf-8")
    for name in ("first_name", "email", "courses", "country", "role", "position", "field_of_study",
                 "python_level", "heard_from", "goals", "consent", "website"):  # fmt: skip
        assert f'name="{name}"' in page, name
    assert "privacy-policy" in page and 'list="countries"' in page
    home = (out / "learn/index.html").read_text(encoding="utf-8")
    assert (
        'href="/learn/waitlist/"' in home and "mailto:contact@monstrous.com.ng?subject" not in home
    )


def test_every_page_has_a_way_back_to_the_top(site):
    """Every page has the back-to-top link to the header (#top) and loads its script."""
    _, pages = site
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert 'class="to-top" href="#top"' in html and 'id="top"' in html, page
        assert "assets/js/totop.js?v=" in html, page


def test_every_lesson_can_be_rated(site):
    """Every lesson page ends with the rating box, naming its own module, and asks for a star."""
    out, pages = site
    lessons = [p for p in pages if p.parent.parent.name == "series-1"]
    assert lessons
    for page in lessons:
        html = page.read_text(encoding="utf-8")
        module = page.parent.relative_to(out / "learn").as_posix()
        assert f'data-module="{module}"' in html, page
        assert 'name="rating"' in html and "github.com/David-Alobo/monstrous-learn" in html, page


# made-up secrets that lessons show on purpose, to teach how to keep real ones out of logs
TEACHING_FAKES = ("abc123", "hunter2", "s3cret")


def test_no_private_information_in_the_published_site(site):
    """Nothing private reaches the public pages, scripts or styles: no passwords or keys, no
    personal or university contact details, no test accounts, no internal addresses."""
    out, _ = site
    forbidden = {
        "a password or secret": (
            r"(?i)(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{6,}"
        ),
        "an application password or WP login": r"WP_AUTH|application-password|wp-login\.php",
        "a private key": r"BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY",
        "a university email or ID": r"(?i)@student\.gla\.ac\.uk|\b\d{7}[A-Z]@",
        "a phone number": r"\+44\s?\d{3,4}\s?\d{3}\s?\d{3,4}|\+234\s?\d{3}\s?\d{3}\s?\d{4}",
        # a page built against a test server (the guides may still explain what 127.0.0.1 means)
        "a test server's address": r"https?://(127\.0\.0\.1|localhost):80[0-9]{2}",
        "a webhook or admin address": r"fluentcrm=1|hash=[0-9a-f]{8,}|/wp-admin/",
    }
    for path in (out / "learn").rglob("*"):
        if path.suffix not in {".html", ".js", ".css", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for what, pattern in forbidden.items():
            for found in re.finditer(pattern, text):
                if found.group(0).endswith(TEACHING_FAKES):
                    continue  # a made-up value a lesson uses on purpose (Module 14's log cleaning)
                raise AssertionError(f"{path}: {what}: {found.group(0)}")
        # ours, and made-up examples at the domains reserved for examples (example.com/.org/.net)
        allowed = {"contact@monstrous.com.ng"}
        emails = {e.rstrip(".") for e in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)} - allowed
        real = {e for e in emails if not re.search(r"example\.(com|org|net)$", e)}
        real = {e for e in real if e.split("@")[0] not in TEACHING_FAKES}
        assert not {e for e in real if not e.endswith((".png", ".svg", ".js"))}, (path, real)
