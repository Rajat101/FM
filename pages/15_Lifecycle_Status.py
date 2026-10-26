import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS

core, df, settings, ref = lp.page_setup("Lifecycle Status", "Lifecycle status — age, end of life and remaining life",
                                        "lcs")
b = settings["basis"]
st.caption("Core lifecycle calculations for every component: age, expected end-of-life year, remaining useful "
           "life, % of life used, status and years overdue.")
lp.basis_note(settings)

with st.expander("How these are calculated", expanded=False):
    st.markdown(f"""
- **Asset age** = {lp.CY} − construction year.
- **Expected end-of-life year** — *Standard life*: construction year + average life. *System forecast*: the
  system's next renewal year (or a 'replace by' year written in the comments).
- **Remaining useful life (RUL)** = end-of-life year − {lp.CY}. Negative = overdue.
- **Useful life consumed** — *Standard life*: age ÷ average life. *System forecast*: 1 − RUL ÷ base life
  (what the system's own date implies).
- **Status** — *Overdue* when RUL < 0; *Approaching EOL* from {settings['approach']*100:.0f}% of life used
  (sidebar); *Unknown* when construction year or life is missing or invalid; otherwise *Healthy*.
- **Expected replacement year** = end-of-life year, or {lp.CY} if already overdue.
""")

# ------------------------------------------------------------------ alerts
crit_hi = df["criticality_tier"].isin(["Critical", "High"])
eol_12m = df[(df["rul"].between(0, 1)) & crit_hi]
od_crit = df[(df["status"] == "Overdue") & (df["criticality_tier"] == "Critical")]
alerts = []
if len(od_crit):
    alerts.append(("critical", f"{len(od_crit):,} critical components are past end of life",
                   f"{money(od_crit['cost'].sum())} replacement value. See Criticality & Risk Hotspots."))
if len(eol_12m):
    alerts.append(("warn", f"{len(eol_12m):,} high/critical components reach end of life within 12 months",
                   f"{money(eol_12m['cost'].sum())} to plan for in {lp.CY}–{lp.CY + 1}."))
unk = (df["status"] == "Unknown").sum()
if unk:
    alerts.append(("normal", f"{unk:,} components have an Unknown status",
                   "Missing or invalid construction year or life — see the completeness section below."))
if alerts:
    cols = st.columns(len(alerts))
    for col, (lvl, h, dtl) in zip(cols, alerts):
        col.markdown(f'<div class="insight-card {lvl}"><div class="headline">{h}</div>'
                     f'<div class="detail">{dtl}</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------------------------ KPIs
n = len(df)
known = df[df["status"] != "Unknown"]
c1, c2, c3, c4, c5, c6 = lp.metric_cols(6)
c1.metric("Components", f"{n:,}")
c2.metric("Avg. asset age", f"{df['asset_age'].mean():.0f} yrs")
c3.metric("Median life used", f"{known['consumed'].median()*100:.0f}%")
c4.metric("Beyond expected life", f"{(df['status'] == 'Overdue').mean()*100:.0f}%")
c5.metric("Avg. years overdue", f"{df.loc[df['status'] == 'Overdue', 'years_overdue'].mean():.1f}"
          if (df["status"] == "Overdue").any() else "–")
c6.metric("Median RUL", f"{known['rul'].median():.0f} yrs" if len(known) else "–")

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Lifecycle status")
    counts = df["status"].value_counts().reindex(lp.STATUS_ORDER).fillna(0)
    cost = df.groupby("status")["cost"].sum().reindex(lp.STATUS_ORDER).fillna(0)
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker_color=[lp.STATUS_COLORS[s] for s in counts.index],
                           text=[f"{int(v):,}<br>{money(c)}" for v, c in zip(counts.values, cost.values)],
                           textposition="outside"))
    fig.update_layout(height=340, margin=dict(t=30, l=0, r=0, b=0), yaxis_title="Components")
    show_chart(fig)
with col2:
    st.subheader("Status by component group")
    ct = pd.crosstab(df["comp. group"], df["status"]).reindex(columns=lp.STATUS_ORDER, fill_value=0)
    ct = ct.loc[ct.sum(axis=1).sort_values().index]
    fig = go.Figure()
    for s in lp.STATUS_ORDER:
        fig.add_trace(go.Bar(y=ct.index, x=ct[s], name=s, orientation="h", marker_color=lp.STATUS_COLORS[s]))
    fig.update_layout(barmode="stack", height=340, margin=dict(t=10, l=0, r=0, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=-0.3))
    show_chart(fig)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Useful life consumed")
    x = (known["consumed"].clip(upper=2.5) * 100)
    fig = go.Figure(go.Histogram(x=x, nbinsx=50, marker_color=COLORS["accent"]))
    fig.add_vline(x=settings["approach"] * 100, line_dash="dot", line_color=COLORS["warn"],
                  annotation_text="Approaching EOL")
    fig.add_vline(x=100, line_dash="dash", line_color=COLORS["critical"], annotation_text="End of life")
    fig.update_layout(height=320, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="% of life used (capped at 250%)",
                      yaxis_title="Components")
    show_chart(fig)
with col2:
    st.subheader("Remaining useful life")
    r = known["rul"].clip(-40, 60)
    fig = go.Figure(go.Histogram(x=r, nbinsx=50, marker_color=COLORS["steel"]))
    fig.add_vline(x=0, line_dash="dash", line_color=COLORS["critical"])
    fig.update_layout(height=320, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="Years (negative = overdue, capped)",
                      yaxis_title="Components")
    show_chart(fig)

# ------------------------------------------------------------------ age vs average life
st.markdown("---")
st.subheader("Asset age versus average life, by component type")
if ref is None:
    st.info("Upload the Asset Life file in the sidebar to compare age against the standard average life.")
else:
    g = df.dropna(subset=["std_life", "asset_age"]).groupby("component").agg(
        components=("cmp_id", "size"), avg_age=("asset_age", "mean"), avg_life=("std_life", "first"),
        system_life=("sys_life", "median"), cost=("cost", "sum"))
    g = g[g["components"] >= 5]
    g["age_vs_life"] = g["avg_age"] / g["avg_life"]
    fig = go.Figure(go.Scatter(
        x=g["avg_life"], y=g["avg_age"], mode="markers", text=g.index,
        marker=dict(size=np.clip(np.sqrt(g["components"]) * 1.5, 5, 40),
                    color=np.where(g["age_vs_life"] >= 1, COLORS["critical"], COLORS["accent"]), opacity=0.7),
        hovertemplate="<b>%{text}</b><br>Average life %{x} yrs<br>Average age %{y:.0f} yrs<extra></extra>"))
    mx = float(max(g["avg_life"].max(), g["avg_age"].max(), 10))
    fig.add_trace(go.Scatter(x=[0, mx], y=[0, mx], mode="lines", line=dict(dash="dash", color=COLORS["text_muted"]),
                             hoverinfo="skip"))
    fig.update_layout(height=420, margin=dict(t=10, l=0, r=0, b=0), showlegend=False,
                      xaxis_title="Standard average life (yrs)", yaxis_title="Average age of components (yrs)")
    show_chart(fig)
    st.caption("Each bubble is a component type (5+ components). Red = on average older than its standard life. "
               "Above the dashed line = past standard life.")

# ------------------------------------------------------------------ completeness
st.markdown("---")
st.subheader("Lifecycle data completeness")
checks = {
    "Construction year valid": df["construction_year_valid"].mean(),
    "Construction year not a property-wide default": 1 - df["construction_year_uniform_property"].fillna(False).mean(),
    "System base life valid": df["base_life_valid"].mean(),
    "Average life found": df["has_avg_life"].mean() if ref is not None else np.nan,
    "Survey year present": df["has_survey"].mean(),
    "Replacement cost > 0": df["has_cost"].mean(),
}
cols = st.columns(len(checks))
for col, (k, v) in zip(cols, checks.items()):
    col.metric(k, "–" if pd.isna(v) else f"{v*100:.0f}%")

issues = df[~df["construction_year_valid"] | ~df["base_life_valid"] | (df["status"] == "Unknown")]
st.markdown(f"**{len(issues):,} components with missing or invalid construction year or life**")
if len(issues):
    st.dataframe(issues[["cmp_id", "source_site", "property", "component", "cmp_construction_year", "base_life",
                         "avg_life", "avg_life_source", "status"]].head(500), hide_index=True, width="stretch")
    lp.download(issues, "Download all (CSV)", "lifecycle_data_gaps.csv", "lcs_dl_gaps")

# ------------------------------------------------------------------ component table
st.markdown("---")
st.subheader("Component lifecycle register")
f1, f2 = st.columns([1, 2])
status_sel = f1.multiselect("Status", lp.STATUS_ORDER, default=["Overdue", "Approaching EOL"], key="lcs_status")
search = f2.text_input("Search component / property", key="lcs_search")
t = df[df["status"].isin(status_sel)] if status_sel else df
if search:
    s = search.lower()
    t = t[t["component"].astype(str).str.lower().str.contains(s, regex=False)
          | t["property"].astype(str).str.lower().str.contains(s, regex=False)]
show = t.assign(expected_eol_year=t["due"], expected_replacement_year=t["planned_year"],
                life_used_pct=(t["consumed"] * 100).round(0))[
    ["cmp_id", "source_site", "site", "property", "comp. group", "component", "Condition", "cmp_construction_year",
     "asset_age", "life", "expected_eol_year", "rul", "life_used_pct", "status", "years_overdue",
     "expected_replacement_year", "sys_due", "std_due", "criticality_tier", "cost"]
].sort_values(["years_overdue", "cost"], ascending=False)
st.caption(f"{len(show):,} components. 'life' and the EOL columns follow the selected basis; sys_due / std_due show both.")
st.dataframe(show.head(2000), hide_index=True, width="stretch",
             column_config={"cost": st.column_config.NumberColumn("Cost", format="$%.0f")})
lp.download(show, "Download register (CSV)", "lifecycle_register.csv", "lcs_dl_reg")
