import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, render_header, COLORS, DECISION_COLORS

st.set_page_config(page_title="Risk & Condition", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Risk & condition analysis")
st.caption("Condition ratings, risk scoring methodology, and the maintain / renew / replace / defer decision matrix.")

df = sidebar_filters(df_all, key_prefix="risk")

with st.expander("How the risk score and decision are calculated", expanded=False):
    st.markdown(
        """
- **Risk score** (0\u2013100) = `condition_numeric \u00d7 consequence \u00d7 safety`, normalised against the
  highest-risk component in the dataset. It reflects both *how far gone* a component is and
  *how much it matters* if it fails.
- **Urgency score** adds a penalty on top of risk for components that are already overdue
  (+15) or flagged for the C-model condition-reset risk (+10) &mdash; both signal that the
  calculated date understates real urgency.
- **Decision** follows a simple matrix: overdue assets are always **Replace Now (Overdue)**;
  assets past 85% of expected life are **Replace Now** if risk is high, otherwise a
  **Defer Candidate**; assets past 55% of life are **Plan Renewal**; everything else is
  **Maintain**.
        """
    )

c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg. risk score", f"{df['risk_score'].mean():.1f} / 100")
c2.metric("High risk (\u226540)", f"{(df['risk_score']>=40).sum():,}")
c3.metric("C1/C2 (good) condition", f"{df['Condition'].isin(['C1','C2']).mean()*100:.0f}%")
c4.metric("C4/C5 (poor) condition", f"{df['Condition'].isin(['C4','C5']).mean()*100:.0f}%")

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Condition distribution")
    cond_counts = df["Condition"].value_counts().sort_index()
    fig = go.Figure(go.Bar(x=cond_counts.index, y=cond_counts.values, marker_color=COLORS["steel"]))
    fig.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Components")
    show_chart(fig)

with col2:
    st.subheader("Risk score distribution")
    fig2 = go.Figure(go.Histogram(x=df["risk_score"], nbinsx=30, marker_color=COLORS["accent"]))
    fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Risk score", yaxis_title="Components")
    show_chart(fig2)

st.markdown("---")
st.subheader("Decision matrix: life used vs. risk")
bins_life = pd.cut(df["life_fraction_used"], bins=[0, 0.3, 0.55, 0.85, 1.51],
                    labels=["<30%", "30-55%", "55-85%", "85%+"])
bins_risk = pd.cut(df["risk_score"], bins=[-1, 15, 30, 50, 101],
                    labels=["Low", "Moderate", "Elevated", "High"])
matrix = pd.crosstab(bins_life, bins_risk)
fig3 = go.Figure(go.Heatmap(
    z=matrix.values, x=matrix.columns.astype(str), y=matrix.index.astype(str),
    colorscale=[[0, COLORS["surface_2"]], [1, COLORS["accent"]]],
    text=matrix.values, texttemplate="%{text}",
))
fig3.update_layout(height=360, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Risk band", yaxis_title="Life used")
show_chart(fig3)

st.markdown("---")
st.subheader("Decision outcomes by component group")
dec_by_group = pd.crosstab(df["comp. group"], df["decision"])
dec_by_group = dec_by_group[[c for c in DECISION_COLORS if c in dec_by_group.columns]]
dec_by_group = dec_by_group.loc[dec_by_group.sum(axis=1).sort_values(ascending=True).index]
fig4 = go.Figure()
for dec, color in DECISION_COLORS.items():
    if dec in dec_by_group.columns:
        fig4.add_trace(go.Bar(y=dec_by_group.index, x=dec_by_group[dec], name=dec, orientation="h", marker_color=color))
fig4.update_layout(barmode="stack", height=440, margin=dict(t=10, l=0, r=0, b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.25))
show_chart(fig4)
