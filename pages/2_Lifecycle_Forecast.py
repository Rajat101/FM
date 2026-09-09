import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, render_header, COLORS, YEARS

st.set_page_config(page_title="Lifecycle Forecast", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Lifecycle forecast")
st.caption("Year-by-year CapEx / OpEx projection, deferred-renewal exposure, and the long-tail beyond 2045.")

df = sidebar_filters(df_all, key_prefix="forecast")

capex = df[df["exp_type"] == "Capex"]
opex = df[df["exp_type"] == "Opex"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("CapEx, 20-yr total", money(capex[YEARS].sum().sum()))
c2.metric("OpEx, 20-yr total", money(opex[YEARS].sum().sum()))
c3.metric("Deferred (overdue) exposure", money(df.loc[df["already_overdue"], "cost"].sum()))
c4.metric("Long-tail (beyond 2045)", money(
    df.loc[df["renewal_beyond_window"] & ~df["already_overdue"], "cost"].sum()
), help="Replacement cost for assets whose calculated renewal falls after 2045")

st.markdown("---")
st.subheader("CapEx vs OpEx by year")
by_year = df.groupby("exp_type")[YEARS].sum().T
by_year.index.name = "year"
fig = go.Figure()
fig.add_trace(go.Bar(x=by_year.index.astype(str), y=by_year.get("Capex", pd.Series(dtype=float)),
                      name="CapEx", marker_color=COLORS["accent"]))
fig.add_trace(go.Bar(x=by_year.index.astype(str), y=by_year.get("Opex", pd.Series(dtype=float)),
                      name="OpEx", marker_color=COLORS["steel"]))
fig.update_layout(barmode="stack", height=380, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$")
show_chart(fig)

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Forecast by portfolio, stacked")
    by_port_year = df.groupby("portfolio")[YEARS].sum()
    fig2 = go.Figure()
    palette = [COLORS["accent"], COLORS["steel"], COLORS["good"], COLORS["warn"], COLORS["critical"], "#B08968", "#7A8B99"]
    for i, (port, row) in enumerate(by_port_year.iterrows()):
        fig2.add_trace(go.Bar(x=[str(y) for y in YEARS], y=row.values, name=port, marker_color=palette[i % len(palette)]))
    fig2.update_layout(barmode="stack", height=420, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$",
                        legend=dict(orientation="h", yanchor="bottom", y=-0.4))
    show_chart(fig2)

with col2:
    st.subheader("Top component groups driving spend")
    by_group = df.groupby("comp. group")[YEARS].sum().sum(axis=1).sort_values(ascending=True).tail(10)
    fig3 = go.Figure(go.Bar(x=by_group.values, y=by_group.index, orientation="h", marker_color=COLORS["accent"]))
    fig3.update_layout(height=420, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="20-yr forecast $")
    show_chart(fig3)

st.markdown("---")
st.subheader("Deferred-renewal exposure by portfolio")
st.markdown(
    '<div class="panel-note">Deferred exposure = replacement cost of components already past their '
    'calculated renewal year. This grows every year those assets stay unfunded &mdash; see Scenario '
    'Modeling to project it forward under different budgets.</div>', unsafe_allow_html=True
)
deferred_by_port = df[df["already_overdue"]].groupby("portfolio")["cost"].sum().sort_values(ascending=True)
fig4 = go.Figure(go.Bar(x=deferred_by_port.values, y=deferred_by_port.index, orientation="h",
                         marker_color=COLORS["critical"]))
fig4.update_layout(height=320, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="$ overdue")
show_chart(fig4)
