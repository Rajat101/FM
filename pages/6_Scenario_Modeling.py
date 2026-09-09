import streamlit as st
import plotly.graph_objects as go
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, run_budget_scenario, render_header, COLORS, YEARS_INT

st.set_page_config(page_title="Scenario Modeling", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Scenario modeling & what-if simulation")
st.caption("Set an annual budget and funding rules, then see who gets funded, who gets deferred, and what that costs later.")

df = sidebar_filters(df_all, key_prefix="scenario")

st.markdown(
    '<div class="panel-note">Each year, every asset that is due (or overdue) competes for that '
    'year\u2019s budget, ranked by a blended score of urgency and cost-efficiency. Anything left unfunded '
    'carries into next year with its cost escalated and its urgency raised &mdash; deferral compounds, '
    'it doesn\u2019t sit still.</div>', unsafe_allow_html=True,
)

st.markdown("#### Scenario A")
a1, a2, a3, a4, a5 = st.columns(5)
budget_a = a1.number_input("Annual budget ($)", min_value=100_000, max_value=50_000_000, value=4_000_000, step=100_000, key="budget_a")
growth_a = a2.slider("Budget growth / yr (%)", -10.0, 15.0, 0.0, 1.0, key="growth_a") / 100
escalation_a = a3.slider("Deferral cost escalation / yr (%)", 0.0, 25.0, 6.0, 1.0, key="esc_a") / 100
risk_weight_a = a4.slider("Priority: risk vs. cost-efficiency", 0.0, 1.0, 0.7, 0.05, key="rw_a",
                           help="1.0 = fund the riskiest assets first; 0.0 = fund the cheapest wins first")
compare_on = a5.toggle("Compare with Scenario B", value=True)

results_a, backlog_a = run_budget_scenario(df, budget_a, growth_a, YEARS_INT, escalation_a, risk_weight_a)

if compare_on:
    st.markdown("#### Scenario B")
    b1, b2, b3, b4 = st.columns(4)
    budget_b = b1.number_input("Annual budget ($)", min_value=100_000, max_value=50_000_000, value=6_000_000, step=100_000, key="budget_b")
    growth_b = b2.slider("Budget growth / yr (%)", -10.0, 15.0, 2.0, 1.0, key="growth_b") / 100
    escalation_b = b3.slider("Deferral cost escalation / yr (%)", 0.0, 25.0, 6.0, 1.0, key="esc_b") / 100
    risk_weight_b = b4.slider("Priority: risk vs. cost-efficiency", 0.0, 1.0, 0.7, 0.05, key="rw_b")
    results_b, backlog_b = run_budget_scenario(df, budget_b, growth_b, YEARS_INT, escalation_b, risk_weight_b)

st.markdown("---")

end_backlog_a = results_a.iloc[-1]["backlog_value"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Scenario A: total spend", money(results_a["spend"].sum()))
c2.metric("Scenario A: backlog by 2045", money(end_backlog_a))
c3.metric("Scenario A: assets never funded", f"{results_a.iloc[-1]['assets_backlog']:,.0f}")
if compare_on:
    end_backlog_b = results_b.iloc[-1]["backlog_value"]
    c4.metric("Scenario B: backlog by 2045", money(end_backlog_b), delta=money(end_backlog_b - end_backlog_a),
              delta_color="inverse")

st.markdown("---")
st.subheader("Backlog value over time")
fig = go.Figure()
fig.add_trace(go.Scatter(x=results_a["year"], y=results_a["backlog_value"], name="Scenario A",
                          line=dict(color=COLORS["accent"], width=3), fill="tozeroy"))
if compare_on:
    fig.add_trace(go.Scatter(x=results_b["year"], y=results_b["backlog_value"], name="Scenario B",
                              line=dict(color=COLORS["steel"], width=3)))
fig.update_layout(height=380, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Unfunded backlog $",
                   legend=dict(orientation="h", yanchor="bottom", y=-0.3))
show_chart(fig)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Spend vs. budget, Scenario A")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=results_a["year"], y=results_a["spend"], name="Spend", marker_color=COLORS["accent"]))
    fig2.add_trace(go.Scatter(x=results_a["year"], y=results_a["budget"], name="Budget cap",
                               line=dict(color=COLORS["text_muted"], dash="dot")))
    fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$",
                        legend=dict(orientation="h", yanchor="bottom", y=-0.3))
    show_chart(fig2)

with col2:
    st.subheader("Assets funded vs. backlogged, Scenario A")
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(x=results_a["year"], y=results_a["assets_funded"], name="Funded", marker_color=COLORS["good"]))
    fig3.add_trace(go.Bar(x=results_a["year"], y=results_a["assets_backlog"], name="Backlogged", marker_color=COLORS["critical"]))
    fig3.update_layout(barmode="stack", height=340, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Assets",
                        legend=dict(orientation="h", yanchor="bottom", y=-0.3))
    show_chart(fig3)

st.markdown("---")
st.subheader("Risk exposure carried in the backlog")
fig4 = go.Figure()
fig4.add_trace(go.Scatter(x=results_a["year"], y=results_a["backlog_risk"], name="Scenario A",
                           line=dict(color=COLORS["accent"], width=3)))
if compare_on:
    fig4.add_trace(go.Scatter(x=results_b["year"], y=results_b["backlog_risk"], name="Scenario B",
                               line=dict(color=COLORS["steel"], width=3)))
fig4.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Cumulative urgency score of unfunded assets",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.3))
show_chart(fig4)

st.markdown("---")
st.subheader("Assets still unfunded at the end of Scenario A")
show_cols = ["cmp_id", "portfolio", "comp. group", "component", "remaining_cost", "current_urgency", "years_deferred"]
if len(backlog_a):
    st.dataframe(
        backlog_a[show_cols].sort_values("current_urgency", ascending=False).head(200),
        width='stretch', height=340,
        column_config={
            "remaining_cost": st.column_config.NumberColumn("cost (escalated)", format="$%.0f"),
            "current_urgency": st.column_config.ProgressColumn("urgency", format="%.0f", min_value=0, max_value=100),
        },
    )
else:
    st.success("No backlog remains under this scenario \u2014 every due asset gets funded.")
