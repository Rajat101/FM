import streamlit as st
import plotly.graph_objects as go
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, render_header, COLORS, DECISION_COLORS, YEARS

st.set_page_config(page_title="Asset Explorer", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Asset explorer")
st.caption(f"Search, filter, and drill into any of the {len(df_all):,} tracked components.")

df = sidebar_filters(df_all, key_prefix="explorer")

st.sidebar.markdown("---")
decision_filter = st.sidebar.multiselect("Decision", sorted(df["decision"].unique()), default=[])
confidence_filter = st.sidebar.multiselect("Data confidence", ["High", "Medium", "Low"], default=[])
search = st.sidebar.text_input("Search component / property")

if decision_filter:
    df = df[df["decision"].isin(decision_filter)]
if confidence_filter:
    df = df[df["data_confidence"].isin(confidence_filter)]
if search:
    s = search.lower()
    df = df[
        df["component"].str.lower().str.contains(s, na=False)
        | df["property"].str.lower().str.contains(s, na=False)
        | df["property code"].str.lower().str.contains(s, na=False)
    ]

st.write(f"**{len(df):,}** components match the current filters")

display_cols = [
    "cmp_id", "portfolio", "site", "property", "comp. group", "comp. type", "component",
    "Condition", "cmp_construction_year", "cmp_survey_year", "best_estimate_year",
    "cost", "risk_score", "urgency_score", "decision", "data_confidence",
]
st.dataframe(
    df[display_cols].sort_values("urgency_score", ascending=False),
    width='stretch',
    height=420,
    column_config={
        "cost": st.column_config.NumberColumn("cost", format="$%.0f"),
        "risk_score": st.column_config.ProgressColumn("risk", min_value=0, max_value=100),
        "urgency_score": st.column_config.ProgressColumn("urgency", min_value=0, max_value=100),
    },
)

st.markdown("---")
st.subheader("Component drill-down")
cmp_id = st.selectbox("Choose a component (cmp_id)", df["cmp_id"].sort_values().unique())
row = df[df["cmp_id"] == cmp_id].iloc[0]

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"**{row['component']}**")
    st.write(f"{row['property']} &mdash; {row['location']}", unsafe_allow_html=True)
    st.write(f"Portfolio: {row['portfolio']} / {row['site']}")
    st.write(f"Group: {row['comp. group']} / {row['comp. type']}")
with c2:
    st.metric("Condition", row["Condition"])
    st.metric("Construction year", int(row["cmp_construction_year"]))
    st.metric("Survey year", int(row["cmp_survey_year"]) if row["cmp_survey_year"] else "Missing")
with c3:
    st.metric("System renewal year", int(row["next_renewal_year"]))
    st.metric("Age-based cross-check", int(row["est_replacement_year_age_based"]))
    st.metric("Decision", row["decision"])

if abs(row["forecast_year_gap"]) >= 5:
    st.warning(
        f"The system's forecast and the age-based cross-check differ by "
        f"**{int(abs(row['forecast_year_gap']))} years** for this component. "
        f"Worth a manual look before relying on the forecast date."
    )
if row["has_replace_override"]:
    st.info(f"A human override was found in the comments, targeting **{int(row['replace_override_year'])}**.")
if row["comment"]:
    st.caption(f"Comment on file: \u201c{row['comment']}\u201d")

st.markdown("#### Forecast profile, 2026\u20132045")
years_vals = [row[y] for y in YEARS]
nonzero = sum(1 for v in years_vals if v)
fig = go.Figure(go.Bar(x=[str(y) for y in YEARS], y=years_vals, marker_color=COLORS["accent"]))
fig.update_layout(height=280, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$")
fig.update_xaxes(tickangle=-45, dtick=1)
show_chart(fig)
if nonzero <= 2:
    st.caption(
        f"This component is only scheduled for replacement {nonzero} time(s) in the 2026\u20132045 window "
        f"\u2014 the mostly-empty chart is expected for a single asset, not a display issue."
    )
