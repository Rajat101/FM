import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS, YEARS_INT

core, df, settings, ref = lp.page_setup("Average Life Benchmarking",
                                        "Average life benchmarking — system versus standard", "alb", needs_ref=True)
st.caption("Compares the source system's base lives and renewal dates with the standard average life for each "
           "asset type. Neither is assumed correct — the gaps show where to look.")

# ------------------------------------------------------------------ coverage
src = df["avg_life_source"].value_counts()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Matched by name", f"{src.get('Exact match', 0) + src.get('Name match (loose)', 0):,}",
          f"{(src.get('Exact match', 0) + src.get('Name match (loose)', 0)) / len(df) * 100:.0f}% of components",
          delta_color="off")
c2.metric("Group median used", f"{src.get('Group median', 0):,}")
c3.metric("No standard life", f"{src.get('Not found', 0):,}")
c4.metric("Cost covered", f"{df.loc[df['std_life'].notna(), 'cost'].sum() / max(df['cost'].sum(), 1) * 100:.1f}%")
with st.expander("Components without a name match"):
    um = df[~df["avg_life_source"].isin(["Exact match", "Name match (loose)"])].groupby(
        ["component", "comp. group", "avg_life_source"]).agg(components=("cmp_id", "size"), cost=("cost", "sum"),
                                                              life_used=("avg_life", "first")).reset_index()
    st.dataframe(um.sort_values("components", ascending=False), hide_index=True, width="stretch",
                 column_config={"cost": st.column_config.NumberColumn(format="$%.0f")})
    st.caption("'Group median' = the median standard life of the matching taxonomy group. Add these names to the "
               "Asset Life file to match them exactly.")

# ------------------------------------------------------------------ headline: forecast comparison
st.markdown("---")
st.subheader("System forecast versus standard-life forecast")
sysd, stdd = lp.apply_basis(df, "sys"), lp.apply_basis(df, "std")
bs, bd = sysd["backlog"].sum(), stdd["backlog"].sum()
a_sys, a_std = lp.annual(sysd, "sys")["cost"], lp.annual(stdd, "std")["cost"]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Backlog — system", money(bs), f"{(sysd['status'] == 'Overdue').sum():,} components", delta_color="off")
k2.metric("Backlog — standard life", money(bd), f"{(stdd['status'] == 'Overdue').sum():,} components",
          delta_color="off")
k3.metric("Hidden backlog", money(bd - bs), "standard − system", delta_color="inverse" if bd > bs else "normal")
k4.metric("10-yr need: standard − system", money((bd + a_std.iloc[:10].sum()) - (bs + a_sys.iloc[:10].sum())),
          "incl. backlog", delta_color="off")
fig = go.Figure()
fig.add_trace(go.Bar(x=YEARS_INT, y=a_sys / 1e6, name="System forecast", marker_color=COLORS["accent"]))
fig.add_trace(go.Bar(x=YEARS_INT, y=a_std / 1e6, name="Standard life", marker_color=COLORS["warn"]))
fig.add_trace(go.Scatter(x=YEARS_INT, y=(a_std.cumsum() + bd - a_sys.cumsum() - bs) / 1e6,
                         name="Cumulative gap incl. backlog", yaxis="y2", line=dict(color=COLORS["text"], width=2)))
fig.update_layout(barmode="group", height=380, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$M per year",
                  yaxis2=dict(title="Cumulative gap $M", overlaying="y", side="right", showgrid=False),
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
show_chart(fig)
st.caption("Both forecasts in today's dollars, built the same way: replacement cost in the due year and every "
           "life-cycle after it; anything due before 2026 counts as backlog.")

ct = pd.crosstab(df["sys_status"], df["std_status"]).reindex(index=lp.STATUS_ORDER, columns=lp.STATUS_ORDER,
                                                               fill_value=0)
st.markdown("**Do the two views agree?** Rows = system status, columns = standard-life status.")
st.dataframe(ct, width="stretch")
agree = np.trace(ct.values) / max(ct.values.sum(), 1)
st.caption(f"The two views give the same status for {agree*100:.0f}% of components.")

# ------------------------------------------------------------------ life comparison by asset type
st.markdown("---")
st.subheader("Base life sanity check")
thr = st.slider("Flag when system life differs from standard by more than (%)", 10, 100, 30, 5, key="alb_thr")
g = df.dropna(subset=["std_life", "sys_life"]).groupby("component").agg(
    components=("cmp_id", "size"), comp_group=("comp. group", "first"), system_life=("sys_life", "median"),
    system_life_min=("sys_life", "min"), system_life_max=("sys_life", "max"),
    distinct_system_lives=("sys_life", "nunique"), standard_life=("std_life", "first"), cost=("cost", "sum"),
    backlog_system=("sys_backlog", "sum"), backlog_standard=("std_backlog", "sum"))
g["difference_yrs"] = g["system_life"] - g["standard_life"]
g["difference_pct"] = (g["difference_yrs"] / g["standard_life"] * 100).round(0)
g["backlog_impact"] = g["backlog_standard"] - g["backlog_system"]
g["verdict"] = np.select([g["difference_pct"] > thr, g["difference_pct"] < -thr],
                         ["System longer", "System shorter"], "Within tolerance")
v = g["verdict"].value_counts()
m1, m2, m3 = st.columns(3)
m1.metric("Asset types within tolerance", f"{v.get('Within tolerance', 0):,}",
          f"{g.loc[g['verdict'] == 'Within tolerance', 'components'].sum():,} components", delta_color="off")
m2.metric("System life longer", f"{v.get('System longer', 0):,}",
          f"{g.loc[g['verdict'] == 'System longer', 'components'].sum():,} components", delta_color="off")
m3.metric("System life shorter", f"{v.get('System shorter', 0):,}",
          f"{g.loc[g['verdict'] == 'System shorter', 'components'].sum():,} components", delta_color="off")

fig = go.Figure()
for verdict, color in [("Within tolerance", COLORS["good"]), ("System longer", COLORS["critical"]),
                       ("System shorter", COLORS["warn"])]:
    s = g[g["verdict"] == verdict]
    fig.add_trace(go.Scatter(x=s["standard_life"], y=s["system_life"], mode="markers", name=verdict, text=s.index,
                             marker=dict(size=np.clip(np.sqrt(s["cost"] / 1e4), 5, 45), color=color, opacity=0.65),
                             customdata=np.stack([s["components"], s["cost"]], axis=-1),
                             hovertemplate="<b>%{text}</b><br>Standard %{x} yrs · System %{y} yrs<br>"
                                           "%{customdata[0]:,} components · $%{customdata[1]:,.0f}<extra></extra>"))
mx = float(max(g["standard_life"].max(), g["system_life"].max(), 10)) if len(g) else 100
fig.add_trace(go.Scatter(x=[0, mx], y=[0, mx], mode="lines", line=dict(dash="dash", color=COLORS["text_muted"]),
                         showlegend=False, hoverinfo="skip"))
fig.update_layout(height=440, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Standard average life (yrs)",
                  yaxis_title="System base life — median (yrs)", legend=dict(orientation="h", yanchor="bottom", y=1.02))
show_chart(fig)
st.caption("Bubble = asset type, sized by replacement cost. On the dashed line = system and standard agree.")

sort_by = st.radio("Sort mismatches by", ["Replacement cost", "Backlog impact", "Size of difference"],
                   horizontal=True, key="alb_sort")
sk = {"Replacement cost": "cost", "Backlog impact": "backlog_impact", "Size of difference": "difference_pct"}[sort_by]
mm = g[g["verdict"] != "Within tolerance"].copy()
mm = mm.reindex(mm[sk].abs().sort_values(ascending=False).index)
st.dataframe(mm, width="stretch", column_config={
    "cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
    "backlog_system": st.column_config.NumberColumn(format="$%.0f"),
    "backlog_standard": st.column_config.NumberColumn(format="$%.0f"),
    "backlog_impact": st.column_config.NumberColumn("Backlog impact", format="$%.0f")})
lp.download(mm.reset_index(), "Download mismatches (CSV)", "base_life_mismatches.csv", "alb_dl1")

inc = g[g["distinct_system_lives"] > 1].sort_values("components", ascending=False)
if len(inc):
    st.markdown(f"**{len(inc)} asset types have more than one base life in the system** "
                f"({inc['components'].sum():,} components) — the same item is being given different lives.")
    st.dataframe(inc[["components", "system_life_min", "system_life_max", "distinct_system_lives", "standard_life"]],
                 width="stretch")

# ------------------------------------------------------------------ survey reset exposure
st.markdown("---")
st.subheader("Survey-reset exposure")
st.caption("Condition-based (C) components whose system renewal date is far later than construction year + "
           "standard life — the pattern the SME described, where a recent survey resets the clock.")
gap_thr = st.slider("Flag when the system date is later than the standard date by at least (years)", 3, 40, 10,
                    key="alb_gap")
cm = df["calc_method"].astype(str).str.upper().str.startswith("C")
ex = df[cm & (df["forecast_gap_years"] >= gap_thr)]
e1, e2, e3, e4 = st.columns(4)
e1.metric("Components flagged", f"{len(ex):,}")
e2.metric("Replacement value", money(ex["cost"].sum()))
e3.metric("Of which overdue on standard life", f"{(ex['std_status'] == 'Overdue').sum():,}")
e4.metric("Critical / high", f"{ex['criticality_tier'].isin(['Critical', 'High']).sum():,}")
if len(ex):
    col1, col2 = st.columns(2)
    with col1:
        bg = ex.groupby("comp. group")["cost"].sum().sort_values()
        fig = go.Figure(go.Bar(y=bg.index, x=bg.values / 1e6, orientation="h", marker_color=COLORS["warn"]))
        fig.update_layout(height=360, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="$M flagged")
        show_chart(fig)
    with col2:
        sy = ex.groupby(ex["cmp_survey_year"].astype(int))["cmp_id"].size()
        fig = go.Figure(go.Bar(x=sy.index.astype(str), y=sy.values, marker_color=COLORS["steel"]))
        fig.update_layout(height=360, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Survey year (0 = none)",
                          yaxis_title="Components flagged")
        show_chart(fig)
    ranked = ex.assign(exposure=ex["cost"] * ex["criticality_score"] / 100).sort_values("exposure", ascending=False)
    cols = ["cmp_id", "source_site", "property", "component", "Condition", "cmp_construction_year", "cmp_survey_year",
            "sys_life", "std_life", "sys_due", "std_due", "forecast_gap_years", "criticality_tier", "cost"]
    st.dataframe(ranked[cols].head(2000), hide_index=True, width="stretch",
                 column_config={"cost": st.column_config.NumberColumn(format="$%.0f"),
                                "sys_due": st.column_config.NumberColumn("System due", format="%d"),
                                "std_due": st.column_config.NumberColumn("Standard due", format="%d")})
    lp.download(ranked[cols], "Download (CSV)", "survey_reset_exposure.csv", "alb_dl2")

# ------------------------------------------------------------------ cross-site
st.markdown("---")
st.subheader("Cross-site benchmarking")
site_col = "source_site" if df["source_site"].nunique() > 1 else "site"
if site_col == "site":
    st.caption("One file loaded — comparing the sites inside it. Upload more files to compare whole sites.")
sb = df.groupby(site_col).agg(
    components=("cmp_id", "size"),
    life_ratio=("life_gap_years", lambda s: (df.loc[s.index, "sys_life"] / df.loc[s.index, "std_life"]).median()),
    beyond_std_pct=("std_status", lambda s: (s == "Overdue").mean() * 100),
    beyond_sys_pct=("sys_status", lambda s: (s == "Overdue").mean() * 100),
    avg_life_used_std=("std_consumed", lambda s: s.clip(upper=3).mean() * 100),
    backlog_std=("std_backlog", "sum"), backlog_sys=("sys_backlog", "sum"))
sb["hidden_backlog"] = sb["backlog_std"] - sb["backlog_sys"]
sb["hidden_backlog_per_component"] = sb["hidden_backlog"] / sb["components"]
sb = sb[sb["components"] >= 20].sort_values("hidden_backlog", ascending=False)
col1, col2 = st.columns(2)
with col1:
    t = sb.head(15).sort_values("life_ratio")
    fig = go.Figure(go.Bar(y=t.index.astype(str), x=t["life_ratio"], orientation="h",
                           marker_color=np.where(t["life_ratio"] > 1, COLORS["critical"], COLORS["good"])))
    fig.add_vline(x=1, line_dash="dash", line_color=COLORS["text_muted"])
    fig.update_layout(height=400, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="System life ÷ standard life (median)",
                      title=dict(text="Does the system run assets longer than standard?", font=dict(size=13)))
    show_chart(fig)
with col2:
    t = sb.head(15).sort_values("hidden_backlog")
    fig = go.Figure(go.Bar(y=t.index.astype(str), x=t["hidden_backlog"] / 1e6, orientation="h",
                           marker_color=COLORS["warn"]))
    fig.update_layout(height=400, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="$M",
                      title=dict(text="Hidden backlog (standard − system)", font=dict(size=13)))
    show_chart(fig)
st.dataframe(sb.round(2), width="stretch", column_config={
    "backlog_std": st.column_config.NumberColumn(format="$%.0f"),
    "backlog_sys": st.column_config.NumberColumn(format="$%.0f"),
    "hidden_backlog": st.column_config.NumberColumn(format="$%.0f"),
    "hidden_backlog_per_component": st.column_config.NumberColumn(format="$%.0f"),
    "beyond_std_pct": st.column_config.NumberColumn("% beyond std life", format="%.0f%%"),
    "beyond_sys_pct": st.column_config.NumberColumn("% overdue (system)", format="%.0f%%"),
    "avg_life_used_std": st.column_config.NumberColumn("Avg. life used (std)", format="%.0f%%")})

# ------------------------------------------------------------------ by category
st.markdown("---")
st.subheader("Average life benchmarking by asset category")
cat = df.dropna(subset=["std_life"]).groupby("comp. group").agg(
    components=("cmp_id", "size"), standard_life_median=("std_life", "median"),
    system_life_median=("sys_life", "median"), avg_age=("asset_age", "mean"),
    beyond_std_pct=("std_status", lambda s: (s == "Overdue").mean() * 100))
cat["age_vs_standard"] = cat["avg_age"] / cat["standard_life_median"]
st.dataframe(cat.round(1), width="stretch",
             column_config={"beyond_std_pct": st.column_config.NumberColumn("% beyond std life", format="%.0f%%")})
