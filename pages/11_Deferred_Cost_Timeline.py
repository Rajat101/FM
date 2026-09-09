import streamlit as st
import numpy as np
import plotly.graph_objects as go
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, render_header, generate_work_order_pdf, COLORS

st.set_page_config(page_title="Deferred-Cost Timeline", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Deferred-cost timeline")
st.caption("What's due, and when \u2014 a year-by-year schedule instead of a dollar chart. Useful for actually planning work, not just budgeting for it.")

df = sidebar_filters(df_all, key_prefix="timeline")

d = df.copy()
d["due_year_bucket"] = np.where(d["best_estimate_year"] > 2045, 2046, d["best_estimate_year"].clip(lower=2020))
d["due_year_bucket"] = np.where(d["already_overdue"], 2025, d["due_year_bucket"])

bucket_labels = {2025: "Overdue (before 2026)", 2046: "Beyond 2045"}
def label_year(y):
    return bucket_labels.get(y, str(int(y)))

counts_by_year = d.groupby("due_year_bucket").agg(components=("cmp_id", "count"), cost=("cost", "sum"))
counts_by_year = counts_by_year.sort_index()
counts_by_year.index = [label_year(y) for y in counts_by_year.index]

st.markdown("##### When is everything due?")
fig = go.Figure()
fig.add_trace(go.Bar(x=counts_by_year.index, y=counts_by_year["cost"], marker_color=COLORS["accent"], name="Cost"))
fig.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$", xaxis_tickangle=-45)
show_chart(fig)

st.markdown("---")
st.markdown("##### Pick a year to see what's actually due")
year_options = ["Overdue (before 2026)"] + [str(y) for y in range(2026, 2046)] + ["Beyond 2045"]
sel = st.selectbox("Year", year_options, index=1)

if sel == "Overdue (before 2026)":
    subset = d[d["already_overdue"]]
elif sel == "Beyond 2045":
    subset = d[(~d["already_overdue"]) & (d["best_estimate_year"] > 2045)]
else:
    yr = int(sel)
    subset = d[(~d["already_overdue"]) & (d["best_estimate_year"] == yr)]

c1, c2 = st.columns(2)
c1.metric("Components due", f"{len(subset):,}")
c2.metric("Total cost", money(subset["cost"].sum()))

show_cols = ["cmp_id", "component", "portfolio", "comp. group", "Condition", "risk_score", "cost"]
st.dataframe(
    subset.sort_values("cost", ascending=False)[show_cols].head(300),
    width="stretch", hide_index=True,
    column_config={
        "cost": st.column_config.NumberColumn("cost", format="$%.0f"),
        "risk_score": st.column_config.ProgressColumn("risk", format="%.0f", min_value=0, max_value=100),
    },
)
if len(subset) > 300:
    st.caption(f"Showing top 300 of {len(subset):,} by cost.")

st.markdown("---")
st.subheader("Volume by portfolio for the selected year")
by_port = subset.groupby("portfolio").agg(components=("cmp_id", "count"), cost=("cost", "sum")).sort_values("cost", ascending=True)
if len(by_port):
    fig2 = go.Figure(go.Bar(x=by_port["cost"], y=by_port.index, orientation="h", marker_color=COLORS["steel"]))
    fig2.update_layout(height=320, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="$")
    show_chart(fig2)
else:
    st.info("Nothing due in this selection for the current filter.")

st.markdown("---")
st.markdown("##### Export as a work order report")
st.caption("Operational document: everything overdue or due in the next 12 months (2026), grouped by "
           "portfolio and sorted by urgency \u2014 for whoever dispatches the work, not who approves the budget.")
if st.button("Generate work order report PDF", type="primary"):
    next12_df = d[d["already_overdue"] | (d["best_estimate_year"] == 2026)]
    by_portfolio_export = next12_df.groupby("portfolio").agg(
        components=("cmp_id", "count"), cost=("cost", "sum")
    ).sort_values("cost", ascending=False)
    portfolios_in_scope = sorted(df["portfolio"].unique())
    scope_label = f"{len(portfolios_in_scope)} portfolio(s), {len(df):,} components"
    pdf_bytes = generate_work_order_pdf(
        scope_label, "Overdue + due in 2026 (next 12 months)", next12_df, by_portfolio_export,
    )
    st.download_button(
        "Download PDF", data=pdf_bytes, file_name="FM_Asset_Excellence_Work_Order_Report.pdf",
        mime="application/pdf",
    )
