import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS, YEARS_INT

core, df, settings, ref = lp.page_setup("Budget Optimiser", "Budget optimiser — get the most risk reduction per dollar",
                                        "bop")
b = settings["basis"]
st.caption("Compare funding strategies, find the budget needed to clear the backlog, see where the money goes, "
           "and test how sensitive the plan is to budget, escalation and lifespan assumptions.")
lp.basis_note(settings)

s1, s2, s3, s4 = st.columns(4)
suggested = lp.suggested_budget(df)
budget = s1.number_input("Annual budget ($M)", 0.1, 2000.0, suggested, 0.5, key="bop_budget") * 1e6
growth = s2.slider("Budget growth / yr (%)", -10, 15, 0, key="bop_growth") / 100
esc = s3.slider("Cost escalation while waiting / yr (%)", 0, 15, 3, key="bop_esc") / 100
cap = s4.number_input("Max replacements / yr (0 = no limit)", 0, 100000, 0, 500, key="bop_cap")
max_jobs = int(cap) or None

big = df[df["valid"] & (df["cost"] > budget)]
if len(big):
    sep = st.toggle(f"Treat {len(big):,} single item{'s' if len(big) != 1 else ''} costing more than the annual budget as separate projects "
                    f"({money(big['cost'].sum())})", value=True, key="bop_sep",
                    help="An item bigger than the whole annual budget can never be funded from it. Turn this on "
                         "to plan it outside the annual programme.")
    with st.expander(f"Items larger than the annual budget ({len(big):,})"):
        st.dataframe(big.sort_values("cost", ascending=False)[
            ["cmp_id", "source_site", "property", "component", "qty", "unit", "rate", "cost", "due"]],
            hide_index=True, width="stretch",
            column_config={"cost": st.column_config.NumberColumn(format="dollar"),
                           "due": st.column_config.NumberColumn("Due", format="%d")})
        st.caption("Check these first: a very large qty × rate is often a data-entry error (see Data Quality & "
                   "Governance → outliers).")
    if sep:
        df = df[~df.index.isin(big.index)]
        df.attrs["basis"] = b
dk = lp.data_key(df)


def run(strategy, bud=budget, e=esc):
    return lp.memo(("bop", dk, strategy, bud, growth, e, max_jobs), lp.schedule, df, bud, growth, max_jobs, e,
                   strategy)


# ------------------------------------------------------------------ strategy comparison
st.markdown("---")
st.subheader("Budget allocation optimisation — which funding rule works best?")
with st.spinner("Running strategies..."):
    runs = {name: run(code) for name, code in lp.STRATEGIES.items()}
rows = []
for name, (res, plan) in runs.items():
    end = res.iloc[-1]
    f = plan.dropna(subset=["scheduled_year"])
    rows.append({"Strategy": name, "Replacements funded": int(res["funded"].sum()),
                 "Spend (20 yrs)": res["spend"].sum(), "Backlog 2045": end["backlog_value"],
                 "Risk still waiting 2045": end["backlog_risk"],
                 "Risk-years carried": res["backlog_risk"].sum(),
                 "Critical/high waiting 2045": int(end["critical_backlog"]),
                 "Avg. wait (yrs)": f["slip_years"].mean() if len(f) else np.nan})
comp = pd.DataFrame(rows).set_index("Strategy")
best = comp["Risk-years carried"].idxmin()
st.markdown(f'<div class="insight-card"><div class="headline">Best for risk under this budget: {best}</div>'
            f'<div class="detail">It carries the least risk over the 20 years (risk-years = sum of the lifecycle '
            f'risk scores of everything waiting, each year). Backlog in 2045: '
            f'{money(comp.loc[best, "Backlog 2045"])}.</div></div>', unsafe_allow_html=True)
st.write("")
st.dataframe(comp, width="stretch", column_config={
    "Spend (20 yrs)": st.column_config.NumberColumn(format="dollar"),
    "Backlog 2045": st.column_config.NumberColumn(format="dollar"),
    "Risk still waiting 2045": st.column_config.NumberColumn(format="localized"),
    "Risk-years carried": st.column_config.NumberColumn(format="localized"),
    "Avg. wait (yrs)": st.column_config.NumberColumn(format="%.1f")})
fig = go.Figure()
for name, (res, _) in runs.items():
    fig.add_trace(go.Scatter(x=res["year"], y=res["backlog_risk"], name=name, mode="lines",
                             line=dict(width=4 if name == best else 2)))
fig.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Risk waiting (sum of risk scores)",
                  legend=dict(orientation="h", yanchor="bottom", y=-0.4))
show_chart(fig)

# ------------------------------------------------------------------ allocation
st.subheader("Where the money goes")
strat_name = st.selectbox("Strategy", list(lp.STRATEGIES), index=list(lp.STRATEGIES).index(best), key="bop_strat")
res, plan = runs[strat_name]
f = plan.dropna(subset=["scheduled_year"])
by = st.radio("Allocate by", ["comp. group", "source_site", "site", "criticality_tier"], horizontal=True,
              key="bop_by", format_func={"comp. group": "Component group", "source_site": "Site (file)",
                                         "site": "Site (in data)", "criticality_tier": "Criticality"}.get)
top = f.groupby(by)["paid_cost"].sum().nlargest(8).index
alloc = f.assign(_g=f[by].where(f[by].isin(top), "Other")).pivot_table(
    index="scheduled_year", columns="_g", values="paid_cost", aggfunc="sum", fill_value=0)
fig = go.Figure()
for g in alloc.columns:
    fig.add_trace(go.Bar(x=alloc.index.astype(int), y=alloc[g] / 1e6, name=str(g)))
fig.update_layout(barmode="stack", height=360, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$M funded",
                  legend=dict(orientation="h", yanchor="bottom", y=-0.35))
show_chart(fig)
share = (f.groupby(by)["paid_cost"].sum() / max(f["paid_cost"].sum(), 1) * 100).sort_values(ascending=False)
st.dataframe(pd.DataFrame({"Share of 20-yr spend (%)": share.round(1),
                           "Funded": f.groupby(by).size().reindex(share.index),
                           "Spend": f.groupby(by)["paid_cost"].sum().reindex(share.index)}),
             width="stretch", column_config={"Spend": st.column_config.NumberColumn(format="dollar")})
lp.download(plan, "Download this strategy's schedule (CSV)", "optimised_schedule.csv", "bop_dl1")

# ------------------------------------------------------------------ multi-year investment
st.markdown("---")
st.subheader("Multi-year capital investment — budget needed to clear the backlog")
t1, t2 = st.columns([1, 2])
target = t1.selectbox("Clear everything due by", [2028, 2030, 2035, 2040, 2045], index=1, key="bop_target")
with st.spinner("Searching for the minimum budget..."):
    need = lp.memo(("bop_min", dk, target, esc, growth, lp.STRATEGIES[strat_name]), lp.min_budget_to_clear, df,
                   target, lp.STRATEGIES[strat_name], esc, growth)
t2.metric(f"Minimum flat annual budget to have nothing waiting by {target}", money(need),
          f"{(need / budget - 1) * 100:+.0f}% vs your budget" if budget else None, delta_color="inverse")
st.caption("Found by testing budgets until nothing that falls due by the target year is still waiting at the end "
           "of it. Uses the selected strategy, escalation and growth.")

# ------------------------------------------------------------------ sensitivity: budget
st.markdown("---")
st.subheader("What-if: budget increases or reductions")
mults = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
with st.spinner("Running budget scenarios..."):
    sens = []
    for m_ in mults:
        r_, p_ = run(lp.STRATEGIES[strat_name], budget * m_)
        sens.append({"Budget change": f"{(m_ - 1) * 100:+.0f}%", "Annual budget": budget * m_,
                     "Backlog 2045": r_.iloc[-1]["backlog_value"], "Risk-years": r_["backlog_risk"].sum(),
                     "Critical/high waiting 2045": int(r_.iloc[-1]["critical_backlog"]),
                     "Funded": int(r_["funded"].sum())})
sens = pd.DataFrame(sens)
col1, col2 = st.columns(2)
with col1:
    fig = go.Figure(go.Bar(x=sens["Budget change"], y=sens["Backlog 2045"] / 1e6, marker_color=COLORS["critical"],
                           text=[money(v) for v in sens["Backlog 2045"]], textposition="outside"))
    fig.update_layout(height=320, margin=dict(t=30, l=0, r=0, b=0), yaxis_title="Backlog in 2045 ($M)")
    show_chart(fig)
with col2:
    st.dataframe(sens.set_index("Budget change"), width="stretch", column_config={
        "Annual budget": st.column_config.NumberColumn(format="dollar"),
        "Backlog 2045": st.column_config.NumberColumn(format="dollar"),
        "Risk-years": st.column_config.NumberColumn(format="localized")})

# ------------------------------------------------------------------ sensitivity: escalation
st.subheader("Replacement schedule sensitivity — cost escalation")
with st.spinner("Running escalation scenarios..."):
    es = []
    for e_ in [0.0, 0.03, 0.06, 0.10]:
        r_, _ = run(lp.STRATEGIES[strat_name], budget, e_)
        es.append({"Escalation while waiting": f"{e_*100:.0f}%", "Backlog 2045": r_.iloc[-1]["backlog_value"],
                   "Funded": int(r_["funded"].sum()), "Risk-years": r_["backlog_risk"].sum()})
st.dataframe(pd.DataFrame(es).set_index("Escalation while waiting"), width="stretch", column_config={
    "Backlog 2045": st.column_config.NumberColumn(format="dollar"),
    "Risk-years": st.column_config.NumberColumn(format="localized")})

# ------------------------------------------------------------------ sensitivity: lifespans
st.markdown("---")
st.subheader("What-if: different average lifespans")
life_src = "std_life" if ref is not None else "sys_life"
st.caption(f"Age-based view using {'the standard average life' if ref is not None else 'the system base life'} "
           f"scaled up or down: shows how much the backlog and near-term need depend on the life assumption.")
cy = df["cmp_construction_year"].astype(float)
life = df[life_src].astype(float)
cost = df["cost"].astype(float)
ok = df["construction_year_valid"] & life.notna()
rows = []
for m_ in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]:
    due = cy + life * m_
    rows.append({"Life change": f"{(m_ - 1) * 100:+.0f}%",
                 "Overdue now": int((ok & (due < lp.CY)).sum()),
                 "Backlog now": cost[ok & (due < lp.CY)].sum(),
                 "Due within 5 yrs": cost[ok & due.between(lp.CY, lp.CY + 4)].sum(),
                 "Due within 10 yrs": cost[ok & due.between(lp.CY, lp.CY + 9)].sum()})
ls = pd.DataFrame(rows)
fig = go.Figure()
fig.add_trace(go.Bar(x=ls["Life change"], y=ls["Backlog now"] / 1e6, name="Backlog now", marker_color=COLORS["critical"]))
fig.add_trace(go.Bar(x=ls["Life change"], y=ls["Due within 10 yrs"] / 1e6, name="Due within 10 yrs",
                     marker_color=COLORS["accent"]))
fig.update_layout(barmode="group", height=320, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$M",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
show_chart(fig)
st.dataframe(ls.set_index("Life change"), width="stretch",
             column_config={c: st.column_config.NumberColumn(format="dollar") for c in
                            ["Backlog now", "Due within 5 yrs", "Due within 10 yrs"]})
