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
    assert set(pages) == want


def test_every_internal_link_and_asset_exists(site):
    out, pages = site
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert "{{" not in html, f"{page}: a template slot was not filled"
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
