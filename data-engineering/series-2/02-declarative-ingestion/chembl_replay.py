"""ChEMBL's answers for this module: replayed from recorded/, called live, or recorded anew.

The lesson's dlt pipeline talks to ChEMBL through a requests session made here. By default the
session replays the answers recorded in recorded/, so the lesson gives the same results on every
computer, works offline and does not load ChEMBL's servers. Set the environment variable
CHEMBL_MODE to choose:

    CHEMBL_MODE=replay   (the default) answer every request from recorded/
    CHEMBL_MODE=live     call ChEMBL for real (the results will differ as ChEMBL grows)
    CHEMBL_MODE=record   call ChEMBL and save every answer in recorded/, replacing what was there

To record again, from the series folder:
    CHEMBL_MODE=record uv run python lessonkit.py 02-declarative-ingestion

ChEMBL data is licensed under CC BY-SA 3.0 (https://www.ebi.ac.uk/chembl/); the recorded answers
are shared under the same licence.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests

RECORDED = Path(__file__).parent / "recorded"


def key(url: str) -> str:
    """The file a request's answer is recorded under: its path and sorted query, hashed.

    Args:
        url: The request's full address.

    Returns:
        A file name such as "chembl-1a2b3c4d5e6f.json".
    """
    parts = urlsplit(url)
    canonical = parts.path + "?" + urlencode(sorted(parse_qsl(parts.query)))
    return "chembl-" + hashlib.sha256(canonical.encode()).hexdigest()[:12] + ".json"


class _Recording(requests.Session):
    """A session that calls ChEMBL and saves every answer in recorded/."""

    def send(self, request: requests.PreparedRequest, **kwargs) -> requests.Response:
        """Send a request for real and keep a copy of its answer.

        Args:
            request: The prepared request.
            **kwargs: Passed on to requests.

        Returns:
            The answer.
        """
        response = super().send(request, **kwargs)
        RECORDED.mkdir(exist_ok=True)
        (RECORDED / key(request.url)).write_text(response.text, encoding="utf-8")
        return response


class _Replay(requests.adapters.BaseAdapter):
    """Answers every request from recorded/, without the network."""

    def send(self, request: requests.PreparedRequest, **kwargs) -> requests.Response:
        """Answer a request from its recorded file (404 if it was never recorded).

        Args:
            request: The prepared request.
            **kwargs: Ignored (timeouts and the like have no meaning here).

        Returns:
            The recorded answer.
        """
        path = RECORDED / key(request.url)
        response = requests.Response()
        response.status_code = 200 if path.exists() else 404
        response._content = path.read_bytes() if path.exists() else b'{"error": "not recorded"}'
        response.headers["Content-Type"] = "application/json"
        response.url, response.request = request.url, request
        return response

    def close(self) -> None:
        """Nothing to close."""


def session() -> requests.Session:
    """A session for ChEMBL that replays, calls live or records, as CHEMBL_MODE says.

    Returns:
        The session to give to dlt's REST client.

    Raises:
        ValueError: If CHEMBL_MODE is not replay, live or record.
    """
    mode = os.environ.get("CHEMBL_MODE", "replay")
    if mode == "record":
        return _Recording()
    s = requests.Session()
    if mode == "replay":
        s.mount("https://", _Replay())
    elif mode != "live":
        raise ValueError(f"CHEMBL_MODE must be replay, live or record, not {mode!r}")
    return s
