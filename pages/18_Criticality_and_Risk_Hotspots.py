import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS

core, df, settings, ref = lp.page_setup("Criticality & Risk Hotspots",
                                        "Criticality & risk hotspots — what matters most, and where", "crh")
b = settings["basis"]
st.caption("Asset criticality, lifecycle risk, overdue critical assets, hotspots by site and asset type, and "
           "the recommended next action for each component.")
lp.basis_note(settings)

with st.expander("How criticality and lifecycle risk are scored", expanded=False):
    st.markdown("""
- **Criticality** = consequence × safety (each 1–5, from the source data), so 1–25.
  Tiers: **Critical** 16–25 · **High** 9–15 · **Medium** 4–8 · **Low** 1–3.
- **Likelihood** (1–5) = the worse of the condition rating (C1–C5) and the life-used band
  (<50% → 1, 50–80% → 2, 80–100% → 3, 100–150% → 4, 150%+ → 5).
- **Lifecycle risk score** (0–100) = likelihood × criticality ÷ 125 × 100.
- **Risk exposure** = replacement cost of components in the selected risk band.
""")

risk_cut = st.slider("'High risk' from lifecycle risk score", 20, 80, 40, 5, key="crh_cut")
hi = df["risk"] >= risk_cut
crit = df["criticality_tier"] == "Critical"
crit_hi = df["criticality_tier"].isin(["Critical", "High"])
od = df["status"] == "Overdue"
appr = df["status"] == "Approaching EOL"

c1, c2, c3, c4, c5, c6 = lp.metric_cols(6)
c1.metric("High-risk components", f"{hi.sum():,}", f"{hi.mean()*100:.0f}% of total", delta_color="off")
c2.metric("Risk exposure", money(df.loc[hi, "cost"].sum()))
c3.metric("Beyond expected life", f"{od.mean()*100:.0f}%")
c4.metric("Overdue critical", f"{(od & crit).sum():,}", money(df.loc[od & crit, "cost"].sum()), delta_color="off")
c5.metric("Approaching EOL, high criticality", f"{(appr & crit_hi).sum():,}",
          money(df.loc[appr & crit_hi, "cost"].sum()), delta_color="off")
c6.metric("Avg. risk score", f"{df['risk'].mean():.0f} / 100")

# ------------------------------------------------------------------ risk matrix
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Risk matrix")
    lk = df["likelihood"].round().clip(1, 5).astype(int)
    cq = pd.to_numeric(df["consequence"], errors="coerce").fillna(3).clip(1, 5).astype(int)
    mat = pd.crosstab(lk, cq).reindex(index=[1, 2, 3, 4, 5], columns=[1, 2, 3, 4, 5], fill_value=0)
    score = np.outer([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    fig = go.Figure(go.Heatmap(z=score, x=[f"C{i}" for i in range(1, 6)], y=[f"L{i}" for i in range(1, 6)],
                               text=mat.values, texttemplate="%{text:,}", showscale=False,
                               colorscale=[[0, COLORS["good"]], [0.35, COLORS["warn"]], [1, COLORS["critical"]]],
                               hovertemplate="Likelihood %{y} · Consequence %{x}<br>%{text:,} components<extra></extra>"))
    fig.update_xaxes(ticktext=["1", "2", "3", "4", "5"], tickvals=[f"C{i}" for i in range(1, 6)])
    fig.update_yaxes(ticktext=["1", "2", "3", "4", "5"], tickvals=[f"L{i}" for i in range(1, 6)])
    fig.update_layout(height=360, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Consequence",
                      yaxis_title="Likelihood")
    show_chart(fig)
with col2:
    st.subheader("Criticality ranking")
    t = df.groupby("criticality_tier").agg(components=("cmp_id", "size"), cost=("cost", "sum"),
                                           overdue=("status", lambda s: (s == "Overdue").sum()))
    t = t.reindex(lp.CRIT_ORDER).fillna(0)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=t.index, y=t["components"], name="Components",
                         marker_color=[lp.CRIT_COLORS[k] for k in t.index]))
    fig.add_trace(go.Bar(x=t.index, y=t["overdue"], name="of which overdue", marker_color=COLORS["text_muted"]))
    fig.update_layout(barmode="overlay", height=360, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Components",
                      legend=dict(orientation="h", yanchor="bottom", y=-0.25))
    show_chart(fig)

# ------------------------------------------------------------------ hotspots
st.markdown("---")
st.subheader("Risk hotspots")
loc_options = {"source_site": "Site (file)", "site": "Site (in data)", "property": "Property"}
if "area" in df.columns and df["area"].notna().any():
    loc_options = {"area": "Region / area", **loc_options}
h1, h2, h3 = st.columns(3)
loc = h1.selectbox("Location level", list(loc_options), format_func=loc_options.get, index=1 if "area" not in
                   loc_options else 0, key="crh_loc")
typ = h2.selectbox("Asset level", ["comp. group", "comp. type", "component"],
                   format_func={"comp. group": "Component group", "comp. type": "Component type",
                                "component": "Component"}.get, key="crh_typ")
measure = h3.selectbox("Measure", ["Risk exposure ($)", "High-risk components", "Overdue critical/high"],
                       key="crh_meas")
val = {"Risk exposure ($)": df["cost"].where(hi, 0), "High-risk components": hi.astype(int),
       "Overdue critical/high": (od & crit_hi).astype(int)}[measure]
d2 = df.assign(_v=val)
top_loc = d2.groupby(loc)["_v"].sum().nlargest(15).index
top_typ = d2.groupby(typ)["_v"].sum().nlargest(12).index
hm = d2[d2[loc].isin(top_loc) & d2[typ].isin(top_typ)].pivot_table(index=loc, columns=typ, values="_v",
                                                                  aggfunc="sum", fill_value=0)
hm = hm.reindex(index=[i for i in top_loc if i in hm.index], columns=[c for c in top_typ if c in hm.columns])
if hm.size:
    z = hm.values / (1e6 if measure.startswith("Risk") else 1)
    fig = go.Figure(go.Heatmap(z=z, x=[str(c)[:28] for c in hm.columns], y=[str(i)[:30] for i in hm.index],
                               colorscale=[[0, COLORS["surface_2"]], [0.5, COLORS["warn"]], [1, COLORS["critical"]]],
                               text=np.round(z, 1), texttemplate="%{text}",
                               colorbar=dict(title="$M" if measure.startswith("Risk") else "count")))
    fig.update_layout(height=520, margin=dict(t=10, l=0, r=0, b=0))
    show_chart(fig)
    st.caption(f"Top 15 {loc_options[loc].lower()}s × top 12 by {measure.lower()}.")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Risk exposure by asset category**")
    e = df.groupby("comp. group").agg(components=("cmp_id", "size"),
                                      high_risk=("risk", lambda s: (s >= risk_cut).sum()),
                                      exposure=("cost", lambda s: s[df.loc[s.index, "risk"] >= risk_cut].sum()),
                                      beyond_life_pct=("status", lambda s: (s == "Overdue").mean() * 100),
                                      avg_risk=("risk", "mean")).sort_values("exposure", ascending=False)
    st.dataframe(e.round(1), width="stretch",
                 column_config={"exposure": st.column_config.NumberColumn("Exposure", format="$%.0f"),
                                "beyond_life_pct": st.column_config.NumberColumn("% beyond life", format="%.0f%%")})
with col2:
    st.markdown("**% of components beyond expected life**")
    site_col = "source_site" if df["source_site"].nunique() > 1 else "site"
    p = df.groupby(site_col)["status"].apply(lambda s: (s == "Overdue").mean() * 100).sort_values().tail(15)
    fig = go.Figure(go.Bar(y=p.index.astype(str), x=p.values, orientation="h", marker_color=COLORS["critical"]))
    fig.update_layout(height=380, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="% beyond expected life")
    show_chart(fig)

# ------------------------------------------------------------------ action lists
st.markdown("---")
st.subheader("Action lists")
cols = ["cmp_id", "source_site", "site", "property", "comp. group", "component", "Condition", "criticality_tier",
        "status", "years_overdue", "due", "risk", "next_action", "cost"]
cfg = {"cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
       "due": st.column_config.NumberColumn("Due year", format="%d")}
tabs = st.tabs(["Overdue critical", "Approaching EOL — high criticality", "High-risk components",
                "Inspection priority", "Next action — all"])
with tabs[0]:
    t = df[od & crit].sort_values(["years_overdue", "cost"], ascending=False)
    st.caption(f"{len(t):,} components · {money(t['cost'].sum())}")
    st.dataframe(t[cols].head(2000), hide_index=True, width="stretch", column_config=cfg)
    lp.download(t[cols], "Download (CSV)", "overdue_critical.csv", "crh_dl1")
with tabs[1]:
    t = df[appr & crit_hi].sort_values(["rul", "risk"], ascending=[True, False])
    st.caption(f"{len(t):,} components · {money(t['cost'].sum())}")
    st.dataframe(t[cols].head(2000), hide_index=True, width="stretch", column_config=cfg)
    lp.download(t[cols], "Download (CSV)", "approaching_eol_critical.csv", "crh_dl2")
with tabs[2]:
    t = df[hi].sort_values("risk", ascending=False)
    st.caption(f"{len(t):,} components · {money(t['cost'].sum())}")
    st.dataframe(t[cols].head(2000), hide_index=True, width="stretch", column_config=cfg)
    lp.download(t[cols], "Download (CSV)", "high_risk.csv", "crh_dl3")
with tabs[3]:
    st.caption("Components to inspect first: high criticality, close to or past end of life, and a survey that is "
               "old or missing. See the Re-survey & Inspection Planner for a property-level plan.")
    stale = df["survey_age"].fillna(99)
    score = (df["criticality_score"] * 0.4 + df["consumed"].clip(upper=1.5).fillna(1) / 1.5 * 100 * 0.35
             + (stale.clip(upper=10) / 10 * 100) * 0.25)
    t = df.assign(inspection_score=score.round(1), survey_age_yrs=df["survey_age"]).sort_values(
        "inspection_score", ascending=False)
    c2 = ["inspection_score", "survey_age_yrs"] + cols
    st.dataframe(t[c2].head(1000), hide_index=True, width="stretch", column_config=cfg)
    lp.download(t[c2].head(20000), "Download top 20,000 (CSV)", "inspection_priority.csv", "crh_dl4")
with tabs[4]:
    a = df.groupby("next_action").agg(components=("cmp_id", "size"), cost=("cost", "sum")).sort_values(
        "components", ascending=False)
    st.dataframe(a, width="stretch", column_config={"cost": st.column_config.NumberColumn("Cost", format="$%.0f")})
    pick = st.selectbox("Show components for action", a.index.tolist(), key="crh_act")
    t = df[df["next_action"] == pick].sort_values("risk", ascending=False)
    st.dataframe(t[cols].head(2000), hide_index=True, width="stretch", column_config=cfg)
    lp.download(t[cols], "Download (CSV)", "next_action.csv", "crh_dl5")
