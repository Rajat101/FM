import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS, YEARS_INT

core, df, settings, ref = lp.page_setup("Capital Plan", "Capital plan — replacement expenditure and budget need",
                                        "cap")
b = settings["basis"]
ycols = lp.year_cols(b)
st.caption("Forecast annual replacement expenditure, 5- and 10-year capital forecasts, budget requirements, "
           "cost scenarios and the cost of deferring.")
lp.basis_note(settings)

base = lp.annual(df, b)["cost"]
backlog = df["backlog"].sum()

# ------------------------------------------------------------------ cost scenario controls
with st.expander("Cost scenario assumptions", expanded=True):
    a1, a2, a3 = st.columns(3)
    infl = a1.slider("Cost escalation / inflation per yr (%)", 0.0, 10.0, 3.0, 0.5, key="cap_infl") / 100
    cont = a2.slider("Contingency (%)", 0, 40, 10, 5, key="cap_cont") / 100
    clear_yrs = a3.slider("Clear the backlog over (years)", 1, 20, 5, key="cap_clear")
idx = np.arange(len(YEARS_INT))
esc_factor = (1 + infl) ** idx
nominal = base * esc_factor * (1 + cont)
backlog_per_yr = np.where(idx < clear_yrs, backlog * (1 + cont) / clear_yrs * esc_factor, 0)
requirement = nominal.to_numpy() + backlog_per_yr

# ------------------------------------------------------------------ KPIs
c1, c2, c3, c4, c5, c6 = lp.metric_cols(6)
c1.metric(f"Next year ({lp.CY})", money(base.iloc[0]))
c2.metric("5-year forecast", money(base.iloc[:5].sum()))
c3.metric("10-year forecast", money(base.iloc[:10].sum()))
c4.metric("20-year forecast", money(base.sum()))
c5.metric("Capital backlog", money(backlog))
c6.metric("Avg. annual budget need", money(requirement.mean()), "incl. escalation, contingency, backlog",
          delta_color="off")
st.caption("Forecast figures are in today's dollars. The budget need adds your escalation, contingency and "
           "backlog-clearance assumptions.")

# ------------------------------------------------------------------ annual forecast
st.markdown("---")
st.subheader("Forecast annual replacement expenditure")
split = st.radio("Split by", ["comp. group", "source_site", "exp_type"] if "exp_type" in df.columns else
                 ["comp. group", "source_site"], horizontal=True, key="cap_split",
                 format_func={"comp. group": "Component group", "source_site": "Site (file)",
                              "exp_type": "CapEx / OpEx"}.get)
grp = lp.top_n_other(df, split, "cost", 8)
m = lp.annual(df.assign(_g=grp), b, "_g") / 1e6
fig = go.Figure()
for g in m.columns:
    fig.add_trace(go.Bar(x=m.index, y=m[g], name=str(g)))
fig.add_trace(go.Scatter(x=YEARS_INT, y=requirement / 1e6, name="Annual budget need", mode="lines+markers",
                         line=dict(color=COLORS["critical"], width=3)))
if ref is not None:
    other = "std" if b == "sys" else "sys"
    fig.add_trace(go.Scatter(x=YEARS_INT, y=lp.annual(df, other)["cost"] / 1e6, mode="lines",
                             name=("Standard life" if other == "std" else "System forecast") + " (today's $)",
                             line=dict(color=COLORS["text"], width=2, dash="dash")))
fig.update_layout(barmode="stack", height=420, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$M",
                  legend=dict(orientation="h", yanchor="bottom", y=-0.35))
show_chart(fig)

# ------------------------------------------------------------------ 5/10-year by site and category
st.subheader("Replacement cost by site and asset category")
h = st.radio("Horizon", ["5 years", "10 years", "20 years"], horizontal=True, key="cap_h")
n = {"5 years": 5, "10 years": 10, "20 years": 20}[h]
site_col = "source_site" if df["source_site"].nunique() > 1 else "site"
tot = df[ycols[:n]].sum(axis=1)
pv = df.assign(_t=tot).pivot_table(index=site_col, columns="comp. group", values="_t", aggfunc="sum",
                                   fill_value=0)
pv["Total"] = pv.sum(axis=1)
pv = pv.sort_values("Total", ascending=False)
pv.loc["Total"] = pv.sum()
st.dataframe((pv / 1000).round(0), width="stretch",
             column_config={c: st.column_config.NumberColumn(c, format="$%.0fK") for c in pv.columns})
lp.download(pv.reset_index(), f"Download {h} table (CSV)", f"capex_{n}yr_by_site_category.csv", "cap_dl1")

# ------------------------------------------------------------------ budget requirement & variance
st.markdown("---")
st.subheader("Annual budget requirement and variance")
st.caption("Enter your planned or approved budget for each year to see the gap against what the forecast needs. "
           "Pre-filled with a flat budget — edit any cell.")
flat = st.number_input("Pre-fill planned budget ($M / yr)", 0.0, 2000.0,
                       float(round(requirement.mean() / 1e6 * 0.8, 1)), 0.5, key="cap_flat")
plan_df = pd.DataFrame({"Year": YEARS_INT, "Planned budget ($M)": [flat] * len(YEARS_INT)})
edited = st.data_editor(plan_df, hide_index=True, width="stretch", key=f"cap_editor_{flat}",
                        column_config={"Year": st.column_config.NumberColumn(disabled=True, format="%d")})
planned = edited["Planned budget ($M)"].to_numpy(dtype=float) * 1e6
var = planned - requirement
cum = var.cumsum()
v1, v2, v3 = st.columns(3)
v1.metric("Total requirement (20 yrs)", money(requirement.sum()))
v2.metric("Total planned (20 yrs)", money(planned.sum()))
v3.metric("Cumulative variance", money(cum[-1]), "surplus" if cum[-1] >= 0 else "shortfall",
          delta_color="normal" if cum[-1] >= 0 else "inverse")
fig = go.Figure()
fig.add_trace(go.Bar(x=YEARS_INT, y=var / 1e6, name="Annual variance",
                     marker_color=np.where(var >= 0, COLORS["good"], COLORS["critical"])))
fig.add_trace(go.Scatter(x=YEARS_INT, y=cum / 1e6, name="Cumulative", line=dict(color=COLORS["text"], width=2)))
fig.update_layout(height=320, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$M (planned − required)",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
show_chart(fig)

# ------------------------------------------------------------------ scenarios
st.markdown("---")
st.subheader("Replacement cost scenarios")
sc = pd.DataFrame({
    "Low (inflation −2 pts, no contingency)": base * (1 + max(infl - 0.02, 0)) ** idx,
    "Base (your assumptions)": nominal,
    "High (inflation +2 pts, contingency +15 pts)": base * (1 + infl + 0.02) ** idx * (1 + cont + 0.15),
}, index=YEARS_INT)
fig = go.Figure()
for col, color in zip(sc.columns, [COLORS["good"], COLORS["accent"], COLORS["critical"]]):
    fig.add_trace(go.Scatter(x=sc.index, y=sc[col].cumsum() / 1e6, name=col, line=dict(color=color, width=3)))
fig.update_layout(height=320, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Cumulative $M (nominal)",
                  legend=dict(orientation="h", yanchor="bottom", y=-0.35))
show_chart(fig)
st.dataframe(pd.DataFrame({k: [money(v.iloc[:5].sum()), money(v.iloc[:10].sum()), money(v.sum())]
                           for k, v in sc.items()}, index=["5-year", "10-year", "20-year"]), width="stretch")

# ------------------------------------------------------------------ deferral impact
st.markdown("---")
st.subheader("Deferred replacement cost impact")
d1, d2 = st.columns(2)
defer_yrs = d1.slider("Defer replacements by (years)", 1, 10, 3, key="cap_defer")
defer_share = d2.slider("Share of the next 5 years' replacements deferred (%)", 10, 100, 50, 10,
                        key="cap_share") / 100
pen = st.slider("Extra cost of waiting per year — escalation plus deterioration (%)", 0.0, 15.0,
                float(round(infl * 100 + 3, 1)), 0.5, key="cap_pen") / 100
deferred_now = base.iloc[:5].sum() * defer_share + backlog * defer_share
extra = deferred_now * ((1 + pen) ** defer_yrs - 1)
e1, e2, e3 = st.columns(3)
e1.metric("Value deferred", money(deferred_now))
e2.metric("Extra cost when finally done", money(extra), f"+{((1 + pen) ** defer_yrs - 1)*100:.0f}%",
          delta_color="inverse")
crit_share = df.loc[df["criticality_tier"].isin(["Critical", "High"]), ycols[:5]].sum().sum() / max(
    base.iloc[:5].sum(), 1)
e3.metric("Of which critical/high assets", f"{crit_share*100:.0f}%")
st.caption("Deferring doesn't remove cost — it moves it later and makes it larger. This view excludes the "
           "added failure and safety risk of running critical assets past end of life.")

# ------------------------------------------------------------------ trend
st.markdown("---")
st.subheader("Replacement expenditure trend")
blocks = pd.Series({f"{y}–{y+4}": base.loc[y:y + 4].sum() for y in range(YEARS_INT[0], YEARS_INT[-1] + 1, 5)})
col1, col2 = st.columns(2)
with col1:
    fig = go.Figure(go.Bar(x=blocks.index, y=blocks.values / 1e6, marker_color=COLORS["steel"],
                           text=[money(v) for v in blocks.values], textposition="outside"))
    fig.update_layout(height=320, margin=dict(t=30, l=0, r=0, b=0), yaxis_title="$M (today's $)",
                      title=dict(text="5-year blocks", font=dict(size=13)))
    show_chart(fig)
with col2:
    roll = base.rolling(3, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS_INT, y=base / 1e6, name="Annual", marker_color=COLORS["surface_2"]))
    fig.add_trace(go.Scatter(x=YEARS_INT, y=roll / 1e6, name="3-yr rolling average",
                             line=dict(color=COLORS["accent"], width=3)))
    fig.update_layout(height=320, margin=dict(t=30, l=0, r=0, b=0), yaxis_title="$M",
                      title=dict(text="Annual with rolling average", font=dict(size=13)),
                      legend=dict(orientation="h", yanchor="bottom", y=-0.3))
    show_chart(fig)
first5, last5 = base.iloc[:5].mean(), base.iloc[-5:].mean()
if first5 > 0:
    cagr = (last5 / first5) ** (1 / 15) - 1
    st.caption(f"Average annual need moves from {money(first5)} (first 5 years) to {money(last5)} (last 5 years): "
               f"{cagr*100:+.1f}% a year before inflation. Peak year {int(base.idxmax())} at {money(base.max())}.")

lp.download(pd.DataFrame({"year": YEARS_INT, "forecast_todays_dollars": base.values, "nominal_with_contingency":
                          nominal.values, "backlog_clearance": backlog_per_yr, "requirement": requirement,
                          "planned_budget": planned, "variance": var}),
            "Download capital plan (CSV)", "capital_plan.csv", "cap_dl2")
