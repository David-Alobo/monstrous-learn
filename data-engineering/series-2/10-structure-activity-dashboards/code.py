"""Structure-activity dashboards: the code of the lesson, in order.

Give the medicinal chemists their own view of the project, served from the warehouse. Build a Streamlit app part by part (filters, headline numbers, each series' progress, potency against selectivity, a table of structures and a page for each compound with its history) and test every part with Streamlit's AppTest before anyone opens it.

Lesson: https://monstrous.com.ng/learn/data-engineering/series-2/10-structure-activity-dashboards/
Run it from anywhere, e.g. from the series folder: uv run python 10-structure-activity-dashboards/code.py
"""

import os as _os
import sys as _sys
from pathlib import Path as _Path

# run as the lesson does: in this module's folder (for work/ and figures/), with the
# course's helpers (chemlib, in the series folder) and this module's own importable
_HERE = _Path(__file__).resolve().parent
_os.chdir(_HERE)
_sys.path[:0] = [str(_HERE), str(_HERE.parent)]

# ---- Setup ----
import json
import logging
import shutil
from pathlib import Path

import duckdb
from streamlit.testing.v1 import AppTest

import labdata
import labstack

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
log = logging.getLogger(__name__)
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").addFilter(
    lambda record: "missing ScriptRunContext" not in record.getMessage())  # expected in a test

# where the lesson writes its files (git-ignored); change it to write somewhere else
WORK = Path("work")
WAREHOUSE = WORK / "lab.duckdb"
PUBLISHED = WORK / "published" / "lab.duckdb"  # the copy the dashboard reads
APP = WORK / "dashboard.py"

shutil.rmtree(WORK, ignore_errors=True)  # start clean
lab = labdata.Lab()
labstack.warehouse_at(lab, labdata.WEEKS, WORK)
PUBLISHED.parent.mkdir(parents=True)
with duckdb.connect(str(WAREHOUSE)) as db:
    db.execute(f"ATTACH '{PUBLISHED.as_posix()}' AS published")
    db.execute("COPY FROM DATABASE lab TO published")
    db.execute("DETACH published")  # let go of the copy, so readers can open it


def add(code: str) -> None:
    """Append one part to the app's file."""
    with APP.open("a", encoding="utf-8", newline="\n") as app:
        app.write(code.lstrip("\n") + "\n\n")


def run_app() -> AppTest:
    """Run the app as it is so far, without a browser, and return what it shows."""
    app = AppTest.from_file(str(APP.resolve()), default_timeout=120).run()
    assert not app.exception, app.exception[0].message  # the app must run without an error
    return app

# ---- 1. The data, read once ----
add('''
"""The EGFR project's structure-activity dashboard (Series 2, Module 10).

Run it with: streamlit run work/dashboard.py   (from the module's folder)
"""

import base64
import os

import altair as alt
import duckdb
import pandas as pd
import streamlit as st
from rdkit import Chem, RDLogger
from rdkit.Chem import Draw

RDLogger.DisableLog("rdApp.*")
WAREHOUSE = os.environ.get("LAB_PUBLISHED", "work/published/lab.duckdb")  # published, read-only
PANEL_CUTOFF = 7.0  # EGFR pIC50 at which a compound goes on to the selectivity panel
# one colour per series, from Okabe and Ito's palette: distinct with colour-vision deficiency
SERIES_COLOURS = {"aminopyrimidines": "#0072B2", "pyrimidine piperazines": "#E69F00",
                  "ureas": "#009E73"}

st.set_page_config(page_title="EGFR project: structure-activity", layout="wide")


@st.cache_data(ttl=600)
def load(sql: str) -> pd.DataFrame:
    """Run one query on the warehouse, read-only; the answer is kept for ten minutes."""
    with duckdb.connect(WAREHOUSE, read_only=True) as db:
        return db.sql(sql).df()


potency = load("""
    SELECT w.compound_id, w.parent_smiles, w.series, w.chemist, w.mw, w.clogp, w.target,
           c.registered_on,
           avg(w.pic50) FILTER (WHERE w.relation = '=')   AS pic50,
           count(*) FILTER (WHERE w.relation = '>')       AS bounds
    FROM marts.measurements_wide AS w
    JOIN marts.dim_compound AS c USING (compound_id)
    GROUP BY ALL
""")
start = load("SELECT min(date_key) AS d FROM marts.dim_date")["d"][0]
potency["week"] = (potency["registered_on"] - start).dt.days // 7 + 1
newest = load("SELECT max(run_date) AS d FROM marts.fact_measurement")["d"][0]

st.title("EGFR project: structure-activity")
st.caption(f"Measurements up to {newest:%d %B %Y}, from the lab's warehouse. Potencies are mean "
           "pIC50 over measured results; superseded readings are left out. The data are synthetic.")
''')
app = run_app()
print(app.title[0].value)
print(app.caption[0].value)

# ---- 2. Filters and headline numbers ----
add('''
wide = potency.pivot_table(index=["compound_id", "parent_smiles", "series", "chemist", "week",
                                  "mw", "clogp"], columns="target", values="pic50").reset_index()
panel = [t for t in ["ABL1", "BRAF", "CDK2", "JAK2"] if t in wide]
wide["best_panel"] = wide[panel].max(axis=1)  # the panel kinase it hits hardest
wide["selectivity"] = wide["EGFR"] - wide["best_panel"]  # 2 = a hundred times more potent on EGFR
wide["lipe"] = wide["EGFR"] - wide["clogp"]

with st.sidebar:
    st.header("Filters")
    series = st.multiselect("Series", list(SERIES_COLOURS), default=list(SERIES_COLOURS))
    weeks = st.slider("Registered in weeks", 1, int(wide["week"].max()), (1, int(wide["week"].max())))
    panel_only = st.checkbox("Only compounds tested on the panel")

shown = wide[wide["series"].isin(series) & wide["week"].between(*weeks)]
if panel_only:
    shown = shown[shown["best_panel"].notna()]

tested = shown[shown["best_panel"].notna()]
columns = st.columns(4)
columns[0].metric("Compounds", len(shown))
columns[1].metric(f"EGFR pIC50 of {PANEL_CUTOFF:g} or more", int((shown["EGFR"] >= PANEL_CUTOFF).sum()))
columns[2].metric("Tested on the panel", len(tested))
columns[3].metric("Best selectivity", f"{tested['selectivity'].max():.1f}" if len(tested) else "-")
''')
app = run_app()
print({metric.label: metric.value for metric in app.metric})
app.sidebar.multiselect[0].set_value(["ureas"])
app.sidebar.slider[0].set_value((1, 6))
app.run()
print({metric.label: metric.value for metric in app.metric})

# ---- 3. Each series' progress ----
add('''
st.subheader("Each series, week by week")
st.caption("Mean EGFR pIC50 of the compounds registered each week. Dashed: the panel cut-off.")
by_week = (shown.dropna(subset=["EGFR"])
           .groupby(["week", "series"], as_index=False)["EGFR"].mean())
colour = alt.Color("series:N", title="Series",
                   scale=alt.Scale(domain=list(SERIES_COLOURS), range=list(SERIES_COLOURS.values())))
lines = alt.Chart(by_week).mark_line(point=True).encode(
    x=alt.X("week:O", title="Week registered"),
    y=alt.Y("EGFR:Q", title="Mean EGFR pIC50", scale=alt.Scale(zero=False)),
    color=colour,
    tooltip=["series", "week", alt.Tooltip("EGFR:Q", format=".2f")],
)
cutoff = alt.Chart(pd.DataFrame({"y": [PANEL_CUTOFF]})).mark_rule(strokeDash=[4, 4]).encode(y="y")
st.altair_chart(lines + cutoff, width="stretch")
''')
app = run_app()
charts = app.get("vega_lite_chart")
print(len(charts), "chart; its marks:",
      [layer["mark"]["type"] for layer in json.loads(charts[0].proto.spec)["layer"]])

# ---- 4. Potency against selectivity ----
add('''
st.subheader("Potency and selectivity")
st.caption("Each point is a compound tested on the panel. Below the solid line it is more potent on "
           "EGFR than on any panel kinase; below the dashed line, a hundred times more.")
low, high = 6.5, 9.0  # only compounds at the panel cut-off (7) or near it reach the panel
guides = pd.DataFrame({"x": [low, high], "same": [low, high], "fold100": [low - 2, high - 2]})
points = alt.Chart(tested).mark_circle(size=70, opacity=0.8).encode(
    x=alt.X("EGFR:Q", title="EGFR pIC50", scale=alt.Scale(domain=[low, high])),
    y=alt.Y("best_panel:Q", title="Best panel pIC50", scale=alt.Scale(domain=[4.0, high])),
    color=colour,
    tooltip=["compound_id", "series", alt.Tooltip("EGFR:Q", format=".2f"),
             alt.Tooltip("best_panel:Q", format=".2f"), alt.Tooltip("selectivity:Q", format=".2f")],
)
same = alt.Chart(guides).mark_line(color="#888888").encode(x="x", y="same")
fold100 = alt.Chart(guides).mark_line(color="#888888", strokeDash=[4, 4]).encode(x="x", y="fold100")
st.altair_chart(points + same + fold100, width="stretch")
''')
app = run_app()
print(len(app.get("vega_lite_chart")), "charts")

# ---- 5. A table of structures ----
add('''
@st.cache_data
def picture(smiles: str) -> str:
    """The molecule drawn as an SVG picture, as a data URL a table can show."""
    svg = Draw.MolsToGridImage([Chem.MolFromSmiles(smiles)], subImgSize=(220, 160), useSVG=True)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


st.subheader("The most potent compounds")
best = shown.dropna(subset=["EGFR"]).sort_values("EGFR", ascending=False).head(25).copy()
best["structure"] = best["parent_smiles"].map(picture)
st.dataframe(
    best[["structure", "compound_id", "series", "chemist", "EGFR", "selectivity", "clogp", "lipe"]],
    column_config={
        "structure": st.column_config.ImageColumn("Structure", width="medium"),
        "compound_id": "Compound",
        "EGFR": st.column_config.NumberColumn("EGFR pIC50", format="%.2f"),
        "selectivity": st.column_config.NumberColumn("Selectivity", format="%.2f",
                                                     help="EGFR pIC50 minus best panel pIC50"),
        "clogp": st.column_config.NumberColumn("cLogP", format="%.2f"),
        "lipe": st.column_config.NumberColumn("LipE", format="%.2f", help="pIC50 minus cLogP"),
    },
    hide_index=True, row_height=110,
)
''')
app = run_app()
table = app.dataframe[0].value
print(table.drop(columns="structure").head(5).round(2).to_string(index=False))
print("every row has a picture:", table["structure"].str.startswith("data:image/svg+xml").all())

# ---- 6. A page for each compound ----
add('''
st.subheader("One compound")
choice = st.selectbox("Compound", sorted(wide["compound_id"]), index=None,
                      placeholder="Choose a compound")
if choice:
    measurements = load(f"""
        SELECT t.target, f.run_date, f.plate, f.replicate, f.relation, f.ic50_nm,
               round(f.pic50, 2) AS pic50, f.status
        FROM marts.fact_measurement AS f
        JOIN marts.dim_compound AS c USING (compound_key)
        JOIN marts.dim_target AS t USING (target_key)
        WHERE c.compound_id = '{choice}'
        ORDER BY f.run_date, t.target, f.replicate, f.status DESC
    """)
    history = load(f"""
        SELECT version, valid_from, valid_to, parent_smiles
        FROM marts.dim_compound_history WHERE compound_id = '{choice}' ORDER BY version
    """)
    left, right = st.columns([1, 2])
    left.image(picture(history["parent_smiles"].iloc[-1]), caption=f"{choice}, as registered now")
    right.dataframe(measurements, hide_index=True)
    if len(history) > 1:
        right.warning(f"{choice}'s registration changed {len(history) - 1} time(s): "
                      "measurements before the change were made under an earlier structure.")
    right.dataframe(history, hide_index=True)
''')
app = run_app()
app.selectbox[0].set_value("LAB-0042").run()
print([warning.value for warning in app.warning])
print(app.dataframe[1].value.to_string(index=False))
print(app.dataframe[2].value.drop(columns="parent_smiles").to_string(index=False))
