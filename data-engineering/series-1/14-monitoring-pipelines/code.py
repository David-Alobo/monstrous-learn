"""Monitoring pipelines: the code of the lesson, in order.

Structured logs, a run history, counts that must reconcile, freshness, drift in molecular properties and alerts, so a pipeline tells you when it goes wrong.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-1/14-monitoring-pipelines/
Run it from anywhere, e.g. from the series folder: uv run python 14-monitoring-pipelines/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]

# ---- 1. What monitoring is for ----
from pathlib import Path

import chemlib
import pandas as pd
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")  # we record RDKit's failures ourselves, as quarantine reasons
Path("work").mkdir(exist_ok=True)

ALLOWED = {"C", "H", "N", "O", "S", "F", "Cl", "Br"}


def check(smiles):
    """Read one record and say why it cannot be used.

    Args:
        smiles: The record's SMILES.

    Returns:
        The molecule (None if rejected) and the quarantine reason ("" if accepted).
    """
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        return None, "unreadable"
    try:
        Chem.SanitizeMol(mol)
    except Chem.MolSanitizeException:
        return None, "impossible valence"
    if len(Chem.GetMolFrags(mol)) > 1:
        return None, "more than one component"
    if {atom.GetSymbol() for atom in mol.GetAtoms()} - ALLOWED:
        return None, "element not allowed"
    return mol, ""


tonight = chemlib.add_defects(chemlib.library(1500, seed=101), rate=0.04, seed=1)
reasons = pd.Series([check(smiles)[1] for smiles in tonight["smiles"]])
print(len(tonight), "records tonight")
print(reasons.replace("", "accepted").value_counts().to_string())

# ---- 2. Structured logs ----
import json
import logging
import re
from datetime import datetime, timedelta


class Clock:
    """The time, as the pipeline sees it: set and advanced by hand (an injected clock).

    In production the same interface would return datetime.now(timezone.utc).
    """

    def __init__(self, start):
        self.time = start

    def now(self):
        """The current time (UTC)."""
        return self.time

    def advance(self, seconds):
        """Move the clock forward."""
        self.time += timedelta(seconds=seconds)


PASSWORD_IN_URL = re.compile(r"(://[^:/@\s]+):[^@\s]+@")
SECRET_FIELD = re.compile(r"((?:password|token|api_key)=)[^&\s\"]+", re.IGNORECASE)


def redact(text):
    """Replace passwords and tokens in a line of text with ***."""
    text = PASSWORD_IN_URL.sub(r"\1:***@", text)
    return SECRET_FIELD.sub(r"\1***", text)


class JsonFormatter(logging.Formatter):
    """Format each log record as one line of JSON, with its fields, and secrets removed."""

    def __init__(self, clock):
        super().__init__()
        self.clock = clock

    def format(self, record):
        """The record as a JSON line."""
        event = {
            "time": self.clock.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        event.update(getattr(record, "fields", {}))
        return redact(json.dumps(event))


class PrintHandler(logging.Handler):
    """Print each log line (so it shows in a notebook; a StreamHandler does this in a script)."""

    def emit(self, record):
        """Print one formatted record."""
        print(self.format(record))


def make_logger(clock, path, screen_level=logging.INFO):
    """A logger that writes JSON lines to a file (everything) and to the screen (from a level).

    Args:
        clock: Where the times come from.
        path: The log file.
        screen_level: The lowest level to print.

    Returns:
        The logger.
    """
    log = logging.getLogger("supplier_pipeline")
    for old in list(log.handlers):  # running this twice must not double every line
        old.close()
        log.removeHandler(old)
    log.setLevel(logging.INFO)
    log.propagate = False
    screen = PrintHandler(level=screen_level)
    file = logging.FileHandler(path, mode="w", encoding="utf-8")
    for handler in (screen, file):
        handler.setFormatter(JsonFormatter(clock))
        log.addHandler(handler)
    return log


clock = Clock(datetime(2027, 1, 4, 2, 0))  # 02:00 UTC on the first night
log = make_logger(clock, Path("work/pipeline.log"))
source = "postgresql://loader:s3cret@chemdb.example.org/suppliers"
log.info("run started", extra={"fields": {"run_id": "run-0001", "source": source}})
log.debug("atom-by-atom detail: below the logger's level, so it is dropped")
clock.advance(4)
n_bad = int((reasons != "").sum())
fields = {"run_id": "run-0001", "step": "validate", "rows_in": len(tonight), "quarantined": n_bad}
log.warning("records quarantined", extra={"fields": fields})
import duckdb

print(
    duckdb.sql(
        "SELECT level, count(*) AS events FROM read_json_auto('work/pipeline.log') "
        "GROUP BY level ORDER BY level"
    ).df().to_string(index=False)
)

# ---- 3. A run history ----
db_path = Path("work/monitoring.duckdb")
db_path.unlink(missing_ok=True)  # start each run of the lesson from an empty history
db = duckdb.connect(str(db_path))
db.execute("""
    CREATE TABLE runs (
        run_id VARCHAR PRIMARY KEY, started TIMESTAMP, finished TIMESTAMP, status VARCHAR,
        rows_in INTEGER, rows_out INTEGER, quarantined INTEGER, duplicates INTEGER,
        message VARCHAR)
""")
db.execute("""
    CREATE TABLE steps (
        run_id VARCHAR, step_no INTEGER, step VARCHAR, started TIMESTAMP, finished TIMESTAMP,
        rows_in INTEGER, rows_out INTEGER, quarantined INTEGER, duplicates INTEGER)
""")
db.execute("CREATE TABLE quarantine (run_id VARCHAR, id VARCHAR, smiles VARCHAR, reason VARCHAR)")
import numpy as np
from rdkit.Chem import Descriptors

NO_ROWS = pd.DataFrame(columns=["id", "smiles", "reason"])
VENDORS = pd.DataFrame(
    {
        "vendor": ["Vendor A", "Vendor B", "Vendor C"],
        "country": ["UK", "Germany", "Ukraine"],
        "lead_time_days": [5, 7, 14],
    }
)


def validate(df):
    """Keep records that pass `check`, with their molecule; quarantine the rest with a reason."""
    checked = [check(smiles) for smiles in df["smiles"]]
    df = df.assign(mol=[mol for mol, _ in checked], reason=[reason for _, reason in checked])
    bad = df["reason"] != ""
    return df[~bad].drop(columns="reason"), df.loc[bad, ["id", "smiles", "reason"]], 0


def deduplicate(df):
    """Keep the first record of each molecule, by InChIKey (as in Module 3)."""
    keys = [Chem.MolToInchiKey(mol) for mol in df["mol"]]
    df = df.assign(inchikey=keys)
    kept = df.drop_duplicates("inchikey")
    return kept, NO_ROWS, len(df) - len(kept)


def enrich(df):
    """Add each vendor's country and lead time; quarantine records from an unknown vendor."""
    merged = df.merge(VENDORS, on="vendor", how="left", indicator=True)
    unknown = merged["_merge"] == "left_only"
    quarantined = merged.loc[unknown, ["id", "smiles"]].assign(reason="unknown vendor")
    return merged[~unknown].drop(columns="_merge"), quarantined, 0


def describe(df):
    """Add molecular weight and logP, the two properties we watch for drift."""
    df = df.assign(
        mw=[round(Descriptors.MolWt(mol), 2) for mol in df["mol"]],
        logp=[round(Descriptors.MolLogP(mol), 2) for mol in df["mol"]],
    )
    return df, NO_ROWS, 0
MS_PER_ROW = {"validate": 0.4, "deduplicate": 0.5, "enrich": 0.05, "describe": 0.3}


def run_step(run_id, step_no, name, func, df, rng):
    """Run one step, move the clock on, and record what the step did.

    Args:
        run_id: The run.
        step_no: The step's position in the run.
        name: The step's name.
        func: The step: a table in; kept rows, quarantined rows and duplicates removed out.
        df: The rows going in.
        rng: The random generator for the simulated duration.

    Returns:
        The rows the step kept.
    """
    started = clock.now()
    kept, quarantined, duplicates = func(df)
    clock.advance(len(df) * MS_PER_ROW[name] / 1000 * rng.uniform(0.8, 1.2))
    db.execute(
        "INSERT INTO steps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [run_id, step_no, name, started, clock.now(), len(df), len(kept), len(quarantined),
         duplicates],
    )
    if len(quarantined):
        db.execute("INSERT INTO quarantine SELECT ?, id, smiles, reason FROM quarantined", [run_id])
    log.info("step finished", extra={"fields": {
        "run_id": run_id, "step": name, "rows_in": len(df), "rows_out": len(kept),
        "quarantined": len(quarantined), "duplicates": duplicates}})
    return kept
STEPS = [("validate", validate), ("deduplicate", deduplicate), ("enrich", enrich),
         ("describe", describe)]


def run_pipeline(run_id, batch, steps, rng):
    """Run every step over a batch and record the run (status, counts) in the run history."""
    db.execute("INSERT INTO runs (run_id, started, status) VALUES (?, ?, 'running')",
               [run_id, clock.now()])
    log.info("run started", extra={"fields": {"run_id": run_id, "rows": len(batch)}})
    df = batch
    for step_no, (name, func) in enumerate(steps, start=1):
        df = run_step(run_id, step_no, name, func, df, rng)
    return df


log = make_logger(clock, Path("work/pipeline.log"), screen_level=logging.WARNING)
published = run_pipeline("run-0001", tonight, STEPS, np.random.default_rng(1))
print(db.sql("SELECT step, rows_in, rows_out, quarantined, duplicates FROM steps "
             "WHERE run_id = 'run-0001' ORDER BY step_no").df().to_string(index=False))

# ---- 4. Counts that reconcile ----
class ReconciliationError(Exception):
    """The counts of a run do not add up: rows were lost or invented."""


def reconcile(run_id):
    """Check that every step's rows are accounted for and that the steps chain together.

    Raises:
        ReconciliationError: listing every step whose counts do not add up.
    """
    problems = db.execute("""
        SELECT step, rows_in, rows_out, quarantined, duplicates,
               rows_in - rows_out - quarantined - duplicates AS unaccounted,
               lag(rows_out) OVER (ORDER BY step_no) AS previous_out
        FROM steps WHERE run_id = ?
        ORDER BY step_no
    """, [run_id]).df()
    lost = problems["unaccounted"] != 0
    broken_chain = problems["previous_out"].notna() & (
        problems["rows_in"] != problems["previous_out"])
    messages = [f"{row.step}: {row.rows_in} in, {row.rows_out} out, {row.quarantined} quarantined,"
                f" {row.duplicates} duplicates, {row.unaccounted} unaccounted for"
                for row in problems[lost | broken_chain].itertuples()]
    if messages:
        raise ReconciliationError("; ".join(messages))


reconcile("run-0001")
print("run-0001 reconciles")
VENDORS_FROM_SPREADSHEET = VENDORS[VENDORS["vendor"] != "Vendor C"]


def enrich_inner_join(df):
    """The buggy version: merge's default inner join drops rows from vendors not in the table."""
    return df.merge(VENDORS_FROM_SPREADSHEET, on="vendor"), NO_ROWS, 0


buggy_steps = [("validate", validate), ("deduplicate", deduplicate),
               ("enrich", enrich_inner_join), ("describe", describe)]
clock.advance(600)
lost_rows = run_pipeline("run-0001-bug", tonight, buggy_steps, np.random.default_rng(1))
print("rows published:", len(lost_rows), "instead of", len(published))
try:
    reconcile("run-0001-bug")
except ReconciliationError as err:
    print("ReconciliationError:", err)
def finish_run(run_id, df, status, message=""):
    """Close a run: its finish time, status and totals (summed from its steps)."""
    db.execute("""
        UPDATE runs SET finished = ?, status = ?, message = ?,
            rows_in = (SELECT rows_in FROM steps WHERE run_id = ? AND step_no = 1),
            rows_out = ?,
            quarantined = (SELECT sum(quarantined) FROM steps WHERE run_id = ?),
            duplicates = (SELECT sum(duplicates) FROM steps WHERE run_id = ?)
        WHERE run_id = ?
    """, [clock.now(), status, message, run_id, len(df), run_id, run_id, run_id])


def run_and_publish(run_id, batch, steps, rng):
    """Run, reconcile, and only then publish the result as Parquet."""
    df = run_pipeline(run_id, batch, steps, rng)
    try:
        reconcile(run_id)
    except ReconciliationError as err:
        finish_run(run_id, df.iloc[0:0], "failed", str(err))
        log.error("run failed reconciliation; nothing published",
                  extra={"fields": {"run_id": run_id}})
        return None
    df = df.drop(columns="mol")  # RDKit objects stay in memory; the SMILES is what we store
    Path("work/published").mkdir(exist_ok=True)
    df.to_parquet(f"work/published/{run_id}.parquet", index=False)
    finish_run(run_id, df, "succeeded")
    return df

# ---- 5. Metrics: throughput, rates and freshness ----
FRESHNESS_LIMIT = timedelta(hours=26)


def freshness(now):
    """Time since the last successful run finished (None if there has never been one)."""
    last = db.execute("SELECT max(finished) FROM runs WHERE status = 'succeeded'").fetchall()[0][0]
    return None if last is None else now - last


clock.advance(600)
run_and_publish("run-0002", tonight, STEPS, np.random.default_rng(2))
metrics = db.sql("""
    SELECT run_id, status,
           round(rows_in / epoch(finished - started)) AS rows_per_s,
           round(100 * quarantined / rows_in, 1) AS quarantined_pct
    FROM runs WHERE status <> 'running' ORDER BY started
""").df()
print(metrics.to_string(index=False))
clock.advance(30 * 3600)  # thirty hours later, and no run since
age = freshness(clock.now())
print(f"freshness: {age.total_seconds() / 3600:.1f} h; within the limit: {age <= FRESHNESS_LIMIT}")

# ---- 6. Drift in molecular properties ----
def psi(reference, new, bins=10):
    """Population stability index of `new` against `reference`, on the reference's quantiles."""
    edges = np.quantile(reference, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf  # catch values beyond the reference's range
    ref_share = np.histogram(reference, edges)[0] / len(reference)
    new_share = np.histogram(new, edges)[0] / len(new)
    ref_share = np.clip(ref_share, 1e-4, None)  # an empty bin would give log(0)
    new_share = np.clip(new_share, 1e-4, None)
    return float(np.sum((new_share - ref_share) * np.log(new_share / ref_share)))


def ks(reference, new):
    """Two-sample Kolmogorov-Smirnov statistic: the largest gap between the two CDFs."""
    values = np.concatenate([reference, new])
    cdf_ref = np.searchsorted(np.sort(reference), values, side="right") / len(reference)
    cdf_new = np.searchsorted(np.sort(new), values, side="right") / len(new)
    return float(np.max(np.abs(cdf_ref - cdf_new)))


def properties(smiles):
    """Molecular weight and logP of a list of SMILES, as two arrays."""
    mols = [Chem.MolFromSmiles(s) for s in smiles]
    return (np.array([Descriptors.MolWt(m) for m in mols]),
            np.array([Descriptors.MolLogP(m) for m in mols]))


reference = published  # run-0001's output, checked by a chemist: the reference
ordinary = properties(chemlib.library(1500, seed=102)["smiles"])
one_page = properties(next(chemlib.stream(1500, batch=1500, start=1_666_800))["smiles"])
print(f"{'batch':10}{'PSI MW':>8}{'PSI logP':>10}{'KS MW':>8}{'KS logP':>9}")
for name, (mw, logp) in [("ordinary", ordinary), ("one page", one_page)]:
    print(f"{name:10}{psi(reference['mw'], mw):8.3f}{psi(reference['logp'], logp):10.3f}"
          f"{ks(reference['mw'], mw):8.3f}{ks(reference['logp'], logp):9.3f}")

# ---- 7. Alerts that people will read ----
from typing import NamedTuple


class Rule(NamedTuple):
    """Alert when `metric` is above `threshold`."""

    name: str
    metric: str
    threshold: float
    severity: str  # "page" (now) or "ticket" (working hours)


RULES = [
    Rule("run failed", "failed", 0.5, "page"),
    Rule("data older than 26 hours", "hours_since_success", 26, "page"),
    Rule("quarantine rate above 10%", "quarantine_rate", 0.10, "ticket"),
    Rule("molecular weight drift (PSI above 0.25)", "psi_mw", 0.25, "ticket"),
    Rule("logP drift (PSI above 0.25)", "psi_logp", 0.25, "ticket"),
]


class Alerter:
    """Evaluate rules and notify only when a rule starts or stops firing."""

    def __init__(self, rules):
        self.rules = rules
        self.firing = set()

    def update(self, metrics):
        """Check every rule whose metric is in `metrics`; notify on changes."""
        for rule in self.rules:
            if rule.metric not in metrics:
                continue
            now_firing = metrics[rule.metric] > rule.threshold
            if now_firing and rule.name not in self.firing:
                self.firing.add(rule.name)
                self.notify(rule, "FIRING", metrics)
            elif not now_firing and rule.name in self.firing:
                self.firing.remove(rule.name)
                self.notify(rule, "resolved", metrics)

    def notify(self, rule, state, metrics):
        """Send one alert. Here it is a log line; a chat webhook or on-call service is one call more.

        With a webhook it would be: requests.post(url, json={"text": message}, timeout=10).
        """
        level = logging.ERROR if rule.severity == "page" and state == "FIRING" else logging.WARNING
        fields = {"alert": rule.name, "state": state, "severity": rule.severity,
                  "value": round(float(metrics[rule.metric]), 3), "run_id": metrics.get("run_id")}
        log.log(level, "alert", extra={"fields": fields})

# ---- 8. A fortnight of runs ----
for table in ("runs", "steps", "quarantine"):  # a fresh history for the fortnight
    db.execute(f"DELETE FROM {table}")
db.execute("CREATE TABLE drift (run_id VARCHAR, psi_mw DOUBLE, psi_logp DOUBLE, "
           "ks_mw DOUBLE, ks_logp DOUBLE)")
alerter = Alerter(RULES)
first_night = datetime(2027, 1, 4, 2, 0)
rng = np.random.default_rng(14)

for night in range(1, 15):
    run_id = f"run-{night:04d}"
    clock.time = first_night + timedelta(days=night - 1)
    if night == 11:  # one page of a sorted export
        batch = next(chemlib.stream(1500, batch=1500, start=1_666_800))
    else:
        batch = chemlib.library(1500, seed=100 + night)
    batch = chemlib.add_defects(batch, rate=0.04, seed=night)
    steps = buggy_steps if night == 8 else STEPS
    out = run_and_publish(run_id, batch, steps, rng)
    run = db.execute("SELECT status, quarantined / rows_in FROM runs WHERE run_id = ?",
                     [run_id]).fetchall()[0]
    metrics = {"run_id": run_id, "failed": run[0] == "failed", "quarantine_rate": run[1]}
    if out is not None:
        drift = [psi(reference["mw"], out["mw"]), psi(reference["logp"], out["logp"]),
                 ks(reference["mw"], out["mw"]), ks(reference["logp"], out["logp"])]
        db.execute("INSERT INTO drift VALUES (?, ?, ?, ?, ?)", [run_id, *drift])
        metrics.update(psi_mw=drift[0], psi_logp=drift[1])
    alerter.update(metrics)
    clock.time = first_night + timedelta(days=night - 1, hours=7)  # 09:00: the freshness check
    age = freshness(clock.now())
    alerter.update({"run_id": run_id, "hours_since_success": age.total_seconds() / 3600})
history = db.sql("""
    SELECT r.run_id, r.status, r.rows_in, r.rows_out,
           round(100 * r.quarantined / r.rows_in, 1) AS quarantined_pct, r.duplicates,
           round(d.psi_mw, 3) AS psi_mw, round(d.psi_logp, 3) AS psi_logp
    FROM runs r LEFT JOIN drift d USING (run_id)
    ORDER BY r.run_id
""").df()
print(history.to_string(index=False))
failed = (history["status"] == "failed").sum()
print(f"error rate over the fortnight: {failed}/{len(history)} runs failed")
import matplotlib

matplotlib.use("Agg")  # draw to a file, without a window
import matplotlib.pyplot as plt

COLOURS = {"ink": "#1d2130", "violet": "#7c5cf0", "cyan": "#0e9fb5", "muted": "#8b91a1"}


def dashboard(db, path):
    """Draw the run history (counts, quarantine rate, drift) as one SVG figure.

    Args:
        db: The DuckDB connection holding the runs and drift tables.
        path: Where to save the figure.
    """
    runs = db.sql("SELECT * FROM runs LEFT JOIN drift USING (run_id) ORDER BY run_id").df()
    night = np.arange(1, len(runs) + 1)
    fig, (top, middle, bottom) = plt.subplots(3, 1, figsize=(7, 7.5), sharex=True)
    top.bar(night - 0.2, runs["rows_in"], 0.4, color=COLOURS["muted"], label="rows in")
    top.bar(night + 0.2, runs["rows_out"], 0.4, color=COLOURS["violet"], label="rows published")
    for n in night[runs["status"] == "failed"]:
        top.annotate("failed:\nnothing\npublished", (n + 0.2, 60), ha="center", fontsize=8,
                     color=COLOURS["ink"])
    top.set_ylabel("rows")
    top.set_ylim(0, 2000)
    top.legend(loc="upper center", ncol=2, fontsize=8, frameon=False)
    middle.plot(night, 100 * runs["quarantined"] / runs["rows_in"], "o-", color=COLOURS["cyan"])
    middle.axhline(10, color=COLOURS["muted"], linestyle="--", linewidth=1)
    middle.text(0.6, 10.3, "alert threshold", fontsize=8, color=COLOURS["muted"])
    middle.set_ylabel("quarantined (%)")
    middle.set_ylim(0, 12)
    bottom.plot(night, runs["psi_mw"], "o-", color=COLOURS["violet"], label="molecular weight")
    bottom.plot(night, runs["psi_logp"], "s-", color=COLOURS["cyan"], label="logP")
    for level, text in [(0.1, "0.1: look"), (0.25, "0.25: alert")]:
        bottom.axhline(level, color=COLOURS["muted"], linestyle="--", linewidth=1)
        bottom.text(0.6, level * 1.08, text, fontsize=8, va="bottom", color=COLOURS["muted"])
    bottom.set_yscale("symlog", linthresh=0.1)
    bottom.set_ylim(0, 10)
    bottom.set_ylabel("PSI against reference")
    bottom.set_xlabel("night")
    bottom.set_xticks(night)
    bottom.legend(loc="upper center", ncol=2, fontsize=8, frameon=False)
    for ax in (top, middle, bottom):
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


dashboard(db, Path("work/run-dashboard.svg"))
db.close()
