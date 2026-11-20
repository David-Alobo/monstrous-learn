"""The course pages: the catalogue is complete, every page is built, and every link inside the
courses leads to a page that exists."""

import re

import pytest

from shared.site import build

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


def test_every_page_links_every_track_and_course(site):
    out, pages = site
    for page in pages:
        html = page.read_text(encoding="utf-8")
        for t in TRACKS:
            assert f'href="{build.url(CAT, t)}"' in html, (page, t["slug"])
        for t, s in SERIES:
            assert f'href="{build.url(CAT, t, s)}"' in html, (page, s["slug"])


def test_stylesheet_address_is_versioned(site):
    out, pages = site
    for page in pages:
        assert re.search(r"learn\.css\?v=[0-9a-f]{10}", page.read_text(encoding="utf-8"))


def test_readmes_follow_the_catalogue():
    for path, text in build.readmes(CAT).items():
        assert path.read_text(encoding="utf-8") == text, path
