import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS, YEARS_INT

core, df, settings, ref = lp.page_setup("Replacement Pipeline", "Replacement pipeline — what is due, when, and where",
                                        "rpl")
b = settings["basis"]
ycols = lp.year_cols(b)
st.caption("Replacements due this year and over the next 1, 3, 5 and 10 years, the annual pipeline, and "
           "where the backlog sits.")
lp.basis_note(settings)

# ------------------------------------------------------------------ due windows (first replacement per component)
od = df[df["status"] == "Overdue"]
due_year = df["due"]
st.markdown("##### Due for replacement")
cols = lp.metric_cols(6)
cols[0].metric("Backlog (overdue)", f"{len(od):,}", money(df["backlog"].sum()), delta_color="off")
for col, (label, h) in zip(cols[1:], [("This year", 0), ("Within 1 yr", 1), ("Within 3 yrs", 3),
                                       ("Within 5 yrs", 5), ("Within 10 yrs", 10)]):
    m = due_year.between(lp.CY, lp.CY + h) & df["valid"]
    col.metric(f"{label} ({lp.CY}{'' if h == 0 else '–' + str(lp.CY + h)})", f"{m.sum():,}",
               money(df.loc[m, "cost"].sum()), delta_color="off")
st.caption("Counts are components whose next end-of-life falls in the window (not yet overdue). "
           "The value under each count is replacement cost.")

# ------------------------------------------------------------------ annual pipeline
st.markdown("---")
st.subheader("Annual replacement pipeline")
annual = lp.annual(df, b)["cost"]
jobs = lp.annual_counts(df, b)
fig = go.Figure()
fig.add_trace(go.Bar(x=YEARS_INT, y=annual / 1e6, name="Replacement cost ($M)", marker_color=COLORS["accent"]))
fig.add_trace(go.Scatter(x=YEARS_INT, y=jobs, name="Replacements (count)", yaxis="y2",
                         line=dict(color=COLORS["warn"], width=3)))
if ref is not None:
    other = "std" if b == "sys" else "sys"
    fig.add_trace(go.Scatter(x=YEARS_INT, y=lp.annual(df, other)["cost"] / 1e6,
                             name=f"{'Standard life' if other == 'std' else 'System forecast'} ($M)",
                             line=dict(color=COLORS["steel"], width=2, dash="dash")))
fig.update_layout(height=380, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$M",
                  yaxis2=dict(title="Replacements", overlaying="y", side="right", showgrid=False),
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
show_chart(fig)
st.caption("Includes repeat replacements within the window (e.g. a 5-year item due 2027 also appears in 2032). "
           "Backlog is shown separately and is not inside these bars.")

# ------------------------------------------------------------------ workload by year and group
st.subheader("Replacement workload by year")
split = st.radio("Split by", ["comp. group", "source_site", "site"], horizontal=True, key="rpl_split",
                 format_func=lambda c: {"comp. group": "Component group", "source_site": "Site (file)",
                                        "site": "Site (in data)"}[c])
mode = st.radio("Measure", ["Number of replacements", "Replacement cost"], horizontal=True, key="rpl_mode")
grp = lp.top_n_other(df, split, "cost", 8)
d2 = df.assign(_g=grp)
if mode == "Replacement cost":
    m = lp.annual(d2, b, "_g") / 1e6
    ytitle = "$M"
else:
    m = (d2[ycols] > 0).groupby(d2["_g"]).sum().T
    m.index = YEARS_INT
    ytitle = "Replacements"
fig = go.Figure()
for g in m.columns:
    fig.add_trace(go.Bar(x=m.index, y=m[g], name=str(g)))
fig.update_layout(barmode="stack", height=380, margin=dict(t=10, l=0, r=0, b=0), yaxis_title=ytitle,
                  legend=dict(orientation="h", yanchor="bottom", y=-0.35))
show_chart(fig)
peak = m.sum(axis=1)
st.caption(f"Peak year: **{int(peak.idxmax())}** ({peak.max():,.0f} {ytitle}). "
           f"Average: {peak.mean():,.0f} {ytitle} per year.")

# ------------------------------------------------------------------ backlog by site and category
st.markdown("---")
st.subheader("Replacement backlog")
if len(od) == 0:
    st.success("No overdue components under this basis and filter.")
else:
    col1, col2 = st.columns(2)
    with col1:
        site_col = "source_site" if df["source_site"].nunique() > 1 else "site"
        s = od.groupby(site_col).agg(components=("cmp_id", "size"), value=("backlog", "sum")).sort_values("value")
        s = s.tail(15)
        fig = go.Figure(go.Bar(y=s.index.astype(str), x=s["value"] / 1e6, orientation="h",
                               marker_color=COLORS["critical"], text=[f"{v:,}" for v in s["components"]],
                               textposition="outside"))
        fig.update_layout(height=420, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="Backlog $M",
                          title=dict(text=f"By {'site (file)' if site_col == 'source_site' else 'site'} — top 15",
                                     font=dict(size=13)))
        show_chart(fig)
    with col2:
        c = od.groupby("comp. group").agg(components=("cmp_id", "size"), value=("backlog", "sum")).sort_values("value")
        fig = go.Figure(go.Bar(y=c.index, x=c["value"] / 1e6, orientation="h", marker_color=COLORS["warn"],
                               text=[f"{v:,}" for v in c["components"]], textposition="outside"))
        fig.update_layout(height=420, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="Backlog $M",
                          title=dict(text="By component group", font=dict(size=13)))
        show_chart(fig)
    st.caption("Bar length = backlog value; label = number of overdue components.")

    age_bins = pd.cut(od["years_overdue"], bins=[0, 2, 5, 10, 20, 1000], right=True,
                      labels=["≤2 yrs", "3–5 yrs", "6–10 yrs", "11–20 yrs", "20+ yrs"])
    ab = od.groupby(age_bins, observed=False).agg(components=("cmp_id", "size"), value=("backlog", "sum"))
    st.markdown("**How long the backlog has been waiting**")
    cols = st.columns(len(ab))
    for col, (k, r) in zip(cols, ab.iterrows()):
        col.metric(str(k), f"{int(r['components']):,}", money(r["value"]), delta_color="off")

# ------------------------------------------------------------------ list
st.markdown("---")
st.subheader("Replacement list")
horizon = st.select_slider("Show components due", ["Overdue only", "This year", "1 year", "3 years", "5 years",
                                                   "10 years"], value="3 years", key="rpl_h")
hmap = {"Overdue only": -1, "This year": 0, "1 year": 1, "3 years": 3, "5 years": 5, "10 years": 10}
h = hmap[horizon]
mask = df["status"] == "Overdue"
if h >= 0:
    mask = mask | (df["valid"] & due_year.between(lp.CY, lp.CY + h))
lst = df[mask].sort_values(["due", "risk"], ascending=[True, False])
st.caption(f"{len(lst):,} components, {money(lst['cost'].sum())} replacement cost.")
cols_show = ["cmp_id", "source_site", "site", "property", "comp. group", "component", "Condition", "due",
             "planned_year", "years_overdue", "criticality_tier", "risk", "next_action", "cost"]
st.dataframe(lst[cols_show].head(2000), hide_index=True, width="stretch",
             column_config={"cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
                            "due": st.column_config.NumberColumn("Due year", format="%d"),
                            "planned_year": st.column_config.NumberColumn("Replacement year", format="%d")})
lp.download(lst[cols_show], "Download list (CSV)", "replacement_list.csv", "rpl_dl")
