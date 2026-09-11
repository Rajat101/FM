import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from common import inject_css, plotly_template, show_chart, money, render_header, COLORS
import jundu_common as jc

st.set_page_config(page_title="Jundunmunnah Refurb Model", layout="wide")
inject_css()
plotly_template()

render_header("Jundunmunnah Refurbishment")
st.caption("Lifecycle & Investment Model \u2014 SAMP framework applied to a brand-new refurbishment package")

st.markdown(
    '<div class="panel-note">This page is separate from the main Pannawonica model because the data shape '
    'is fundamentally different: a small (~170-line), brand-new refurbishment package where every asset is '
    'Condition C1, built in a single year \u2014 not an aged, multi-thousand-asset portfolio. Every calculation '
    'here is a transparent formula (cost escalation, capital recovery factor, rule-based staging), not '
    'machine learning \u2014 there is no history yet for a model to learn from. Base life is supplied by the '
    'asset owner, not auto-calculated: an earlier test found Pannawonica category averages varied too widely '
    '(5\u2013100 years within a single group) to safely borrow from.</div>',
    unsafe_allow_html=True,
)

# ============================================================================ UPLOAD
st.markdown("##### Upload the Jundunmunnah workbook")
uploaded = st.file_uploader(
    "Upload a Jundunmunnah-format LCCM workbook (.xlsx) with an 'LCCM Asset Components' sheet",
    type=["xlsx"], key="jundu_upload",
)

if uploaded is None:
    st.info("Upload the workbook above to load the model. Nothing is stored beyond this session.")
    st.stop()


@st.cache_data(show_spinner="Processing Jundunmunnah workbook\u2026")
def process_jundu_file(file_bytes):
    import io
    buf = io.BytesIO(file_bytes)
    df = jc.load_jundu_workbook(buf)
    buf.seek(0)
    missing_df = jc.load_missing_cost_inputs(buf)
    df, not_in_register = jc.flag_partial_cost_items(df, missing_df)
    df = jc.compute_confidence(df)
    df = jc.compute_lifecycle_stage(df, view_year=jc.CONSTRUCTION_YEAR)
    df = jc.compute_recommendation(df)
    return df, not_in_register


try:
    df_raw, not_in_register = process_jundu_file(uploaded.getvalue())
except Exception as e:
    st.error(f"Couldn't process this file: {e}. Make sure it has an 'LCCM Asset Components' sheet in the "
             f"same layout as the Jundunmunnah template.")
    st.stop()

n = len(df_raw)

# ============================================================================ KPI ROW
st.markdown("##### At a glance")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total assets", f"{n:,}")
c2.metric("Base life set", f"{df_raw['has_base_life'].sum():,} of {n:,}")
c3.metric("Total package cost", money(df_raw["Package Cost"].sum()))
c4.metric("Overdue / renewal due", f"{(df_raw['lcm_stage'].isin(['Overdue', 'Renewal Due'])).sum():,}")
c5.metric("Unique asset types", f"{df_raw['Asset / Component'].nunique()}")

st.markdown("---")

# ============================================================================ SAMP INPUTS / CONFIDENCE
st.markdown("##### SAMP Inputs: data confidence")
st.caption("Confidence combines two states from the source file: whether cost is Priced, and whether Base "
           "Life has been supplied. Both must be true for an asset to be forecast-ready.")

col1, col2 = st.columns([3, 2])
with col1:
    conf_counts = df_raw["confidence"].value_counts()
    def conf_color(c):
        if c.startswith("Not Ready"):
            return COLORS["critical"]
        if c.startswith("Ready"):
            return COLORS["good"]
        return COLORS["warn"]
    fig = go.Figure(go.Bar(
        y=conf_counts.index, x=conf_counts.values, orientation="h",
        marker_color=[conf_color(c) for c in conf_counts.index],
    ))
    fig.update_layout(height=280, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Assets")
    show_chart(fig)
with col2:
    st.markdown("**Known cost/scope gaps, from the file's own tracker**")
    known_gap_names = df_raw[df_raw["is_known_partial_cost"]]["Asset / Component"].unique()
    if len(known_gap_names):
        for name in known_gap_names:
            note = df_raw[df_raw["Asset / Component"] == name]["partial_cost_note"].iloc[0]
            st.markdown(f"- **{name}** \u2014 in register, {note.lower()}")
    if not_in_register:
        st.markdown("**Flagged but not in the register at all \u2014 needs adding from scratch:**")
        for item in not_in_register:
            st.markdown(f"- **{item['item']}** \u2014 {item['missing_info']}")

st.markdown("---")

# ============================================================================ COST ENGINE
st.markdown("##### SAMP Cost Engine: today's dollars")
ce_totals = jc.cost_engine_breakdown(df_raw)
col1, col2 = st.columns([3, 2])
with col1:
    ce_items = {k: v for k, v in ce_totals.items() if k != "Total package cost"}
    fig = go.Figure(go.Bar(
        x=list(ce_items.keys()), y=list(ce_items.values()), marker_color=COLORS["accent"],
    ))
    fig.update_layout(height=280, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$")
    show_chart(fig)
with col2:
    st.metric("Total package cost", money(ce_totals["Total package cost"]))
    st.caption(
        "SAMP's cost engine also names Delivery, Project, and Disposal steps. These are deliberately "
        "excluded from this asset register per the source workbook's own scope notes (treated as separate "
        "project on-costs, not asset lines)."
    )

st.markdown("---")

# ============================================================================ LIFECYCLE / TCO ASSUMPTIONS
st.markdown("##### SAMP Lifecycle & TCO: assumptions")
st.caption("These sliders recompute every forecast, TCO, and scenario number below \u2014 move them to "
           "stress-test the assumptions rather than take a single number on faith.")
a1, a2, a3 = st.columns(3)
escalation_pct = a1.slider("Cost escalation / yr (%)", 0.0, 10.0, 3.0, 0.5,
                            key="jundu_escalation", help="How much replacement cost grows each year from today's price.")
discount_pct = a2.slider("Discount rate (%)", 2.0, 15.0, 7.0, 0.5,
                          key="jundu_discount", help="Used for the present-value (NPV) and EAC calculations.")
horizon_years = a3.slider("Forecast horizon (years from now)", 10, 40, 20, 1, key="jundu_horizon")
escalation_rate = escalation_pct / 100
discount_rate = discount_pct / 100
horizon_end_year = jc.CONSTRUCTION_YEAR + horizon_years

df = jc.compute_escalated_cost(df_raw, escalation_rate, view_year=jc.CONSTRUCTION_YEAR)
df = jc.compute_tco(df, discount_rate, escalation_rate, view_year=jc.CONSTRUCTION_YEAR)

valid = df[df["has_base_life"]]
t1, t2, t3 = st.columns(3)
t1.metric("Nominal cost at renewal (all assets)", money(valid["cost_at_renewal"].sum()))
t2.metric("Present value of that cost", money(valid["pv_at_renewal"].sum()))
t3.metric("EAC of today's cost (all assets)", money(valid["eac_today"].sum()))

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Lifecycle stage distribution**")
    stage_counts = df["lcm_stage"].value_counts()
    stage_colors = {"New": COLORS["good"], "Mid-Life": COLORS["accent"], "Renewal Due": COLORS["warn"],
                    "Overdue": COLORS["critical"], "Unassessed": COLORS["steel"]}
    fig = go.Figure(go.Bar(
        x=stage_counts.index, y=stage_counts.values,
        marker_color=[stage_colors.get(s, COLORS["steel"]) for s in stage_counts.index],
    ))
    fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Assets")
    show_chart(fig)
with col2:
    st.markdown(f"**Repeating refurb forecast, {jc.CONSTRUCTION_YEAR}\u2013{horizon_end_year}**")
    events = jc.build_cycle_events(df, horizon_end_year, escalation_rate, view_year=jc.CONSTRUCTION_YEAR)
    if len(events):
        by_year = events.groupby("event_year")["cost"].sum()
        fig2 = go.Figure(go.Bar(x=by_year.index, y=by_year.values, marker_color=COLORS["accent"]))
        fig2.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="$")
        show_chart(fig2)
        st.caption("Each asset recurs every own base life \u2014 this is the '20yr refurb cost' vision "
                   "point: a repeating package, not a one-off.")
    else:
        st.info("No assets have a base life set yet, so no forecast can be projected.")

st.markdown("---")

# ============================================================================ RECOMMENDATIONS
st.markdown("##### SAMP Decision Logic: recommendations")
st.caption("Rule-based, evaluated in order: overdue first, then due within 2 years, then cost/lifecycle "
           "data gaps, then monitored by life stage. No machine learning \u2014 every category traces to a "
           "visible rule.")
rec_summary = df.groupby("recommendation").agg(count=("Package Cost", "count"), cost=("Package Cost", "sum"))
rec_summary = rec_summary.reindex(jc.RECOMMENDATION_ORDER).dropna(how="all")
cols = st.columns(len(rec_summary)) if len(rec_summary) else []
for col, (rec_name, row) in zip(cols, rec_summary.iterrows()):
    color = jc.RECOMMENDATION_COLORS.get(rec_name, COLORS["steel"])
    col.markdown(
        f"""<div style="background:{COLORS['surface']}; border:1px solid {COLORS['border']};
                    border-left:3px solid {color}; border-radius:10px; padding:12px;">
            <div style="font-size:11px; color:{COLORS['text_muted']};">{rec_name}</div>
            <div style="font-size:19px; font-weight:800; color:{COLORS['text']};">{int(row['count']):,}</div>
            <div style="font-size:11px; color:{COLORS['text_muted']};">{money(row['cost'])}</div>
        </div>""",
        unsafe_allow_html=True,
    )
with st.expander("View all assets by recommendation"):
    show_cols = ["Asset Group", "Asset / Component", "Condition", "Base Life", "Renewal Year",
                 "Cost Status", "Package Cost", "recommendation"]
    st.dataframe(
        df[show_cols].sort_values("recommendation"), width="stretch", hide_index=True,
        column_config={"Package Cost": st.column_config.NumberColumn(format="$%.0f")},
    )

st.markdown("---")

# ============================================================================ SCENARIO MODELING
st.markdown("##### SAMP Scenarios: budget simulation")
b1, b2, b3 = st.columns(3)
annual_budget = b1.number_input("Annual budget ($)", min_value=10_000, max_value=10_000_000, value=500_000,
                                 step=10_000, key="jundu_budget")
budget_growth_pct = b2.slider("Budget growth / yr (%)", -5.0, 15.0, 2.0, 0.5, key="jundu_growth")
deferral_escalation_pct = b3.slider("Deferral cost escalation / yr (%)", 0.0, 20.0, 6.0, 0.5, key="jundu_defer_esc")
budget_growth = budget_growth_pct / 100
deferral_escalation = deferral_escalation_pct / 100

if len(events):
    results = jc.run_jundu_scenario(events, jc.CONSTRUCTION_YEAR, horizon_end_year, annual_budget,
                                     budget_growth, deferral_escalation)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total spend, forecast window", money(results["spend"].sum()))
    m2.metric(f"Backlog by {horizon_end_year}", money(results.iloc[-1]["backlog_value"]))
    m3.metric("Events never funded", f"{int(results.iloc[-1]['assets_backlog']):,}")

    fig = go.Figure(go.Scatter(
        x=results["year"], y=results["backlog_value"], line=dict(color=COLORS["critical"], width=3),
        fill="tozeroy", name="Backlog",
    ))
    fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Unfunded backlog $")
    show_chart(fig)
else:
    results = pd.DataFrame({"year": [jc.CONSTRUCTION_YEAR], "budget": [annual_budget], "spend": [0],
                             "assets_funded": [0], "assets_backlog": [0], "backlog_value": [0]})
    st.info("No assets have a base life set yet, so no scenario can be simulated.")

st.markdown("---")

# ============================================================================ VISION TRACKER
st.markdown("##### Vision-text item tracker")
vision_status = jc.vision_point_status(df)
vt_rows = pd.DataFrame(vision_status)[["item", "vision_text", "status", "detail"]]
vt_rows.columns = ["Item", "Vision statement", "Status", "Detail"]
status_order = {"Ready": 0, "Cost incomplete": 1, "Needs base life": 1, "Missing entirely": 2}
vt_rows = vt_rows.sort_values(by="Status", key=lambda s: s.map(status_order).fillna(1))
st.dataframe(vt_rows, width="stretch", hide_index=True)

st.markdown("---")

# ============================================================================ EXPORTS
st.markdown("##### Export as a SAMP-format report")
st.caption("PDF: a written SAMP alignment report. PPTX: a slide deck matching the SAMP concept deck's "
           "section structure, populated with these live numbers.")

scope_label = f"{n:,} assets, Jundunmunnah refurb package"
kpis = {
    "Total assets": f"{n:,}",
    "Base life set": f"{df['has_base_life'].sum():,} of {n:,}",
    "Total package cost": money(df["Package Cost"].sum()),
    "Overdue / renewal due": f"{(df['lcm_stage'].isin(['Overdue', 'Renewal Due'])).sum():,}",
}
conf_summary_export = df.groupby("confidence").agg(count=("Package Cost", "count"), cost=("Package Cost", "sum"))
params_export = {"budget": annual_budget, "growth": budget_growth, "escalation": deferral_escalation,
                  "horizon": horizon_end_year}

exp1, exp2 = st.columns(2)
with exp1:
    if st.button("Generate PDF report", type="primary", key="jundu_pdf_btn"):
        pdf_bytes = jc.generate_jundu_pdf_report(
            scope_label, kpis, conf_summary_export, rec_summary, vision_status, ce_totals, results, params_export,
        )
        st.download_button("Download PDF", data=pdf_bytes, file_name="Jundunmunnah_SAMP_Report.pdf",
                            mime="application/pdf", key="jundu_pdf_dl")
with exp2:
    if st.button("Generate PPTX deck", type="primary", key="jundu_pptx_btn"):
        pptx_bytes = jc.generate_jundu_pptx(
            scope_label, kpis, conf_summary_export, ce_totals, rec_summary, vision_status, results, params_export,
        )
        st.download_button("Download PPTX", data=pptx_bytes, file_name="Jundunmunnah_SAMP_Deck.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            key="jundu_pptx_dl")
