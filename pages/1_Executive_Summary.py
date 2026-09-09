import streamlit as st
import plotly.graph_objects as go
from common import (
    inject_css, plotly_template, show_chart, load_data, money, render_header,
    generate_insights, run_budget_scenario, compute_recommendations,
    COLORS, RECOMMENDATION_ORDER, RECOMMENDATION_COLORS, YEARS, YEARS_INT,
)

st.set_page_config(page_title="Executive Summary", layout="wide")
inject_css()
plotly_template()

df = load_data()
render_header("Executive summary")
st.caption("The one page to present from. No filters here \u2014 this is the whole portfolio, headline numbers only.")

# ---------------------------------------------------------------- headline KPIs
n = len(df)
overdue = df[df["already_overdue"]]
total_20yr = df[YEARS].sum().sum()
deferred_val = df["deferred"].sum()
avg_condition = df["condition_numeric"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tracked components", f"{n:,}")
c2.metric("20-yr forecast CapEx", money(total_20yr))
c3.metric("Overdue assets", f"{len(overdue):,}", help=money(overdue['cost'].sum()) + " in replacement cost")
c4.metric("Deferred exposure", money(deferred_val))
c5.metric("Avg. condition", f"C{avg_condition:.1f}")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------- insights
st.markdown("##### What matters most right now")
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

# ---------------------------------------------------------------- the one chart
st.markdown(
    f"""<div style="background: linear-gradient(135deg, {COLORS['surface_2']}, {COLORS['surface']});
                border: 1px solid {COLORS['border']}; border-radius: 16px; padding: 22px 26px 10px;">
        <h4 style="margin:0; color:{COLORS['text']};">If you remember one chart, remember this one</h4>
        <p style="font-size:13px; color:{COLORS['text_muted']}; margin:4px 0 12px;">
            Unfunded backlog value under a status-quo budget (current 20-yr average spend, held flat, no
            escalation offset). This is what happens if nothing changes.
        </p>
    </div>""",
    unsafe_allow_html=True,
)
status_quo_budget = total_20yr / 20
results, _ = run_budget_scenario(df, status_quo_budget, 0.0, YEARS_INT, 0.06, 0.7)
fig = go.Figure(go.Scatter(
    x=results["year"], y=results["backlog_value"], line=dict(color=COLORS["critical"], width=3),
    fill="tozeroy", name="Backlog",
))
fig.update_layout(height=280, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Unfunded backlog $", showlegend=False)
show_chart(fig)
m1, m2, m3 = st.columns(3)
m1.metric("Status-quo annual budget", money(status_quo_budget))
m2.metric("Backlog by 2045 at this rate", money(results.iloc[-1]["backlog_value"]))
m3.metric("Assets never funded", f"{results.iloc[-1]['assets_backlog']:,.0f}")
st.caption("See the Scenario Modeling page to test your actual proposed budget against this baseline.")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------- top priority actions
st.markdown("##### Top priority actions")
rec_df = compute_recommendations(df)
summary = (
    rec_df.groupby("recommendation").agg(Assets=("cmp_id", "count"), **{"Total cost": ("cost", "sum")})
    .reindex(RECOMMENDATION_ORDER).dropna(how="all").fillna(0)
)
summary["Assets"] = summary["Assets"].astype(int)
cols = st.columns(len(summary))
for col, (rec_name, row) in zip(cols, summary.iterrows()):
    color = RECOMMENDATION_COLORS.get(rec_name, COLORS["steel"])
    col.markdown(
        f"""<div style="background:{COLORS['surface']}; border:1px solid {COLORS['border']};
                    border-left:3px solid {color}; border-radius:10px; padding:12px;">
            <div style="font-size:11.5px; color:{COLORS['text_muted']};">{rec_name}</div>
            <div style="font-size:20px; font-weight:800; color:{COLORS['text']};">{int(row['Assets']):,}</div>
            <div style="font-size:11.5px; color:{COLORS['text_muted']};">{money(row['Total cost'])}</div>
        </div>""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
top5 = df.sort_values("urgency_score", ascending=False).head(5)[
    ["component", "portfolio", "Condition", "decision", "cost"]
]
st.dataframe(
    top5, width="stretch", hide_index=True,
    column_config={"cost": st.column_config.NumberColumn("Est. cost", format="$%.0f")},
)
st.caption("Full thresholds are adjustable on the Recommendations page. Full detail on Asset Explorer.")
