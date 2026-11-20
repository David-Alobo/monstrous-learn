"""The course pages: the catalogue is complete, every page is built, and every link inside the
courses leads to a page that exists."""

import re
from pathlib import Path

import pytest

from shared.site import build

CAT = build.load()


def test_catalogue_is_complete():
    slugs = [s["slug"] for s in CAT["series"]]
    assert len(slugs) == len(set(slugs))
    for k, s in enumerate(CAT["series"], start=1):
        assert s["number"] == k
        assert Path(s["folder"]).is_dir(), f"{s['folder']} is missing"
        assert [m["number"] for m in s["modules"]] == list(range(1, len(s["modules"]) + 1))
        for key in ("title", "tagline", "status", "level", "summary"):
            assert s[key].strip(), (s["slug"], key)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    return out, build.build(out)


def test_one_page_per_course_and_an_introduction(site):
    out, pages = site
    want = {out / "learn/index.html"} | {
        out / f"learn/{s['slug']}/index.html" for s in CAT["series"]
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


def test_every_page_links_every_course(site):
    out, pages = site
    for page in pages:
        html = page.read_text(encoding="utf-8")
        for s in CAT["series"]:
            assert f'href="/learn/{s["slug"]}/"' in html, (page, s["slug"])


def test_stylesheet_address_is_versioned(site):
    out, pages = site
    for page in pages:
        assert re.search(r"learn\.css\?v=[0-9a-f]{10}", page.read_text(encoding="utf-8"))
