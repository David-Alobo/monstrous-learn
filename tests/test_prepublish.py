"""The pre-publication check catches what it must, and passes ordinary course text."""

import importlib.util
import re
from pathlib import Path

spec = importlib.util.spec_from_file_location("prepublish", Path("tools/prepublish.py"))
prepublish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepublish)


def flagged(line: str) -> list[str]:
    return [what for what, p in prepublish.FORBIDDEN.items() if re.search(p, line, re.M)]


def test_catches_what_must_not_be_published():
    assert flagged("password = hunter2-secret")
    assert flagged("API_KEY: sk_live_abcdefgh12345")
    assert flagged("token ghp_" + "a" * 36)
    assert flagged("-----BEGIN OPENSSH PRIVATE KEY-----")
    assert flagged("WP_AUTH=admin:abcd efgh")
    assert flagged("write to someone@student.gla.ac.uk")
    assert flagged("call +44 7700 900123")
    assert flagged("## Answer key")
    for name in ["homework/answers.md", "answer_key.json", ".env", "library.sdf", "zinc.parquet"]:
        assert re.search(prepublish.FORBIDDEN_FILES, name), name


def test_passes_ordinary_course_text():
    for line in [
        "toc = [(t['id'], t['name']) for t in md.toc_tokens]",
        "Answer each question by running code like the code in the lesson.",
        "print(Chem.MolToInchiKey(aspirin))",
        "Write to contact@monstrous.com.ng",
    ]:
        assert not flagged(line), line
    for name in ["lesson.md", "homework.md", "figures/smarts-acid.svg"]:
        assert not re.search(prepublish.FORBIDDEN_FILES, name), name
