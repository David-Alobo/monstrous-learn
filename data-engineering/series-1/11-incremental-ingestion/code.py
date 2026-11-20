"""Incremental ingestion from ChEMBL and PubChem: the code of the lesson, in order.

Fetch only what changed from public chemistry APIs, page through them politely within their limits, check every response against a model, load idempotently with a high-water mark, run backfills safely, and keep the licence with the data.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/11-incremental-ingestion/
Run it from anywhere, e.g. from the series folder: uv run python 11-incremental-ingestion/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]
import hashlib
import json
import math
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import duckdb
import pandas as pd
import requests

LIVE = False  # False: replay the recorded responses. True: call ChEMBL and PubChem for real.
RECORDED = Path("recorded")
CACHE = Path("work") / "http-cache"  # live responses are kept here, so a rerun asks again for nothing
Path("work").mkdir(exist_ok=True)

# ---- 2. A polite client ----
USER_AGENT = "chem-ingest-tutorial/1.0 (mailto:you@example.org)"  # put your own contact here
TIMEOUT = (10, 60)  # seconds to connect, seconds to wait for the answer


class RateLimiter:
    """Allow at most `per_second` requests per second, by waiting before a request when needed."""

    def __init__(self, per_second: float, clock=time.monotonic, sleep=time.sleep):
        self.interval = 1 / per_second
        self.clock = clock
        self.sleep = sleep
        self.next_allowed = -math.inf

    def wait(self) -> None:
        """Wait until the next request is allowed, then reserve the slot after it."""
        now = self.clock()
        if now < self.next_allowed:
            self.sleep(self.next_allowed - now)
            now = self.next_allowed
        self.next_allowed = now + self.interval


class PretendClock:
    """A clock that only moves when something sleeps: for showing waits without waiting."""

    def __init__(self):
        self.now = 0.0

    def time(self) -> float:
        """The current pretend time, in seconds."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Move the pretend time on."""
        self.now += seconds


clock = PretendClock()
limiter = RateLimiter(per_second=5, clock=clock.time, sleep=clock.sleep)
sent = []
for _ in range(12):
    limiter.wait()
    sent.append(round(clock.now, 1))
print("12 requests sent at (s):", sent)
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_random_exponential

TRANSIENT_STATUS = {429, 500, 502, 503, 504}
SESSION = requests.Session()
LIMITERS = {"www.ebi.ac.uk": RateLimiter(2), "pubchem.ncbi.nlm.nih.gov": RateLimiter(5)}


class TransientHTTPError(Exception):
    """A response worth retrying: rate limited, or the server failed."""


def polite_get(url: str, session=SESSION, limiter=None, sleep=time.sleep) -> dict:
    """GET a URL politely and return its JSON, retrying transient failures with back-off.

    Args:
        url: The full URL.
        session: The HTTP session (a requests.Session in real use).
        limiter: The rate limiter for the URL's service (by default, the one for its host).
        sleep: How to wait between retries.

    Returns:
        The response's JSON.

    Raises:
        requests.HTTPError: For a permanent failure (4xx other than 429), at once.
        TransientHTTPError: If every attempt failed.
    """
    limiter = limiter or LIMITERS[urlsplit(url).netloc]
    retrying = Retrying(
        retry=retry_if_exception_type(
            (TransientHTTPError, requests.ConnectionError, requests.Timeout)
        ),
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(multiplier=1, max=60),
        sleep=sleep,
        reraise=True,
    )
    for attempt in retrying:
        with attempt:
            limiter.wait()
            response = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            if response.status_code in TRANSIENT_STATUS:
                raise TransientHTTPError(f"HTTP {response.status_code} from {urlsplit(url).netloc}")
            response.raise_for_status()  # any other 4xx or 5xx: permanent, raised at once
            return response.json()


class PretendResponse:
    """Just enough of a requests.Response for polite_get."""

    def __init__(self, status_code: int):
        self.status_code = status_code

    def json(self) -> dict:
        """The body."""
        return {"answer": "the data"}

    def raise_for_status(self) -> None:
        """Raise for 4xx and 5xx, like requests does."""
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error")


class PretendServer:
    """Answers each request with the next status code from a list."""

    def __init__(self, statuses: list[int]):
        self.statuses = list(statuses)
        self.requests = 0

    def get(self, url, headers, timeout):
        """Answer one request."""
        self.requests += 1
        return PretendResponse(self.statuses.pop(0))


quiet = RateLimiter(5, clock=clock.time, sleep=clock.sleep)
server = PretendServer([503, 429, 200])
answer = polite_get("https://example.org/x", server, quiet, sleep=clock.sleep)
print(f"{answer} after {server.requests} requests")

server = PretendServer([404])
try:
    polite_get("https://example.org/x", server, quiet, sleep=clock.sleep)
except requests.HTTPError as err:
    print(f"not retried ({server.requests} request): {err}")

# ---- 3. Record and replay ----
CHEMBL_HOST = "https://www.ebi.ac.uk"


def canonical_url(url: str, params: dict | None = None) -> str:
    """One spelling for a request: an absolute URL with its query parameters sorted.

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
    """The file a canonical URL is recorded under: the service and a hash of the URL."""
    service = "chembl" if "ebi.ac.uk" in url else "pubchem"
    return f"{service}-{hashlib.sha256(url.encode()).hexdigest()[:12]}.json"


requests_made = []


def fetch_json(url: str, params: dict | None = None) -> dict:
    """The JSON for a request: replayed from recorded/, or fetched live and cached on disk.

    Args:
        url: The URL.
        params: Its query parameters.

    Returns:
        The response's JSON, the same in both modes.
    """
    url = canonical_url(url, params)
    requests_made.append(url)
    name = recording_name(url)
    if not LIVE:
        path = RECORDED / name
        if not path.exists():
            raise FileNotFoundError(f"{url} was never recorded: run record.py")
        return json.loads(path.read_text(encoding="utf-8"))["body"]
    cached = CACHE / name
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))["body"]
    body = polite_get(url)
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = cached.with_name(cached.name + ".tmp")  # an atomic write, as in Module 10
    tmp.write_text(json.dumps({"url": url, "body": body}), encoding="utf-8")
    tmp.replace(cached)
    return body


recordings = sorted(RECORDED.glob("*.json"))
size_kib = sum(p.stat().st_size for p in recordings) / 1024
print(f"{len(recordings)} recorded responses, {size_kib:.0f} KiB in all")

# ---- 4. Pages: limit, offset and next ----
CHEMBL_ACTIVITY = f"{CHEMBL_HOST}/chembl/api/data/activity.json"
QUERY = {
    "target_chembl_id": "CHEMBL3529",  # IKK-epsilon
    "standard_type": "IC50",
    "pchembl_value__isnull": "false",
    "order_by": "activity_id",
    "only": "activity_id,molecule_chembl_id,standard_type,standard_relation,standard_value,"
    "standard_units,pchembl_value,document_chembl_id",
    "limit": "100",
}
FIRST_RUN_CUTOFF = 18811464  # explained in section 6

page = fetch_json(CHEMBL_ACTIVITY,
                  {**QUERY, "activity_id__gt": "0", "activity_id__lte": str(FIRST_RUN_CUTOFF)})
print(json.dumps(page["page_meta"], indent=1))
print(json.dumps(page["activities"][0], indent=1))
def pages(params: dict):
    """Every page of a ChEMBL activity query, following page_meta.next.

    Args:
        params: The query.

    Yields:
        One page (the parsed JSON) at a time.
    """
    url, extra = CHEMBL_ACTIVITY, params
    while url:
        page = fetch_json(url, extra)
        yield page
        url, extra = page["page_meta"]["next"], None


for each in pages({**QUERY, "activity_id__gt": "0", "activity_id__lte": str(FIRST_RUN_CUTOFF)}):
    meta = each["page_meta"]
    print(f"offset {meta['offset']:>3}: {len(each['activities'])} records, next page: "
          f"{'yes' if meta['next'] else 'none'}")

# ---- 5. Check every record at the door ----
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class Activity(BaseModel):
    """One ChEMBL bioactivity record, as this pipeline needs it."""

    model_config = ConfigDict(extra="ignore", frozen=True)  # new fields are ignored, not errors

    activity_id: int = Field(gt=0)
    molecule_chembl_id: str = Field(pattern=r"^CHEMBL\d+$")
    document_chembl_id: str = Field(pattern=r"^CHEMBL\d+$")
    standard_type: str
    standard_relation: str | None
    standard_value: float | None = Field(gt=0)
    standard_units: str | None
    pchembl_value: float | None = Field(default=None, ge=0, le=15)

    @model_validator(mode="after")
    def pchembl_agrees_with_value(self) -> "Activity":
        """pChEMBL is -log10(molar value): for nM values it must be 9 - log10(value)."""
        known = self.pchembl_value is not None and self.standard_value is not None
        if known and self.standard_units == "nM":
            expected = 9 - math.log10(self.standard_value)
            if abs(expected - self.pchembl_value) > 0.01:
                raise ValueError(f"pchembl_value {self.pchembl_value} but the value gives "
                                 f"{expected:.2f}")
        return self


record = page["activities"][0]
activity = Activity.model_validate(record)
print(activity)
broken = {
    "value is not a number": {**record, "standard_value": "n/a"},
    "field renamed by the API": {k.replace("molecule_chembl_id", "molecule_id"): v
                                 for k, v in record.items()},
    "pChEMBL disagrees": {**record, "pchembl_value": "8.10"},
}
for label, bad in broken.items():
    try:
        Activity.model_validate(bad)
    except ValidationError as err:
        problem = err.errors()[0]
        print(f"{label}: {'.'.join(map(str, problem['loc'])) or 'record'}: {problem['msg']}")
def validate_page(page: dict) -> list[Activity]:
    """Every activity of a page, checked; any invalid record stops the run before storing."""
    return [Activity.model_validate(record) for record in page["activities"]]

# ---- 6. Incremental loads with a high-water mark ----
SOURCE_CHEMBL = "ChEMBL (CC BY-SA 3.0)"

db_path = Path("work") / "ingest.duckdb"
db_path.unlink(missing_ok=True)
con = duckdb.connect(str(db_path))
con.execute("""
    CREATE TABLE activities (
        activity_id BIGINT PRIMARY KEY, molecule_chembl_id VARCHAR, document_chembl_id VARCHAR,
        standard_type VARCHAR, standard_relation VARCHAR, standard_value DOUBLE,
        standard_units VARCHAR, pchembl_value DOUBLE, source VARCHAR);
    CREATE TABLE load_state (source VARCHAR PRIMARY KEY, high_water_mark BIGINT);
""")
UPSERT = """
    INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (activity_id) DO UPDATE SET
        molecule_chembl_id = excluded.molecule_chembl_id,
        document_chembl_id = excluded.document_chembl_id,
        standard_type = excluded.standard_type, standard_relation = excluded.standard_relation,
        standard_value = excluded.standard_value, standard_units = excluded.standard_units,
        pchembl_value = excluded.pchembl_value, source = excluded.source
"""


def upsert(con, activities: list[Activity]) -> None:
    """Insert new activities and overwrite ones already stored (idempotent)."""
    rows = [(a.activity_id, a.molecule_chembl_id, a.document_chembl_id, a.standard_type,
             a.standard_relation, a.standard_value, a.standard_units, a.pchembl_value,
             SOURCE_CHEMBL) for a in activities]  # fmt: skip
    if rows:
        con.executemany(UPSERT, rows)


def high_water_mark(con) -> int:
    """The largest activity_id loaded so far (0 before the first run)."""
    row = con.execute("SELECT high_water_mark FROM load_state WHERE source = 'chembl'").fetchone()
    return row[0] if row else 0


def load_increment(con, until: int | None = None) -> str:
    """Fetch and store every activity above the high-water mark, page by page.

    Args:
        con: The DuckDB connection.
        until: Only for the lesson's first run: ignore activities above this id.

    Returns:
        A one-line report of the run.
    """
    start = high_water_mark(con)
    params = {**QUERY, "activity_id__gt": str(start)}
    if until is not None:
        params["activity_id__lte"] = str(until)
    n_pages = n_records = 0
    for page in pages(params):
        activities = validate_page(page)
        mark = max([high_water_mark(con)] + [a.activity_id for a in activities])
        con.begin()  # the page's rows and the new mark: together or not at all
        upsert(con, activities)
        con.execute("INSERT OR REPLACE INTO load_state VALUES ('chembl', ?)", [mark])
        con.commit()
        n_pages, n_records = n_pages + 1, n_records + len(activities)
    stored = con.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    return (f"mark {start} -> {high_water_mark(con)}; pages: {n_pages}, records fetched: "
            f"{n_records}; stored: {stored}")
print("run 1:", load_increment(con, until=FIRST_RUN_CUTOFF))
print("run 2:", load_increment(con))
print("run 3:", load_increment(con))
before = con.execute("SELECT COUNT(*), SUM(pchembl_value) FROM activities").fetchone()
again = fetch_json(CHEMBL_ACTIVITY,
                   {**QUERY, "activity_id__gt": "0", "activity_id__lte": str(FIRST_RUN_CUTOFF)})
upsert(con, validate_page(again))
after = con.execute("SELECT COUNT(*), SUM(pchembl_value) FROM activities").fetchone()
print(f"rows and pChEMBL total before: {before[0]}, {before[1]:.2f}; after: {after[0]}, "
      f"{after[1]:.2f}; unchanged: {before == after}")

# ---- 7. Backfills ----
BACKFILL = (16279324, 16354699)  # the range of activity ids to fetch again


def backfill(con, first_id: int, last_id: int) -> int:
    """Re-fetch and upsert every activity with an id in [first_id, last_id]; the mark is unchanged.

    Returns:
        How many records were fetched.
    """
    params = {**QUERY, "activity_id__gte": str(first_id), "activity_id__lte": str(last_id)}
    n_records = 0
    for page in pages(params):
        activities = validate_page(page)
        upsert(con, activities)
        n_records += len(activities)
    return n_records


con.execute("UPDATE activities SET pchembl_value = NULL WHERE activity_id BETWEEN ? AND ?",
            list(BACKFILL))  # the pretend bug
missing = "SELECT COUNT(*) FROM activities WHERE pchembl_value IS NULL"
print("records missing pChEMBL before the backfill:", con.execute(missing).fetchone()[0])
mark = high_water_mark(con)
print("records re-fetched:", backfill(con, *BACKFILL))
print("records missing pChEMBL after:", con.execute(missing).fetchone()[0])
print("high-water mark unchanged:", high_water_mark(con) == mark)
print("rows:", con.execute("SELECT COUNT(*) FROM activities").fetchone()[0])

# ---- 8. PubChem: properties for a list of compounds ----
PUBCHEM_PROPERTIES = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids}"
                      "/property/Title,MolecularFormula,MolecularWeight,SMILES,InChIKey/JSON")
CHUNK = 5
SOURCE_PUBCHEM = "PubChem (NCBI: no restrictions on use)"


class Compound(BaseModel):
    """One row of a PubChem property table."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    cid: int = Field(alias="CID", gt=0)
    title: str = Field(alias="Title")
    formula: str = Field(alias="MolecularFormula")
    mol_wt: float = Field(alias="MolecularWeight", gt=0)  # sent as text, e.g. "180.16"
    smiles: str = Field(alias="SMILES")
    inchikey: str = Field(alias="InChIKey", pattern=r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


con.execute("""
    CREATE TABLE compounds (cid BIGINT PRIMARY KEY, title VARCHAR, formula VARCHAR,
        mol_wt DOUBLE, smiles VARCHAR, inchikey VARCHAR, source VARCHAR);
    CREATE TABLE compound_rejects (cid BIGINT PRIMARY KEY, reason VARCHAR);
""")


def load_compounds(con, cids: list[int]) -> str:
    """Fetch properties for the CIDs not stored yet, in chunks; bad records go to rejects.

    Returns:
        A one-line report.
    """
    stored = {row[0] for row in con.execute("SELECT cid FROM compounds").fetchall()}
    new = [cid for cid in cids if cid not in stored]
    n_requests = n_rejected = 0
    for i in range(0, len(new), CHUNK):
        chunk = new[i : i + CHUNK]
        table = fetch_json(PUBCHEM_PROPERTIES.format(cids=",".join(map(str, chunk))))
        n_requests += 1
        for record in table["PropertyTable"]["Properties"]:  # a KeyError here: the API changed
            try:
                c = Compound.model_validate(record)
            except ValidationError as err:
                reason = f"{err.error_count()} problems, e.g. {err.errors()[0]['loc'][0]} missing"
                con.execute("INSERT OR REPLACE INTO compound_rejects VALUES (?, ?)",
                            [record.get("CID"), reason])
                n_rejected += 1
                continue
            con.execute("INSERT OR REPLACE INTO compounds VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [c.cid, c.title, c.formula, c.mol_wt, c.smiles, c.inchikey,
                         SOURCE_PUBCHEM])
    total = con.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    return (f"CIDs asked for: {len(cids)}, not yet stored: {len(new)}; requests: {n_requests}, "
            f"rejected: {n_rejected}; stored: {total}")


CIDS_FIRST = [2244, 2519, 3672, 1983, 156391, 3033, 4091, 60823, 4594, 33613]
CIDS_SECOND = [*CIDS_FIRST, 54678486, 5090, 2662, 999999999]
print("run 1:", load_compounds(con, CIDS_FIRST))
print("run 2:", load_compounds(con, CIDS_SECOND))
print(con.execute("SELECT * FROM compound_rejects").df().to_string(index=False))
print(con.execute("SELECT cid, title, formula, mol_wt FROM compounds ORDER BY cid LIMIT 5")
      .df().to_string(index=False))

# ---- 9. Keeping the source with the data, and writing Parquet ----
for table in ("activities", "compounds"):
    path = Path("work") / f"{table}.parquet"
    con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT parquet)")
    check = con.execute(f"SELECT COUNT(*), ANY_VALUE(source) FROM '{path.as_posix()}'").fetchone()
    print(f"{path.name}: {check[0]} rows, source: {check[1]}")
con.close()
print(f"requests made in this lesson: {len(requests_made)}, all replayed: {not LIVE}")
