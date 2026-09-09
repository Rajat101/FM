import streamlit as st
import plotly.graph_objects as go
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, render_header, COLORS, YEARS

st.set_page_config(page_title="Portfolio Benchmarking", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Portfolio benchmarking")
st.caption("Compare portfolios head-to-head \u2014 is a portfolio actually worse, or does it just have more assets?")

df = sidebar_filters(df_all, key_prefix="bench")

bench = df.groupby("portfolio").agg(
    components=("cmp_id", "count"),
    total_cost=("cost", "sum"),
    avg_cost=("cost", "mean"),
    avg_condition=("condition_numeric", "mean"),
    avg_risk=("risk_score", "mean"),
    overdue_count=("already_overdue", "sum"),
    forecast_20yr=("cmp_id", "count"),  # placeholder, replaced below
)
bench["forecast_20yr"] = df.groupby("portfolio")[YEARS].sum().sum(axis=1)
bench["overdue_pct"] = bench["overdue_count"] / bench["components"] * 100
bench = bench.sort_values("total_cost", ascending=False)

st.markdown("##### Benchmark table")
display_bench = bench.reset_index().rename(columns={
    "portfolio": "Portfolio", "components": "Components", "total_cost": "Total replacement cost",
    "avg_cost": "Avg. cost / component", "avg_condition": "Avg. condition", "avg_risk": "Avg. risk score",
    "overdue_count": "Overdue count", "overdue_pct": "Overdue %", "forecast_20yr": "20-yr forecast",
})
st.dataframe(
    display_bench, width="stretch", hide_index=True,
    column_config={
        "Total replacement cost": st.column_config.NumberColumn(format="$%.0f"),
        "Avg. cost / component": st.column_config.NumberColumn(format="$%.0f"),
        "Avg. condition": st.column_config.NumberColumn(format="%.2f"),
        "Avg. risk score": st.column_config.NumberColumn(format="%.1f"),
        "Overdue %": st.column_config.NumberColumn(format="%.1f%%"),
        "20-yr forecast": st.column_config.NumberColumn(format="$%.0f"),
    },
)

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Avg. cost per component")
    b = bench.sort_values("avg_cost", ascending=True)
    fig = go.Figure(go.Bar(x=b["avg_cost"], y=b.index, orientation="h", marker_color=COLORS["accent"]))
    fig.update_layout(height=360, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="$ / component")
    show_chart(fig)

with col2:
    st.subheader("Avg. condition (lower is better)")
    b = bench.sort_values("avg_condition", ascending=True)
    fig2 = go.Figure(go.Bar(x=b["avg_condition"], y=b.index, orientation="h", marker_color=COLORS["steel"]))
    fig2.update_layout(height=360, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Avg. condition (1=best, 5=worst)")
    show_chart(fig2)

st.markdown("---")
st.subheader("Risk vs. cost, sized by component count")
fig3 = go.Figure(go.Scatter(
    x=bench["avg_risk"], y=bench["avg_cost"], mode="markers+text",
    marker=dict(size=(bench["components"] / bench["components"].max() * 60 + 10),
                color=COLORS["accent"], opacity=0.75),
    text=bench.index, textposition="top center",
))
fig3.update_layout(height=420, margin=dict(t=10, l=0, r=0, b=0),
                    xaxis_title="Avg. risk score", yaxis_title="Avg. cost / component ($)")
show_chart(fig3)
st.caption("Bubble size = number of components in that portfolio. Top-right = high risk, expensive components \u2014 the highest-stakes portfolios.")

st.markdown("---")
st.subheader("Overdue share by portfolio")
b = bench.sort_values("overdue_pct", ascending=True)
fig4 = go.Figure(go.Bar(x=b["overdue_pct"], y=b.index, orientation="h", marker_color=COLORS["critical"]))
fig4.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="% of components overdue")
show_chart(fig4)
