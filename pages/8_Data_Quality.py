import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, render_header, COLORS, CONFIDENCE_COLORS

st.set_page_config(page_title="Data Quality", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Data quality")
st.caption("Where the underlying data is strong or shaky, and the dollar value riding on the gaps.")

df = sidebar_filters(df_all, key_prefix="dq")

st.markdown(
    '<div class="panel-note">Confidence combines three flags: missing survey data, a uniform construction '
    'year across a whole property (consistent with a system default, not proof of one), and the C-model '
    'condition-reset pattern for recently-surveyed, short-life equipment. It is a heuristic, not a certainty '
    '&mdash; see the How to Use page for the full breakdown.</div>',
    unsafe_allow_html=True,
)

n = len(df)
low_med = df[df["data_confidence"].isin(["Low", "Medium"])]
c1, c2, c3, c4 = st.columns(4)
c1.metric("High confidence", f"{(df['data_confidence']=='High').mean()*100:.0f}%")
c2.metric("Medium confidence", f"{(df['data_confidence']=='Medium').mean()*100:.0f}%")
c3.metric("Low confidence", f"{(df['data_confidence']=='Low').mean()*100:.0f}%")
c4.metric("$ at stake in Low/Medium", money(low_med["cost"].sum()))

st.markdown("---")
c1, c2 = st.columns(2)
c1.metric("Never surveyed", f"{df['survey_missing'].sum():,}")
c2.metric("C-model reset risk flagged", f"{df['condition_reset_risk'].sum():,}")

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Confidence distribution")
    counts = df["data_confidence"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0)
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values,
                            marker_color=[CONFIDENCE_COLORS[k] for k in counts.index]))
    fig.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Components")
    show_chart(fig)

with col2:
    st.subheader("Confidence by portfolio")
    ct = pd.crosstab(df["portfolio"], df["data_confidence"])
    ct = ct[[c for c in ["High", "Medium", "Low"] if c in ct.columns]]
    ct = ct.loc[ct.sum(axis=1).sort_values(ascending=True).index]
    fig2 = go.Figure()
    for level in ["Low", "Medium", "High"]:
        if level in ct.columns:
            fig2.add_trace(go.Bar(y=ct.index, x=ct[level], name=level, orientation="h",
                                   marker_color=CONFIDENCE_COLORS[level]))
    fig2.update_layout(barmode="stack", height=340, margin=dict(t=10, l=0, r=0, b=0),
                        legend=dict(orientation="h", yanchor="bottom", y=-0.3))
    show_chart(fig2)

st.markdown("---")
st.subheader("Confidence by component group")
ct2 = pd.crosstab(df["comp. group"], df["data_confidence"])
ct2 = ct2[[c for c in ["High", "Medium", "Low"] if c in ct2.columns]]
ct2 = ct2.loc[ct2.sum(axis=1).sort_values(ascending=True).index]
fig3 = go.Figure()
for level in ["Low", "Medium", "High"]:
    if level in ct2.columns:
        fig3.add_trace(go.Bar(y=ct2.index, x=ct2[level], name=level, orientation="h",
                               marker_color=CONFIDENCE_COLORS[level]))
fig3.update_layout(barmode="stack", height=440, margin=dict(t=10, l=0, r=0, b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2))
show_chart(fig3)

st.markdown("---")
st.subheader("Biggest gaps \u2014 highest-cost components with Low or Medium confidence")
gaps = low_med.sort_values("cost", ascending=False)[
    ["cmp_id", "component", "portfolio", "comp. group", "Condition", "data_confidence",
     "survey_missing", "condition_reset_risk", "cost"]
]
display_n = min(len(gaps), 100)
st.dataframe(
    gaps.head(display_n), width="stretch", hide_index=True,
    column_config={"cost": st.column_config.NumberColumn("cost", format="$%.0f")},
)
if len(gaps) > display_n:
    st.caption(f"Showing top {display_n:,} of {len(gaps):,} by cost.")
