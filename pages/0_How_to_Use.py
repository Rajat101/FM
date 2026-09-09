import streamlit as st
from common import inject_css, plotly_template, load_data, render_header, COLORS

st.set_page_config(page_title="How to Use", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("How to use this app")
st.caption("A quick orientation before your first pass \u2014 what each page is for, and a recommended order to read them in.")

st.markdown(
    f"""<div class="panel-note">This app processes your uploaded workbook entirely in memory for this
    session &mdash; nothing is saved to a server or shared with anyone else. If you refresh the page or
    it goes idle too long, you'll need to re-upload from the Home page sidebar.</div>""",
    unsafe_allow_html=True,
)

st.markdown("##### Recommended first pass")
steps = [
    ("Home", "Read the three insight cards first. They're generated fresh from your current filter and "
             "tell you where the real story is before you look at anything else."),
    ("Executive Summary", "The single page to present from if you only have five minutes. Headline "
             "numbers, top insights, one chart, and the top priority actions \u2014 no filters to fiddle with."),
    ("Risk & Condition", "Open the methodology expander and read the decision logic once. Every other "
             "page assumes you understand this."),
    ("Asset Explorer", "Pick two or three components you recognise and check their drill-down. Look "
             "specifically at the forecast_year_gap warning and data_confidence \u2014 this builds trust "
             "(or healthy scepticism) in the underlying numbers fast."),
    ("Data Quality", "See exactly which components and portfolios have the shakiest underlying data, and "
             "how much money sits behind those gaps, before you rely on any single forecast date."),
    ("Economic Tipping Points", "Select the component group that matters most to you and read its "
             "maintain-vs-replace curve. Try moving the discount rate and escalation sliders to see how "
             "sensitive the tipping point is to those assumptions."),
    ("Scenario Modeling", "Set Scenario A to your actual expected budget and Scenario B to a stretch or "
             "constrained alternative. Compare the backlog-by-2045 delta \u2014 this is usually the single "
             "most persuasive number for a budget conversation."),
    ("Recommendations", "Set thresholds that match your organisation's actual policy (not necessarily the "
             "app's defaults) and use the grouped tables as your action list."),
]
for i, (title, desc) in enumerate(steps, start=1):
    st.markdown(
        f"""<div style="display:flex; gap:14px; background:{COLORS['surface']}; border:1px solid {COLORS['border']};
                    border-radius:10px; padding:14px 18px; margin-bottom:8px;">
            <div style="font-size:20px; font-weight:800; color:{COLORS['accent']}; min-width:26px;">{i}</div>
            <div>
                <div style="font-weight:700; margin-bottom:2px;">{title}</div>
                <div style="font-size:13px; color:{COLORS['text_muted']};">{desc}</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("##### What every page covers")
page_dirs = [
    ("Home", "Insight banner, portfolio KPIs, a live scenario/forecast hero, and the three \u201chow it works\u201d visuals."),
    ("Executive Summary", "One-page briefing: headline numbers, top insights, one chart, top priority actions."),
    ("Asset Explorer", "Search, filter, and drill into any single component's full history and forecast."),
    ("Lifecycle Forecast", "Year-by-year CapEx/OpEx, portfolio and component-group breakdowns, deferred exposure."),
    ("Risk & Condition", "Risk scoring methodology, condition distribution, and the decision matrix."),
    ("Data Quality", "Where the underlying data is strong or shaky, and the dollar value riding on the gaps."),
    ("Economic Tipping Points", "Adjustable maintain-vs-replace economics, per component group and per asset."),
    ("Scenario Modeling", "The full budget simulation engine \u2014 compare two funding policies side by side."),
    ("Recommendations", "Set your own thresholds and get a live, grouped action list, exportable to PDF."),
    ("Field Notes", "What's actually written in the comments \u2014 known faults and human overrides on record."),
    ("Portfolio Benchmarking", "Compare portfolios head-to-head on cost, condition, risk, and overdue share."),
    ("Deferred-Cost Timeline", "What's due, and when \u2014 a year-by-year schedule instead of a dollar chart."),
]
cols = st.columns(2)
for i, (name, desc) in enumerate(page_dirs):
    with cols[i % 2]:
        st.markdown(
            f"""<div style="background:{COLORS['surface']}; border:1px solid {COLORS['border']}; border-left:3px solid {COLORS['steel']};
                        border-radius:8px; padding:12px 16px; margin-bottom:10px;">
                <div style="font-weight:700; font-size:13.5px;">{name}</div>
                <div style="font-size:12.5px; color:{COLORS['text_muted']};">{desc}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("##### Reading the numbers")
st.markdown(
    """
Every number in this app falls into one of three categories:

- **Straight from your workbook** &mdash; portfolio, cost, condition, base life. Challenge the data at the
  source if these look wrong.
- **Fixed calculations** &mdash; risk score, urgency score, the decision column, data confidence. These use
  one formula everywhere in the app (see the methodology expander on Risk & Condition).
- **Adjustable assumptions** &mdash; every slider on Economic Tipping Points, Scenario Modeling, and
  Recommendations. These are deliberately exposed so you can stress-test them rather than take the
  defaults on faith.

A full field-by-field glossary and every formula used in this app is available in the companion PDF guide,
if one has been shared with you separately.
    """
)
