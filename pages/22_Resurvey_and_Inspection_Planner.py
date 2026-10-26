import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS

core, df, settings, ref = lp.page_setup("Re-survey & Inspection Planner",
                                        "Re-survey & inspection planner — where a survey changes the forecast most",
                                        "rsp")
st.caption("Ranks components and properties by how much a fresh survey would reduce uncertainty, then turns that "
           "into a year-by-year inspection plan for your available crew.")

has_ref = ref is not None
sy = df["survey_age"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Never surveyed", f"{sy.isna().sum():,}", money(df.loc[sy.isna(), "cost"].sum()), delta_color="off")
c2.metric("Surveyed 5+ years ago", f"{(sy >= 5).sum():,}", money(df.loc[sy >= 5, "cost"].sum()), delta_color="off")
c3.metric("Median survey age", f"{sy.median():.0f} yrs" if sy.notna().any() else "–")
c4.metric("C-model reset risk flagged", f"{df['condition_reset_risk'].fillna(False).sum():,}")

col1, col2 = st.columns(2)
with col1:
    s = df["cmp_survey_year"].fillna(0).astype(int).replace(0, "Never").astype(str).value_counts()
    s = s.reindex(sorted(s.index, key=lambda x: (x != "Never", x)))
    fig = go.Figure(go.Bar(x=s.index, y=s.values, marker_color=[COLORS["critical"] if i == "Never" else COLORS["steel"]
                                                                 for i in s.index]))
    fig.update_layout(height=280, margin=dict(t=30, l=0, r=0, b=0), yaxis_title="Components",
                      title=dict(text="Last survey year", font=dict(size=13)))
    show_chart(fig)
with col2:
    by = df.assign(_never=sy.isna()).groupby("comp. group")["_never"].mean().sort_values() * 100
    fig = go.Figure(go.Bar(y=by.index, x=by.values, orientation="h", marker_color=COLORS["warn"]))
    fig.update_layout(height=280, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="% never surveyed",
                      title=dict(text="Never surveyed, by component group", font=dict(size=13)))
    show_chart(fig)

# ------------------------------------------------------------------ scoring
st.markdown("---")
st.subheader("Survey priority score")
with st.expander("Weights", expanded=False):
    w = st.columns(4)
    w_stale = w[0].slider("Survey old / missing", 0.0, 1.0, 0.25, 0.05, key="rsp_w1")
    w_life = w[1].slider("Near / past standard life", 0.0, 1.0, 0.20, 0.05, key="rsp_w2")
    w_crit = w[2].slider("Criticality", 0.0, 1.0, 0.20, 0.05, key="rsp_w3")
    w_cost = w[3].slider("Replacement cost", 0.0, 1.0, 0.15, 0.05, key="rsp_w4")
    w2 = st.columns(3)
    w_gap = w2[0].slider("System vs standard date gap", 0.0, 1.0, 0.15 if has_ref else 0.0, 0.05, key="rsp_w5",
                         disabled=not has_ref)
    w_reset = w2[1].slider("C-model reset flag", 0.0, 1.0, 0.05, 0.05, key="rsp_w6")
    w_conf = w2[2].slider("Low data confidence", 0.0, 1.0, 0.05, 0.05, key="rsp_w7")

f_stale = np.where(sy.isna(), 100, (sy.clip(upper=10) / 10 * 100))
f_life = (df["std_consumed"] if has_ref else df["sys_consumed"]).clip(upper=1.2).fillna(1) / 1.2 * 100
f_crit = df["criticality_score"]
f_cost = df["cost"].rank(pct=True) * 100
f_gap = (df["forecast_gap_years"].abs().clip(upper=20) / 20 * 100).fillna(0) if has_ref else 0
f_reset = df["condition_reset_risk"].fillna(False).astype(float) * 100
f_conf = (100 - df["data_confidence_score"].fillna(100)).clip(0, 100)
wt = w_stale + w_life + w_crit + w_cost + w_gap + w_reset + w_conf
score = (w_stale * f_stale + w_life * f_life + w_crit * f_crit + w_cost * f_cost + w_gap * f_gap
         + w_reset * f_reset + w_conf * f_conf) / max(wt, 1e-9)
d = df.assign(survey_score=np.round(score, 1))
cut = st.slider("Include components with a survey score of at least", 0, 100, 60, 5, key="rsp_cut")
need = d[d["survey_score"] >= cut]
st.caption(f"**{len(need):,} components** ({money(need['cost'].sum())} replacement value) meet the threshold.")

# ------------------------------------------------------------------ property-level priority
st.subheader("Where to send the field team — property priority")
grp_cols = ["source_site", "site", "property code", "property"]
prop = need.groupby(grp_cols, dropna=False).agg(
    components_to_survey=("cmp_id", "size"), value_at_stake=("cost", "sum"), avg_score=("survey_score", "mean"),
    never_surveyed=("survey_age", lambda s: s.isna().sum()), critical_high=("criticality_tier",
                                                                             lambda s: s.isin(["Critical", "High"]).sum()),
    last_survey=("cmp_survey_year", "max")).reset_index()
prop["survey_value"] = (need.groupby(grp_cols, dropna=False).apply(
    lambda g: (g["survey_score"] / 100 * g["cost"]).sum(), include_groups=False).values)
prop = prop.sort_values("survey_value", ascending=False).reset_index(drop=True)
prop.insert(0, "priority", np.arange(1, len(prop) + 1))
prop["last_survey"] = prop["last_survey"].replace(0, np.nan)
st.dataframe(prop.head(500), hide_index=True, width="stretch", column_config={
    "value_at_stake": st.column_config.NumberColumn("Value at stake", format="$%.0f"),
    "survey_value": st.column_config.NumberColumn("Survey value", format="$%.0f",
                                                  help="Σ (score/100 × replacement cost): $ of forecast the survey "
                                                       "would firm up"),
    "avg_score": st.column_config.NumberColumn(format="%.0f"),
    "last_survey": st.column_config.NumberColumn("Latest survey", format="%d")})
lp.download(prop, "Download property priority (CSV)", "survey_property_priority.csv", "rsp_dl1")
if len(prop):
    top20 = prop.head(20)
    st.caption(f"The top 20 properties hold {top20['components_to_survey'].sum():,} components and "
               f"{top20['survey_value'].sum() / max(prop['survey_value'].sum(), 1) * 100:.0f}% of the total survey value.")

# ------------------------------------------------------------------ crew plan
st.markdown("---")
st.subheader("Workforce and inspection resource plan")
p1, p2, p3, p4 = st.columns(4)
inspectors = p1.number_input("Inspectors", 1, 100, 2, key="rsp_insp")
days = p2.number_input("Survey days per inspector per year", 10, 250, 120, 10, key="rsp_days")
per_day = p3.number_input("Components surveyed per inspector-day", 10, 1000, 80, 10, key="rsp_rate")
day_cost = p4.number_input("Cost per inspector-day ($)", 0, 10000, 1200, 100, key="rsp_cost")
capacity = inspectors * days * per_day
total = int(prop["components_to_survey"].sum())
years_needed = total / capacity if capacity else np.inf
k1, k2, k3, k4 = st.columns(4)
k1.metric("Capacity per year", f"{capacity:,.0f} components")
k2.metric("Components to survey", f"{total:,}")
k3.metric("Years to complete", f"{years_needed:.1f}")
k4.metric("Total survey cost", money(total / per_day * day_cost))
cum = prop["components_to_survey"].cumsum()
prop["plan_year"] = (lp.CY + ((cum - 1) // max(capacity, 1))).astype(int)
yp = prop.groupby("plan_year").agg(properties=("property", "size"), components=("components_to_survey", "sum"),
                                   survey_value=("survey_value", "sum"))
fig = go.Figure()
fig.add_trace(go.Bar(x=yp.index.astype(str), y=yp["components"], name="Components", marker_color=COLORS["accent"]))
fig.add_trace(go.Scatter(x=yp.index.astype(str), y=yp["survey_value"].cumsum() / max(prop["survey_value"].sum(), 1)
                         * 100, name="Cumulative survey value (%)", yaxis="y2", line=dict(color=COLORS["good"], width=3)))
fig.update_layout(height=320, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Components",
                  yaxis2=dict(title="% of survey value", overlaying="y", side="right", range=[0, 105], showgrid=False),
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
show_chart(fig)
st.caption("Properties are scheduled in priority order until each year's capacity is used. Highest-value surveys "
           "come first, so most of the uncertainty is removed early.")
yr = st.selectbox("Show plan for", yp.index.tolist(), key="rsp_year")
st.dataframe(prop[prop["plan_year"] == yr], hide_index=True, width="stretch", column_config={
    "value_at_stake": st.column_config.NumberColumn(format="$%.0f"),
    "survey_value": st.column_config.NumberColumn(format="$%.0f"),
    "last_survey": st.column_config.NumberColumn(format="%d")})
lp.download(prop, "Download full inspection plan (CSV)", "inspection_plan.csv", "rsp_dl2")

# ------------------------------------------------------------------ component list
st.markdown("---")
st.subheader("Component inspection priority")
cols = ["survey_score", "cmp_id", "source_site", "property", "component", "Condition", "cmp_survey_year",
        "cmp_construction_year", "sys_due", "std_due", "criticality_tier", "data_confidence", "cost"]
t = need.sort_values("survey_score", ascending=False)
st.dataframe(t[cols].head(2000), hide_index=True, width="stretch", column_config={
    "cost": st.column_config.NumberColumn(format="$%.0f"),
    "sys_due": st.column_config.NumberColumn("System due", format="%d"),
    "std_due": st.column_config.NumberColumn("Standard due", format="%d")})
lp.download(t[cols], "Download components (CSV)", "survey_components.csv", "rsp_dl3")
