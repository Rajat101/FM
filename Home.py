import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, COLORS, DECISION_COLORS, CONFIDENCE_COLORS, YEARS

st.set_page_config(page_title="Pannawonica Asset Lifecycle", page_icon=":material/insights:", layout="wide")
inject_css()
plotly_template()

df_all = load_data()

st.title("Pannawonica Asset Lifecycle & Decision Model")
st.caption(
    "Portfolio-wide view across 129,487 tracked components in accommodation, residential, "
    "commercial and town properties."
)

df = sidebar_filters(df_all, key_prefix="home")

st.sidebar.markdown("---")
st.sidebar.markdown(
    f'<div class="panel-note">Built from <b>Lifecycle_PAN.xlsx</b>. '
    f'Forecast window 2026&ndash;2045. Figures shown are model estimates, not commitments.</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- headline KPIs
n = len(df)
overdue = df[df["already_overdue"]]
total_20yr = df[YEARS].sum().sum()
deferred_val = df["deferred"].sum()
beyond_window = df["renewal_beyond_window"].sum()
avg_condition = df["condition_numeric"].mean()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Tracked components", f"{n:,}")
c2.metric("20-yr forecast CapEx", money(total_20yr))
c3.metric("Overdue assets", f"{len(overdue):,}", help="next_renewal_year before 2026")
c4.metric("Deferred exposure", money(deferred_val))
c5.metric("Beyond forecast window", f"{beyond_window:,}", help="Renewal due after 2045")
c6.metric("Avg. condition", f"C{avg_condition:.1f}")

c7, c8, c9, c10, c11, c12 = st.columns(6)
c7.metric("Properties", f"{df['property code'].nunique():,}")
c8.metric("Sites", f"{df['site'].nunique():,}")
c9.metric("Survey data missing", f"{df['survey_missing'].sum():,}", help="cmp_survey_year = 0")
c10.metric("C-model reset risk", f"{df['condition_reset_risk'].sum():,}",
           help="Recently-surveyed, good-condition, short-life components -- see SME note")
c11.metric("High-risk assets", f"{(df['risk_score']>=40).sum():,}", help="Risk score >= 40 / 100")
c12.metric("Human overrides found", f"{df['has_replace_override'].sum():,}", help='"Replace by [year]" in comments')

st.markdown("---")

# ---------------------------------------------------------------- CapEx forecast + decision mix
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("CapEx forecast, 2026\u20132045")
    yearly = df[YEARS].sum().reset_index()
    yearly.columns = ["year", "cost"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=yearly["year"], y=yearly["cost"], marker_color=COLORS["accent"], name="Forecast CapEx"))
    fig.update_layout(height=380, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$", xaxis_title=None,
                       showlegend=False)
    show_chart(fig)

with col_right:
    st.subheader("Decision mix")
    dec_counts = df["decision"].value_counts().reindex(DECISION_COLORS.keys()).dropna()
    fig2 = go.Figure(go.Pie(
        labels=dec_counts.index, values=dec_counts.values, hole=0.55,
        marker_colors=[DECISION_COLORS[k] for k in dec_counts.index],
        textinfo="percent",
    ))
    fig2.update_layout(height=380, margin=dict(t=10, l=0, r=0, b=0),
                        legend=dict(orientation="h", yanchor="bottom", y=-0.25))
    show_chart(fig2)

st.markdown("---")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("CapEx by portfolio")
    by_port = df.groupby("portfolio")[YEARS].sum().sum(axis=1).sort_values(ascending=True)
    fig3 = go.Figure(go.Bar(
        x=by_port.values, y=by_port.index, orientation="h", marker_color=COLORS["steel"]
    ))
    fig3.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="20-yr forecast $")
    show_chart(fig3)

with col_b:
    st.subheader("Data confidence across the portfolio")
    conf_counts = df["data_confidence"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0)
    fig4 = go.Figure(go.Bar(
        x=conf_counts.index, y=conf_counts.values,
        marker_color=[CONFIDENCE_COLORS[k] for k in conf_counts.index]
    ))
    fig4.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Components")
    show_chart(fig4)

st.markdown(
    '<div class="panel-note">Confidence combines missing survey data, a uniform construction '
    'year across a whole property (consistent with a system default, per the SME notes), and the '
    'condition-reset pattern flagged for short-life, recently-surveyed equipment. It is a heuristic, '
    'not a certainty &mdash; see the Risk &amp; Condition page for the full method.</div>',
    unsafe_allow_html=True,
)

st.markdown("---")
st.subheader("Component groups by forecast spend")
by_group = df.groupby("comp. group")[YEARS].sum().sum(axis=1).sort_values(ascending=False)
fig5 = px.treemap(
    names=by_group.index, parents=[""] * len(by_group), values=by_group.values,
    color=by_group.values, color_continuous_scale=[COLORS["surface_2"], COLORS["accent"]],
)
fig5.update_layout(height=420, margin=dict(t=10, l=0, r=0, b=0), coloraxis_showscale=False)
show_chart(fig5)
