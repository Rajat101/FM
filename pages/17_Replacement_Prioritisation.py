import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS, YEARS_INT

core, df, settings, ref = lp.page_setup("Replacement Prioritisation",
                                        "Replacement prioritisation — ranking and schedule", "rpr")
b = settings["basis"]
st.caption("Rank every component by a priority score you control, then build a replacement schedule that "
           "respects your annual budget and crew capacity.")
lp.basis_note(settings)

# ------------------------------------------------------------------ weights
with st.expander("Priority score weights", expanded=True):
    st.caption("Each factor is scaled 0–100, then combined using these weights.")
    w1, w2, w3, w4, w5 = st.columns(5)
    w_risk = w1.slider("Lifecycle risk", 0.0, 1.0, 0.40, 0.05, key="rpr_wr",
                       help="Likelihood (life used / condition) × criticality (consequence × safety)")
    w_od = w2.slider("Years overdue", 0.0, 1.0, 0.25, 0.05, key="rpr_wo")
    w_cond = w3.slider("Condition", 0.0, 1.0, 0.15, 0.05, key="rpr_wc")
    w_crit = w4.slider("Criticality", 0.0, 1.0, 0.10, 0.05, key="rpr_wk")
    w_eff = w5.slider("Risk per $", 0.0, 1.0, 0.10, 0.05, key="rpr_we", help="Favours cheap, high-risk fixes")

prio = lp.priority_score(df, w_risk, w_od, w_cond, w_crit, w_eff)
ranked = df.assign(priority=prio).sort_values("priority", ascending=False)
ranked["rank"] = np.arange(1, len(ranked) + 1)

# ------------------------------------------------------------------ ranking
st.subheader("Replacement prioritisation ranking")
scope = st.radio("Rank", ["Overdue and due within 5 years", "Overdue only", "All components"], horizontal=True,
                 key="rpr_scope")
if scope == "Overdue only":
    r = ranked[ranked["status"] == "Overdue"]
elif scope.startswith("Overdue and"):
    r = ranked[(ranked["status"] == "Overdue") | (ranked["valid"] & (ranked["due"] <= lp.CY + 5))]
else:
    r = ranked
c1, c2, c3, c4 = st.columns(4)
c1.metric("Components ranked", f"{len(r):,}")
c2.metric("Top 100 — replacement cost", money(r.head(100)["cost"].sum()))
c3.metric("Top 100 — critical / high", f"{r.head(100)['criticality_tier'].isin(['Critical', 'High']).sum()}")
c4.metric("Avg. priority (top 100)", f"{r.head(100)['priority'].mean():.0f} / 100")

cols_show = ["rank", "priority", "cmp_id", "source_site", "site", "property", "comp. group", "component",
             "Condition", "criticality_tier", "status", "years_overdue", "due", "risk", "next_action", "cost"]
st.dataframe(r[cols_show].head(1000), hide_index=True, width="stretch",
             column_config={"cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
                            "priority": st.column_config.ProgressColumn("Priority", min_value=0, max_value=100,
                                                                        format="%.0f"),
                            "due": st.column_config.NumberColumn("Due year", format="%d")})
lp.download(r[cols_show], "Download ranking (CSV)", "replacement_ranking.csv", "rpr_dl_rank")

g = r.head(500).groupby("comp. group")["cost"].agg(["size", "sum"]).sort_values("sum")
fig = go.Figure(go.Bar(y=g.index, x=g["sum"] / 1e6, orientation="h", marker_color=COLORS["accent"],
                       text=[f"{v}" for v in g["size"]], textposition="outside"))
fig.update_layout(height=320, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="$M",
                  title=dict(text="What the top 500 are made of (label = count)", font=dict(size=13)))
show_chart(fig)

# ------------------------------------------------------------------ schedule optimisation
st.markdown("---")
st.subheader("Replacement schedule optimisation")
st.caption("Each year, components that are due compete for that year's budget in priority order. Anything that "
           "doesn't fit waits a year (its cost escalating). Optional crew capacity caps the number of jobs a year.")
s1, s2, s3, s4 = st.columns(4)
suggested = lp.suggested_budget(df)
budget = s1.number_input("Annual budget ($M)", 0.1, 2000.0, suggested, 0.5, key="rpr_budget",
                         help=f"Default = average annual forecast + backlog spread over 10 years "
                              f"(${suggested:,.1f}M for the current filter).") * 1e6
growth = s2.slider("Budget growth / yr (%)", -10, 15, 0, key="rpr_growth") / 100
esc = s3.slider("Cost escalation while waiting / yr (%)", 0, 15, 3, key="rpr_esc") / 100
cap_on = s4.toggle("Limit jobs per year (crew capacity)", value=False, key="rpr_capon")
max_jobs = None
if cap_on:
    max_jobs = st.number_input("Max replacements per year", 100, 100000, 3000, 100, key="rpr_cap")

big = df[df["valid"] & (df["cost"] > budget)]
if len(big):
    st.warning(f"{len(big):,} single item{'s' if len(big) != 1 else ''} cost{'' if len(big) != 1 else 's'} more than the annual budget ({money(big['cost'].sum())}, largest: "
               f"{big.nlargest(1, 'cost')['component'].iloc[0]} at {money(big['cost'].max())}). They can't be "
               f"funded inside this budget — the Budget Optimiser can plan them as separate projects.")
key = ("rpr", lp.data_key(df), round(w_risk, 2), round(w_od, 2), round(w_cond, 2), round(w_crit, 2),
       round(w_eff, 2), budget, growth, esc, max_jobs)
res, plan = lp.memo(key, lp.schedule, df, budget, growth, max_jobs, esc, "priority", prio)

end = res.iloc[-1]
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Replacements funded (20 yrs)", f"{int(res['funded'].sum()):,}")
m2.metric("Total spend", money(res["spend"].sum()))
m3.metric("Backlog in 2045", money(end["backlog_value"]), f"{int(end['backlog_count']):,} components",
          delta_color="off")
m4.metric("Critical/high still waiting (2045)", f"{int(end['critical_backlog']):,}")
funded = plan.dropna(subset=["scheduled_year"])
m5.metric("Avg. wait after due date", f"{funded['slip_years'].mean():.1f} yrs" if len(funded) else "–")

fig = go.Figure()
fig.add_trace(go.Bar(x=res["year"], y=res["spend"] / 1e6, name="Funded spend", marker_color=COLORS["accent"]))
fig.add_trace(go.Scatter(x=res["year"], y=res["backlog_value"] / 1e6, name="Backlog value",
                         line=dict(color=COLORS["critical"], width=3)))
fig.add_trace(go.Scatter(x=res["year"], y=res["budget"] / 1e6, name="Budget",
                         line=dict(color=COLORS["text_muted"], dash="dot")))
fig.update_layout(height=360, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$M",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
show_chart(fig)

col1, col2 = st.columns(2)
with col1:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=res["year"], y=res["due_this_year"], name="Falling due", marker_color=COLORS["steel"]))
    fig.add_trace(go.Bar(x=res["year"], y=res["funded"], name="Scheduled", marker_color=COLORS["good"]))
    fig.update_layout(barmode="group", height=300, margin=dict(t=30, l=0, r=0, b=0), yaxis_title="Components",
                      title=dict(text="Workload: falling due vs scheduled", font=dict(size=13)),
                      legend=dict(orientation="h", yanchor="bottom", y=-0.3))
    show_chart(fig)
with col2:
    slip = funded["slip_years"].clip(upper=10).value_counts().sort_index()
    fig = go.Figure(go.Bar(x=slip.index.astype(int), y=slip.values, marker_color=COLORS["warn"]))
    fig.update_layout(height=300, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="Years waited after due (10 = 10+)",
                      yaxis_title="Components", title=dict(text="How long replacements wait", font=dict(size=13)))
    show_chart(fig)

st.caption("The schedule covers each component's next replacement. Overdue components are due from "
           f"{lp.CY}. Repeat cycles later in the window are in the Capital Plan forecast.")
st.markdown("**Schedule**")
yr_pick = st.selectbox("Show year", ["All"] + YEARS_INT + ["Not funded by 2045"], key="rpr_year")
p = plan
if yr_pick == "Not funded by 2045":
    p = plan[plan["scheduled_year"].isna()]
elif yr_pick != "All":
    p = plan[plan["scheduled_year"] == yr_pick]
st.dataframe(p.head(2000), hide_index=True, width="stretch",
             column_config={"cost": st.column_config.NumberColumn("Cost today", format="$%.0f"),
                            "paid_cost": st.column_config.NumberColumn("Cost when done", format="$%.0f"),
                            "due_year": st.column_config.NumberColumn("Due", format="%d"),
                            "scheduled_year": st.column_config.NumberColumn("Scheduled", format="%d")})
lp.download(p, "Download schedule (CSV)", "replacement_schedule.csv", "rpr_dl_plan")
