"""The EGFR project's structure-activity dashboard (Series 2, Module 10; the capstone's copy).

Run it with: streamlit run dashboard.py   (from this folder, after the lesson has run)
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
SERIES_COLOURS = {
    "aminopyrimidines": "#0072B2",
    "pyrimidine piperazines": "#E69F00",
    "ureas": "#009E73",
}

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
st.caption(
    f"Measurements up to {newest:%d %B %Y}, from the lab's warehouse. Potencies are mean "
    "pIC50 over measured results; superseded readings are left out. The data are synthetic."
)


wide = potency.pivot_table(
    index=["compound_id", "parent_smiles", "series", "chemist", "week", "mw", "clogp"],
    columns="target",
    values="pic50",
).reset_index()
panel = [t for t in ["ABL1", "BRAF", "CDK2", "JAK2"] if t in wide]
wide["best_panel"] = wide[panel].max(axis=1)  # the panel kinase it hits hardest
wide["selectivity"] = wide["EGFR"] - wide["best_panel"]  # 2 = a hundred times more potent on EGFR
wide["lipe"] = wide["EGFR"] - wide["clogp"]

with st.sidebar:
    st.header("Filters")
    series = st.multiselect("Series", list(SERIES_COLOURS), default=list(SERIES_COLOURS))
    weeks = st.slider(
        "Registered in weeks", 1, int(wide["week"].max()), (1, int(wide["week"].max()))
    )
    panel_only = st.checkbox("Only compounds tested on the panel")

shown = wide[wide["series"].isin(series) & wide["week"].between(*weeks)]
if panel_only:
    shown = shown[shown["best_panel"].notna()]

tested = shown[shown["best_panel"].notna()]
columns = st.columns(4)
columns[0].metric("Compounds", len(shown))
columns[1].metric(
    f"EGFR pIC50 of {PANEL_CUTOFF:g} or more", int((shown["EGFR"] >= PANEL_CUTOFF).sum())
)
columns[2].metric("Tested on the panel", len(tested))
columns[3].metric("Best selectivity", f"{tested['selectivity'].max():.1f}" if len(tested) else "-")


st.subheader("Each series, week by week")
st.caption("Mean EGFR pIC50 of the compounds registered each week. Dashed: the panel cut-off.")
by_week = shown.dropna(subset=["EGFR"]).groupby(["week", "series"], as_index=False)["EGFR"].mean()
colour = alt.Color(
    "series:N",
    title="Series",
    scale=alt.Scale(domain=list(SERIES_COLOURS), range=list(SERIES_COLOURS.values())),
)
lines = (
    alt.Chart(by_week)
    .mark_line(point=True)
    .encode(
        x=alt.X("week:O", title="Week registered"),
        y=alt.Y("EGFR:Q", title="Mean EGFR pIC50", scale=alt.Scale(zero=False)),
        color=colour,
        tooltip=["series", "week", alt.Tooltip("EGFR:Q", format=".2f")],
    )
)
cutoff = alt.Chart(pd.DataFrame({"y": [PANEL_CUTOFF]})).mark_rule(strokeDash=[4, 4]).encode(y="y")
st.altair_chart(lines + cutoff, width="stretch")


st.subheader("Potency and selectivity")
st.caption(
    "Each point is a compound tested on the panel. Below the solid line it is more potent on "
    "EGFR than on any panel kinase; below the dashed line, a hundred times more."
)
low, high = 6.5, 9.0  # only compounds at the panel cut-off (7) or near it reach the panel
guides = pd.DataFrame({"x": [low, high], "same": [low, high], "fold100": [low - 2, high - 2]})
points = (
    alt.Chart(tested)
    .mark_circle(size=70, opacity=0.8)
    .encode(
        x=alt.X("EGFR:Q", title="EGFR pIC50", scale=alt.Scale(domain=[low, high])),
        y=alt.Y("best_panel:Q", title="Best panel pIC50", scale=alt.Scale(domain=[4.0, high])),
        color=colour,
        tooltip=[
            "compound_id",
            "series",
            alt.Tooltip("EGFR:Q", format=".2f"),
            alt.Tooltip("best_panel:Q", format=".2f"),
            alt.Tooltip("selectivity:Q", format=".2f"),
        ],
    )
)
same = alt.Chart(guides).mark_line(color="#888888").encode(x="x", y="same")
fold100 = alt.Chart(guides).mark_line(color="#888888", strokeDash=[4, 4]).encode(x="x", y="fold100")
st.altair_chart(points + same + fold100, width="stretch")


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
        "selectivity": st.column_config.NumberColumn(
            "Selectivity", format="%.2f", help="EGFR pIC50 minus best panel pIC50"
        ),
        "clogp": st.column_config.NumberColumn("cLogP", format="%.2f"),
        "lipe": st.column_config.NumberColumn("LipE", format="%.2f", help="pIC50 minus cLogP"),
    },
    hide_index=True,
    row_height=110,
)


st.subheader("One compound")
choice = st.selectbox(
    "Compound", sorted(wide["compound_id"]), index=None, placeholder="Choose a compound"
)
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
        right.warning(
            f"{choice}'s registration changed {len(history) - 1} time(s): "
            "measurements before the change were made under an earlier structure."
        )
    right.dataframe(history, hide_index=True)
