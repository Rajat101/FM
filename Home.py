import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd
from common import (
    inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, render_header,
    render_flow_diagram, generate_insights, run_budget_scenario, compute_tipping_economics,
    COLORS, DECISION_COLORS, CONFIDENCE_COLORS, YEARS, YEARS_INT,
)

st.set_page_config(page_title="FM Asset Excellence", page_icon=":material/insights:", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Facilities asset lifecycle and capital decision model — Pannawonica")
st.markdown('<span class="badge-tag">LIVE MODEL — figures update as you filter or upload a new workbook</span>', unsafe_allow_html=True)

df = sidebar_filters(df_all, key_prefix="home")

st.sidebar.markdown("---")
st.sidebar.markdown(
    '<div class="panel-note">Forecast window 2026&ndash;2045. Figures shown are model estimates, not commitments.</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- insights banner
st.markdown("##### What this data is telling you")
insights = generate_insights(df)
cols = st.columns(len(insights)) if insights else []
for col, ins in zip(cols, insights):
    with col:
        st.markdown(
            f"""<div class="insight-card {ins['level']}">
                    <div class="headline">{ins['headline']}</div>
                    <div class="detail">{ins['detail']}</div>
                </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------- KPI row
st.markdown("##### Portfolio at a glance")
n = len(df)
overdue = df[df["already_overdue"]]
total_20yr = df[YEARS].sum().sum()
deferred_val = df["deferred"].sum()
avg_condition = df["condition_numeric"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tracked components", f"{n:,}")
c2.metric("20-yr forecast CapEx", money(total_20yr))
c3.metric("Overdue assets", f"{len(overdue):,}")
c4.metric("Deferred exposure", money(deferred_val))
c5.metric("Avg. condition", f"C{avg_condition:.1f}")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------- scenario hero
st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, {COLORS['surface_2']}, {COLORS['surface']});
                border: 1px solid {COLORS['border']}; border-radius: 16px; padding: 24px 28px 8px; margin-bottom: 8px;">
        <h4 style="margin:0; color:{COLORS['text']};">Scenario &amp; forecast — set your own parameters</h4>
        <p style="font-size:13px; color:{COLORS['text_muted']}; margin:4px 0 0;">
            Move any control below and the forecast redraws live against your uploaded data.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

hero_l, hero_r = st.columns([1, 2])
with hero_l:
    st.write("")
    h_budget = st.slider("Annual budget ($M)", 1.0, 15.0, 4.0, 0.5, key="hero_budget")
    h_growth = st.slider("Budget growth / yr (%)", -10.0, 15.0, 0.0, 1.0, key="hero_growth") / 100
    h_esc = st.slider("Deferral cost escalation / yr (%)", 0.0, 25.0, 6.0, 1.0, key="hero_esc") / 100
    h_risk = st.slider("Priority: risk vs. cost-efficiency", 0.0, 1.0, 0.7, 0.05, key="hero_risk")

hero_results, hero_backlog = run_budget_scenario(
    df, h_budget * 1_000_000, h_growth, YEARS_INT, h_esc, h_risk
)

with hero_r:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hero_results["year"], y=hero_results["backlog_value"] / 1_000_000,
        line=dict(color=COLORS["accent"], width=3), fill="tozeroy", name="Unfunded backlog",
    ))
    fig.update_layout(height=280, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Backlog ($M)", showlegend=False)
    show_chart(fig)
    m1, m2, m3 = st.columns(3)
    m1.metric("Backlog by 2045", money(hero_results.iloc[-1]["backlog_value"]))
    total_due = df["cost"].sum()
    funded_pct = hero_results["spend"].sum() / max(total_due, 1) * 100
    m2.metric("Total funded (20yr)", f"{min(funded_pct, 100):.0f}%")
    m3.metric("Assets still unfunded", f"{hero_results.iloc[-1]['assets_backlog']:,.0f}")

st.markdown(
    '<p style="text-align:right;"><a href="Scenario_Modeling" target="_self" style="font-size:13px;">'
    'Open full scenario comparison &rarr;</a></p>',
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------- uncovering the mechanics
st.markdown("##### Uncovering the mechanics behind the numbers")
v1, v2, v3 = st.columns(3)

with v1:
    st.markdown(
        f"""<div style="background:{COLORS['surface']}; border:1px solid {COLORS['border']}; border-radius:14px; padding:18px;">
        <b>Asset lifecycle flow</b><br>
        <span style="font-size:12px; color:{COLORS['text_muted']};">Every asset moves through this cycle &mdash;
        the tipping point is where cost stops favoring repair.</span></div>""",
        unsafe_allow_html=True,
    )
    st.write("")
    render_flow_diagram()

with v2:
    st.markdown(
        f"""<div style="background:{COLORS['surface']}; border:1px solid {COLORS['border']}; border-radius:14px; padding:18px; margin-bottom:8px;">
        <b>Condition decay curve</b><br>
        <span style="font-size:12px; color:{COLORS['text_muted']};">Typical condition against asset age, based on this portfolio's average component life.</span></div>""",
        unsafe_allow_html=True,
    )
    avg_life = df["base_life"].mean()
    age_frac = np.linspace(0, 1.3, 60)
    condition_pct = 100 * np.exp(-1.6 * age_frac)
    fig = go.Figure(go.Scatter(x=age_frac * avg_life, y=condition_pct, line=dict(color=COLORS["accent"], width=3),
                                fill="tozeroy"))
    fig.update_layout(height=230, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Age (years)", yaxis_title="Condition (%)")
    show_chart(fig)

with v3:
    st.markdown(
        f"""<div style="background:{COLORS['surface']}; border:1px solid {COLORS['border']}; border-radius:14px; padding:18px; margin-bottom:8px;">
        <b>Cost crossover</b><br>
        <span style="font-size:12px; color:{COLORS['text_muted']};">Where rising maintenance cost overtakes the cost of replacing, on average.</span></div>""",
        unsafe_allow_html=True,
    )
    d = compute_tipping_economics(df, 0.07, 0.02, 3.0)
    life_pct = np.linspace(0, 1.5, 60)
    avg_cost = d["cost"].mean()
    avg_eac = d["eac_replace_live"].mean()
    maint_curve = 0.02 * avg_cost * np.exp(3.0 * life_pct)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=life_pct * 100, y=maint_curve, name="Maintenance", line=dict(color=COLORS["warn"], width=3)))
    fig.add_trace(go.Scatter(x=life_pct * 100, y=[avg_eac] * len(life_pct), name="Replacement (EAC)",
                              line=dict(color=COLORS["critical"], width=2, dash="dash")))
    fig.update_layout(height=230, margin=dict(t=30, l=0, r=0, b=0), xaxis_title="% of life used", yaxis_title="$/yr",
                       legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    show_chart(fig)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------- top priority assets (real data)
st.markdown("##### Highest-priority assets right now")
top_priority = df.sort_values("urgency_score", ascending=False).head(8)[
    ["component", "portfolio", "Condition", "decision", "cost"]
]
st.dataframe(
    top_priority,
    width="stretch", hide_index=True,
    column_config={"cost": st.column_config.NumberColumn("Est. cost", format="$%.0f")},
)
