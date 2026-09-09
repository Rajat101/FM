import streamlit as st
import pandas as pd
from common import (
    inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, render_header,
    generate_insights, compute_recommendations, generate_pdf_report,
    RECOMMENDATION_ORDER, RECOMMENDATION_COLORS, COLORS,
)
import plotly.graph_objects as go

st.set_page_config(page_title="Recommendations", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Recommendation engine")
st.caption("Set your own thresholds below -- every asset is re-classified live against them.")

df = sidebar_filters(df_all, key_prefix="rec")

st.markdown("##### Set your thresholds")
st.markdown(
    '<div class="panel-note">These thresholds drive the recommendation directly -- they are independent '
    'of the fixed logic used elsewhere in the app, so you can stress-test different policies.</div>',
    unsafe_allow_html=True,
)
p1, p2, p3 = st.columns(3)
life_maintain_max = p1.slider("Maintain below (% of life used)", 20, 80, 55, 5,
                               help="Assets under this life-used threshold are recommended to simply maintain") / 100
life_plan_max = p2.slider("Plan renewal below (% of life used)", int(life_maintain_max * 100) + 5, 98, 85, 1,
                           help="Between the maintain threshold and this one -> Plan Renewal") / 100
risk_high_threshold = p3.slider("High risk threshold (0-100)", 10, 90, 40, 5,
                                 help="At or past the plan-renewal threshold, risk at or above this becomes Replace Now")

use_budget = st.checkbox("Apply an annual budget cap to the Replace bucket")
budget_cap = None
if use_budget:
    budget_cap = st.number_input("Annual budget available for replacements ($)", min_value=100_000,
                                  max_value=50_000_000, value=4_000_000, step=100_000)
    st.caption("Replace-flagged assets beyond what this budget covers (ranked by urgency) move to a "
               "'Replace \u2014 Budget Constrained' bucket instead.")

rec_df = compute_recommendations(df, life_maintain_max, life_plan_max, risk_high_threshold, budget_cap)

st.markdown("---")
st.markdown("##### Recommendation summary")
summary = (
    rec_df.groupby("recommendation")
    .agg(Assets=("cmp_id", "count"), **{"Total cost": ("cost", "sum")})
    .reindex(RECOMMENDATION_ORDER)
    .dropna(how="all")
    .fillna(0)
)
summary["Assets"] = summary["Assets"].astype(int)
cols = st.columns(len(summary))
for col, (rec_name, row) in zip(cols, summary.iterrows()):
    color = RECOMMENDATION_COLORS.get(rec_name, COLORS["steel"])
    col.markdown(
        f"""<div style="background:{COLORS['surface']}; border:1px solid {COLORS['border']};
                    border-left:3px solid {color}; border-radius:10px; padding:14px;">
            <div style="font-size:12px; color:{COLORS['text_muted']};">{rec_name}</div>
            <div style="font-size:22px; font-weight:800; color:{COLORS['text']};">{int(row['Assets']):,}</div>
            <div style="font-size:12px; color:{COLORS['text_muted']};">{money(row['Total cost'])}</div>
        </div>""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
fig = go.Figure(go.Bar(
    x=summary.index, y=summary["Assets"],
    marker_color=[RECOMMENDATION_COLORS.get(i, COLORS["steel"]) for i in summary.index],
))
fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Assets")
show_chart(fig)

st.markdown("---")
st.markdown("##### Assets grouped by recommendation")
rec_samples = {}
for rec_name in RECOMMENDATION_ORDER:
    subset = rec_df[rec_df["recommendation"] == rec_name]
    if len(subset) == 0:
        continue
    with st.expander(f"{rec_name} \u2014 {len(subset):,} assets, {money(subset['cost'].sum())}"):
        show_cols = ["cmp_id", "component", "portfolio", "comp. group", "Condition",
                     "risk_score", "urgency_score", "cost"]
        display_n = min(len(subset), 200)
        st.dataframe(
            subset.sort_values("urgency_score", ascending=False)[show_cols].head(display_n),
            width="stretch", hide_index=True,
            column_config={
                "cost": st.column_config.NumberColumn("cost", format="$%.0f"),
                "risk_score": st.column_config.ProgressColumn("risk", format="%.0f", min_value=0, max_value=100),
                "urgency_score": st.column_config.ProgressColumn("urgency", format="%.0f", min_value=0, max_value=100),
            },
        )
        if len(subset) > display_n:
            st.caption(f"Showing top {display_n:,} of {len(subset):,} by urgency.")
    rec_samples[rec_name] = subset.sort_values("urgency_score", ascending=False).head(10)

st.markdown("---")
st.markdown("##### Export report")
st.caption("Generates a PDF with KPIs, insights, and recommendation counts/costs -- plus a top-10 sample "
           "per category, never the full underlying data.")

if st.button("Generate PDF report", type="primary"):
    portfolios_in_scope = sorted(df["portfolio"].unique())
    scope_label = f"{len(portfolios_in_scope)} portfolio(s), {len(df):,} components"
    kpis = {
        "Tracked components": f"{len(df):,}",
        "20-yr forecast CapEx": money(df[[c for c in df.columns if c.isdigit()]].sum().sum())
            if any(c.isdigit() for c in df.columns) else "n/a",
        "Overdue assets": f"{df['already_overdue'].sum():,}",
        "Deferred exposure": money(df['deferred'].sum()),
        "Avg. condition": f"C{df['condition_numeric'].mean():.1f}",
    }
    insights = generate_insights(df)
    summary_export = summary.reset_index().rename(columns={"recommendation": "Recommendation"})
    summary_export["Total cost"] = summary_export["Total cost"].apply(money)
    params = {
        "life_maintain_max": life_maintain_max, "life_plan_max": life_plan_max,
        "risk_high_threshold": risk_high_threshold, "budget_cap": budget_cap,
    }
    pdf_bytes = generate_pdf_report(scope_label, kpis, insights, summary_export, rec_samples, params)
    st.download_button(
        "Download PDF", data=pdf_bytes, file_name="FM_Asset_Excellence_Recommendation_Report.pdf",
        mime="application/pdf",
    )
