"""Record the real ChEMBL and PubChem responses that Module 11 replays (recorded/*.json).

Usage (from the series folder; needs the internet, takes about a minute):
    uv run python 11-incremental-ingestion/record.py

The lesson runs offline and gives the same output every time because it reads these recordings
instead of calling the web services ("record and replay"). This script makes exactly the requests
the lesson makes, politely (a descriptive User-Agent, timeouts, at most 2 requests per second,
retries with back-off on 429 and 5xx), and saves each response with its URL. Run it again to
refresh the recordings; the numbers in the lesson will then change with the data, so rerun
`lessonkit.py 11-incremental-ingestion --write` and reread the lesson's text against them.

ChEMBL data: CC BY-SA 3.0 (https://www.ebi.ac.uk/chembl/). PubChem data: NCBI places no
restrictions on its use (https://www.ncbi.nlm.nih.gov/home/about/policies/).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

log = logging.getLogger(__name__)

HERE = Path(__file__).parent
RECORDED = HERE / "recorded"
CHEMBL_HOST = "https://www.ebi.ac.uk"
CHEMBL_ACTIVITY = f"{CHEMBL_HOST}/chembl/api/data/activity.json"
PUBCHEM_PROPERTIES = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids}/property/{props}/JSON"
)

# the same constants as the lesson (changing any of them changes the recorded URLs)
PAGE_SIZE = 100
QUERY = {
    "target_chembl_id": "CHEMBL3529",  # IKK-epsilon
    "standard_type": "IC50",
    "pchembl_value__isnull": "false",
    "order_by": "activity_id",
    "only": "activity_id,molecule_chembl_id,standard_type,standard_relation,standard_value,"
    "standard_units,pchembl_value,document_chembl_id",
    "limit": str(PAGE_SIZE),
}
FIRST_RUN_CUTOFF = 18811464  # the first run sees only activities up to this id
BACKFILL = (16279324, 16354699)  # the range the lesson backfills
PROPERTIES = "Title,MolecularFormula,MolecularWeight,SMILES,InChIKey"
CIDS_FIRST = [2244, 2519, 3672, 1983, 156391, 3033, 4091, 60823, 4594, 33613]
CIDS_SECOND = [*CIDS_FIRST, 54678486, 5090, 2662, 999999999]
CHUNK_SIZE = 5
USER_AGENT = "monstrous-learn-course/1.0 (teaching example; record-and-replay recorder)"
TRANSIENT = {429, 500, 502, 503, 504}
# the recorder's own politeness: slower and more patient than the lesson, as it runs rarely
MIN_INTERVAL_S = 0.5  # at most 2 requests per second
TIMEOUT = (10, 120)  # seconds to connect, seconds to wait for the answer
MAX_ATTEMPTS = 10  # requests in all before a transient failure is given up
FIRST_WAIT_S, MAX_WAIT_S = 2, 120  # back-off: first ceiling and largest ceiling, in seconds


class TransientHTTPError(Exception):
    """A response worth retrying: rate limited or a server error."""


def canonical_url(url: str, params: dict[str, str] | None = None) -> str:
    """One spelling for a request: absolute URL with its query parameters sorted.

    Args:
        url: The URL, absolute or a path on the ChEMBL host (as in ChEMBL's `next` links).
        params: Extra query parameters.

    Returns:
        The canonical URL.
    """
    parts = urlsplit(urljoin(CHEMBL_HOST, url))
    query = sorted(parse_qsl(parts.query) + [(k, str(v)) for k, v in (params or {}).items()])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def recording_name(url: str) -> str:
    """The file a canonical URL is recorded in.

    Args:
        url: A canonical URL.

    Returns:
        A short file name: the service and a hash of the URL.
    """
    service = "chembl" if "ebi.ac.uk" in url else "pubchem"
    return f"{service}-{hashlib.sha256(url.encode()).hexdigest()[:12]}.json"


_last_request = [0.0]


@retry(
    retry=retry_if_exception_type((TransientHTTPError, requests.ConnectionError, requests.Timeout)),
    stop=stop_after_attempt(MAX_ATTEMPTS),
    wait=wait_random_exponential(multiplier=FIRST_WAIT_S, max=MAX_WAIT_S),
    reraise=True,
)
def get(url: str) -> tuple[int, dict]:
    """GET a canonical URL politely, retrying transient failures.

    Args:
        url: A canonical URL.

    Returns:
        The HTTP status and the JSON body.
    """
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if response.status_code in TRANSIENT:
        raise TransientHTTPError(f"HTTP {response.status_code} for {url}")
    return response.status_code, response.json()


def record(url: str, params: dict[str, str] | None = None) -> dict:
    """Fetch one request and save it under recorded/.

    Args:
        url: The URL.
        params: Its query parameters.

    Returns:
        The JSON body.
    """
    url = canonical_url(url, params)
    status, body = get(url)
    entry = {"url": url, "status": status, "recorded": datetime.date.today().isoformat(),
             "body": body}  # fmt: skip
    path = RECORDED / recording_name(url)
    path.write_text(json.dumps(entry, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("%s  HTTP %d  %s", path.name, status, url[:110])
    return body


def walk(params: dict[str, str]) -> list[dict]:
    """Record every page of a ChEMBL activity query, following `page_meta.next`.

    Args:
        params: The query.

    Returns:
        All its activities.
    """
    records, url, extra = [], CHEMBL_ACTIVITY, params
    while url:
        page = record(url, extra)
        records += page["activities"]
        url, extra = page["page_meta"]["next"], None
    return records


def main() -> None:
    """Record every response the lesson replays."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    RECORDED.mkdir(exist_ok=True)
    for old in RECORDED.glob("*.json"):
        old.unlink()
    first = walk({**QUERY, "activity_id__gt": "0", "activity_id__lte": str(FIRST_RUN_CUTOFF)})
    mark = max(a["activity_id"] for a in first)
    second = walk({**QUERY, "activity_id__gt": str(mark)})
    mark = max([mark] + [a["activity_id"] for a in second])
    walk({**QUERY, "activity_id__gt": str(mark)})  # the third run: nothing new
    walk({**QUERY, "activity_id__gte": str(BACKFILL[0]), "activity_id__lte": str(BACKFILL[1])})
    seen: set[int] = set()
    for cids in (CIDS_FIRST, CIDS_SECOND):
        new = [c for c in cids if c not in seen]
        for i in range(0, len(new), CHUNK_SIZE):
            chunk = new[i : i + CHUNK_SIZE]
            record(PUBCHEM_PROPERTIES.format(cids=",".join(map(str, chunk)), props=PROPERTIES))
        seen.update(cids)
    total = sum(p.stat().st_size for p in RECORDED.glob("*.json"))
    log.info("%d recordings, %.0f KiB", len(list(RECORDED.glob("*.json"))), total / 1024)


if __name__ == "__main__":
    main()
