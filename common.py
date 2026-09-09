"""Shared helpers used by every page of the app."""
import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

YEARS_INT = list(range(2026, 2046))
YEARS = [str(y) for y in YEARS_INT]

CURRENT_YEAR = 2026
CONDITION_NUM = {"C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}
CONDITION_LIFE_USED = {"C1": 0.10, "C2": 0.40, "C3": 0.65, "C4": 0.85, "C5": 0.97}

# ---------------------------------------------------------------- design tokens (Sodexo brand)
COLORS = {
    "bg": "#060B1F",
    "bg2": "#0A1440",
    "surface": "#101B4A",
    "surface_2": "#16215A",
    "border": "#2A3570",
    "text": "#F4F6FC",
    "text_muted": "#97A0CC",
    "accent": "#5A69D6",      # brand-light blue -- primary accent
    "accent_soft": "#2B3797", # Sodexo brand navy
    "steel": "#8AA0F0",       # secondary data series
    "good": "#2FBF7A",
    "warn": "#F5A623",
    "critical": "#ED1C24",    # Sodexo red -- reserved for overdue/critical only
}

DECISION_COLORS = {
    "Maintain": COLORS["good"],
    "Plan Renewal": COLORS["steel"],
    "Defer Candidate": COLORS["warn"],
    "Replace Now": COLORS["accent"],
    "Replace Now (Overdue)": COLORS["critical"],
}

CONFIDENCE_COLORS = {"High": COLORS["good"], "Medium": COLORS["warn"], "Low": COLORS["critical"]}


def inject_css():
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
        }}
        .stApp {{
            background:
                radial-gradient(ellipse 1400px 700px at 10% -10%, rgba(90,105,214,0.28), transparent),
                linear-gradient(160deg, {COLORS['bg']} 0%, {COLORS['bg2']} 45%, {COLORS['accent_soft']} 150%);
            color: {COLORS['text']};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {COLORS['bg2']};
            border-right: 1px solid {COLORS['border']};
        }}
        h1, h2, h3 {{
            font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
            font-weight: 700;
            letter-spacing: -0.01em;
        }}
        h1 {{ color: {COLORS['text']}; }}
        [data-testid="stMetricValue"] {{
            font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
            font-weight: 700;
            color: {COLORS['text']};
        }}
        [data-testid="stMetricLabel"] {{
            color: {COLORS['text_muted']};
        }}
        [data-testid="stMetric"] {{
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-left: 3px solid {COLORS['accent']};
            padding: 0.9rem 1rem;
            border-radius: 10px;
        }}
        .block-container {{ padding-top: 1.5rem; }}
        div[data-testid="stExpander"] {{
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
        }}
        .stTabs [data-baseweb="tab"] {{
            font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
            font-size: 0.85rem;
        }}
        .panel-note {{
            background-color: {COLORS['surface']};
            border-left: 3px solid {COLORS['steel']};
            padding: 0.7rem 1rem;
            color: {COLORS['text_muted']};
            font-size: 0.88rem;
            margin-bottom: 1rem;
            border-radius: 0 10px 10px 0;
        }}
        .insight-card {{
            background: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-left: 3px solid {COLORS['accent']};
            border-radius: 10px;
            padding: 16px 18px;
            height: 100%;
        }}
        .insight-card.warn {{ border-left-color: {COLORS['warn']}; }}
        .insight-card.critical {{ border-left-color: {COLORS['critical']}; }}
        .insight-card .headline {{
            font-size: 15px; font-weight: 700; line-height: 1.4; margin-bottom: 6px; color: {COLORS['text']};
        }}
        .insight-card .detail {{
            font-size: 13px; color: {COLORS['text_muted']}; line-height: 1.5;
        }}
        .fm-header {{ display: flex; align-items: center; gap: 16px; padding: 4px 0 18px; }}
        .fm-logo-plate {{ background: #fff; border-radius: 10px; padding: 8px 12px; display: flex; align-items: center; }}
        .fm-logo-plate img {{ height: 22px; display: block; }}
        .fm-header .fm-title {{ font-size: 24px; font-weight: 800; color: {COLORS['text']}; margin: 0; }}
        .fm-header .fm-subtitle {{ font-size: 13px; color: {COLORS['text_muted']}; margin: 2px 0 0; }}
        .badge-tag {{
            display: inline-block; font-size: 11px; letter-spacing: .04em; font-weight: 600;
            color: {COLORS['text_muted']}; border: 1px solid {COLORS['border']}; border-radius: 100px;
            padding: 4px 12px; margin-bottom: 18px;
        }}
        .flow-step {{
            display: flex; align-items: center; gap: 10px; font-size: 12.5px; padding: 8px 12px;
            background: {COLORS['surface_2']}; border-radius: 8px; border: 1px solid {COLORS['border']};
            color: {COLORS['text']}; margin-bottom: 2px;
        }}
        .flow-step .dot {{ width: 7px; height: 7px; border-radius: 50%; background: {COLORS['accent']}; flex-shrink:0; }}
        .flow-step.tip {{ border-color: {COLORS['warn']}; }}
        .flow-step.tip .dot {{ background: {COLORS['warn']}; }}
        .flow-arrow {{ text-align: center; font-size: 12px; color: {COLORS['text_muted']}; padding: 2px 0; }}
        hr {{ border-color: {COLORS['border']}; }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
        }}
        [data-testid="stToolbar"] {{
            background: transparent !important;
        }}
        [data-testid="stDecoration"] {{
            background-image: none !important;
            background: transparent !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )



@st.cache_resource
def _logo_b64():
    import base64
    with open("assets/logo.png", "rb") as f:
        return base64.b64encode(f.read()).decode()


def render_header(subtitle: str):
    try:
        logo = _logo_b64()
        logo_html = f'<div class="fm-logo-plate"><img src="data:image/png;base64,{logo}" alt="Sodexo"></div>'
    except Exception:
        logo_html = ""
    st.markdown(
        f"""
        <div class="fm-header">
            {logo_html}
            <div>
                <p class="fm-title">FM Asset Excellence</p>
                <p class="fm-subtitle">{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_flow_diagram():
    steps = [
        ("Asset acquisition &mdash; CapEx", False),
        ("In operation &mdash; routine O&amp;M / OpEx", False),
        ("Asset ages, condition declines", False),
        ("Failures more frequent and costly", False),
        ("&#9733; Economic tipping point", True),
        ("Replacement CapEx &mdash; new cycle begins", False),
    ]
    html = ""
    for i, (label, is_tip) in enumerate(steps):
        cls = "flow-step tip" if is_tip else "flow-step"
        html += f'<div class="{cls}"><span class="dot"></span>{label}</div>'
        if i < len(steps) - 1:
            html += '<div class="flow-arrow">&darr;</div>'
    st.markdown(html, unsafe_allow_html=True)


def generate_insights(df: pd.DataFrame):
    """Real, data-driven insight callouts -- not sample copy."""
    insights = []
    n = len(df)
    overdue = df["already_overdue"].sum()
    if overdue > 0:
        pct = overdue / n * 100
        insights.append({
            "level": "critical",
            "headline": f"{pct:.0f}% of assets are already past due",
            "detail": f"{overdue:,} components have missed their calculated renewal year "
                      f"&mdash; {money(df.loc[df['already_overdue'],'cost'].sum())} in deferred exposure sitting unfunded today.",
        })

    reset_risk = df["condition_reset_risk"].sum()
    if reset_risk > 0:
        insights.append({
            "level": "warn",
            "headline": "Recently-surveyed equipment may be under-forecast",
            "detail": f"{reset_risk:,} components were rated in good condition on a recent survey but have a short "
                      f"base life &mdash; the model may be resetting their clock rather than tracking true age.",
        })

    by_port = df.groupby("portfolio")[YEARS].sum().sum(axis=1).sort_values(ascending=False)
    if len(by_port) >= 2:
        top2_share = by_port.head(2).sum() / by_port.sum() * 100
        insights.append({
            "level": "normal",
            "headline": f"{by_port.index[0]} and {by_port.index[1]} drive {top2_share:.0f}% of forecast spend",
            "detail": "A natural place to focus renewal planning first, given how concentrated the 20-year "
                      "CapEx forecast is across just two portfolios.",
        })
    return insights[:3]


def plotly_template():
    tmpl = pio.templates["plotly_dark"].to_plotly_json()
    tmpl["layout"]["paper_bgcolor"] = COLORS["bg"]
    tmpl["layout"]["plot_bgcolor"] = COLORS["surface"]
    tmpl["layout"]["font"] = {"family": "-apple-system, Segoe UI, Roboto, Arial, sans-serif", "color": COLORS["text"]}
    tmpl["layout"]["colorway"] = [
        COLORS["accent"], COLORS["steel"], COLORS["good"], COLORS["warn"],
        COLORS["critical"], "#B08968", "#7A8B99",
    ]
    tmpl["layout"]["xaxis"] = {"gridcolor": COLORS["border"], "zerolinecolor": COLORS["border"]}
    tmpl["layout"]["yaxis"] = {"gridcolor": COLORS["border"], "zerolinecolor": COLORS["border"]}
    pio.templates["pannawonica"] = go.layout.Template(tmpl)
    pio.templates.default = "pannawonica"


def show_chart(fig, **kwargs):
    """Render a plotly figure with the dark theme forced at the figure level --
    belt-and-suspenders against Streamlit's own theme overriding template defaults."""
    fig.update_layout(
        template="pannawonica",
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["surface"],
        font=dict(family="-apple-system, Segoe UI, Roboto, Arial, sans-serif", color=COLORS["text"]),
    )
    # automargin=True re-enables Plotly's automatic space allocation for tick
    # labels -- without it, a fixed-zero margin (used elsewhere for tight
    # layouts) silently clips y-axis numbers and long category names.
    fig.update_xaxes(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"], linecolor=COLORS["border"],
                      automargin=True)
    fig.update_yaxes(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"], linecolor=COLORS["border"],
                      automargin=True)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False}, **kwargs)


def _clean_workbook(df: pd.DataFrame) -> pd.DataFrame:
    """Full cleaning + feature pipeline, run in-memory on whatever workbook was uploaded."""
    df.columns = [str(c).strip() for c in df.columns]
    df["comment"] = df["comment"].apply(lambda v: v if isinstance(v, str) else ("" if pd.isna(v) else str(v)))

    # --- quality flags -------------------------------------------------
    df["survey_missing"] = df["cmp_survey_year"] == 0
    nunique_years = df.groupby("property code")["cmp_construction_year"].transform("nunique")
    n_components = df.groupby("property code")["cmp_construction_year"].transform("count")
    df["construction_year_uniform_property"] = (nunique_years == 1) & (n_components >= 5)
    df["already_overdue"] = df["next_renewal_year"] < CURRENT_YEAR
    df["renewal_beyond_window"] = df["next_renewal_year"] > 2045
    df["condition_reset_risk"] = (
        (df["calc_method"] == "C")
        & (df["cmp_survey_year"] >= 2023)
        & df["Condition"].isin(["C1", "C2"])
        & (df["base_life"] <= 20)
    )
    conf = pd.Series(100.0, index=df.index)
    conf -= df["survey_missing"] * 30
    conf -= df["construction_year_uniform_property"] * 15
    conf -= df["condition_reset_risk"] * 25
    conf = conf.clip(0, 100)
    df["data_confidence_score"] = conf
    df["data_confidence"] = pd.cut(conf, bins=[-1, 59, 89, 101], labels=["Low", "Medium", "High"])

    # --- mine free-text comments ---------------------------------------
    c = df["comment"].fillna("")
    df["has_replace_override"] = c.str.contains(r"replace by", case=False, regex=True)
    df["replace_override_year"] = c.str.extract(r"[Rr]eplace by\s*(\d{4})", expand=False).astype("float")
    df["has_fault_note"] = c.str.contains(r"leak|crack|fault|damage|broken|not working", case=False, regex=True)
    df["has_maintenance_record"] = c.str.contains(r"order:|replaced", case=False, regex=True)

    # --- lifecycle estimates ---------------------------------------------
    df["condition_numeric"] = df["Condition"].map(CONDITION_NUM)
    life_used_frac = df["Condition"].map(CONDITION_LIFE_USED)
    age = CURRENT_YEAR - df["cmp_construction_year"]
    df["est_replacement_year_age_based"] = CURRENT_YEAR + (df["base_life"] - age)
    df["forecast_year_gap"] = (df["next_renewal_year"] - df["est_replacement_year_age_based"]).round(0)
    df["best_estimate_year"] = np.where(
        df["has_replace_override"] & df["replace_override_year"].notna(),
        df["replace_override_year"],
        df["next_renewal_year"],
    )
    df["life_fraction_used"] = np.clip(life_used_frac, 0, 1.5)

    # --- risk + economics -------------------------------------------------
    raw_risk = df["condition_numeric"] * df["consequence"] * df["safety"]
    df["risk_score"] = (raw_risk / raw_risk.max() * 100).round(1)
    urgency = df["risk_score"].copy()
    urgency += df["already_overdue"] * 15
    urgency += df["condition_reset_risk"] * 10
    df["urgency_score"] = np.clip(urgency, 0, 100).round(1)

    discount_rate, maint_base_pct, maint_growth_k = 0.07, 0.02, 3.0
    n = df["base_life"].clip(lower=1)
    r = discount_rate
    crf = (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    df["eac_replace"] = (df["cost"] * crf).round(2)
    x = df["life_fraction_used"].clip(0, 1.5)
    df["annual_maintenance_cost_now"] = (maint_base_pct * df["cost"] * np.exp(maint_growth_k * x)).round(2)
    with np.errstate(divide="ignore", invalid="ignore"):
        x_star = np.log(df["eac_replace"] / (maint_base_pct * df["cost"]).replace(0, np.nan)) / maint_growth_k
    x_star = x_star.clip(lower=0, upper=1.5)
    df["tipping_life_fraction"] = x_star
    df["tipping_year"] = (df["cmp_construction_year"] + x_star * df["base_life"]).round(0)

    def decide(row):
        if row["already_overdue"]:
            return "Replace Now (Overdue)"
        if row["life_fraction_used"] >= 0.85:
            return "Replace Now" if row["risk_score"] >= 40 else "Defer Candidate"
        if row["life_fraction_used"] >= 0.55:
            return "Plan Renewal"
        return "Maintain"

    df["decision"] = df.apply(decide, axis=1)

    # keep year columns as strings throughout the app, regardless of source
    df = df.rename(columns={y: str(y) for y in YEARS_INT if y in df.columns})
    return df


@st.cache_data(show_spinner="Cleaning workbook and computing lifecycle model...")
def process_workbook(file_bytes: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0)
    return _clean_workbook(raw)


def load_data() -> pd.DataFrame:
    """Returns the processed dataframe, prompting for an upload if one isn't
    already in this session. Cached in session_state so switching pages
    doesn't reprocess or re-prompt."""
    if "processed_df" in st.session_state:
        st.sidebar.markdown("### Data source")
        st.sidebar.caption(f"Loaded: **{st.session_state.get('uploaded_filename', 'workbook')}**")
        if st.sidebar.button("Change file", key="change_file_btn"):
            del st.session_state["processed_df"]
            st.rerun()
        return st.session_state["processed_df"]

    st.sidebar.markdown("### Data source")
    uploaded = st.sidebar.file_uploader("Upload Lifecycle_PAN.xlsx", type=["xlsx"])
    if uploaded is None:
        render_header("Upload your workbook to begin")
        st.info(
            "Upload the **Lifecycle_PAN.xlsx** workbook in the sidebar to load the model. "
            "Nothing is stored beyond this session -- the file is processed in memory only."
        )
        st.stop()

    df = process_workbook(uploaded.getvalue())
    st.session_state["processed_df"] = df
    st.session_state["uploaded_filename"] = uploaded.name
    st.rerun()


def money(x, decimals=0):
    if pd.isna(x):
        return "-"
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:,.{max(decimals,1)}f}M"
    if abs(x) >= 1_000:
        return f"${x/1_000:,.0f}K"
    return f"${x:,.0f}"


def sidebar_filters(df: pd.DataFrame, key_prefix=""):
    st.sidebar.markdown("### Filters")
    portfolios = sorted(df["portfolio"].unique())
    sel_portfolio = st.sidebar.multiselect(
        "Portfolio", portfolios, default=portfolios, key=f"{key_prefix}_portfolio"
    )
    d = df[df["portfolio"].isin(sel_portfolio)] if sel_portfolio else df

    groups = sorted(d["comp. group"].unique())
    sel_group = st.sidebar.multiselect(
        "Component group", groups, default=[], key=f"{key_prefix}_group",
        help="Leave empty to include all component groups"
    )
    if sel_group:
        d = d[d["comp. group"].isin(sel_group)]
    return d


def compute_tipping_economics(df: pd.DataFrame, discount_rate: float, maint_base_pct: float, maint_growth_k: float):
    """Live recompute of EAC-vs-maintenance tipping point for the What-If controls."""
    d = df.copy()
    n = d["base_life"].clip(lower=1)
    r = discount_rate
    crf = (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    d["eac_replace_live"] = d["cost"] * crf
    x = d["life_fraction_used"].clip(0, 1.5)
    d["annual_maintenance_now_live"] = maint_base_pct * d["cost"] * np.exp(maint_growth_k * x)
    with np.errstate(divide="ignore", invalid="ignore"):
        x_star = np.log(d["eac_replace_live"] / (maint_base_pct * d["cost"]).replace(0, np.nan)) / maint_growth_k
    d["tipping_life_fraction_live"] = x_star.clip(lower=0, upper=1.5)
    d["tipping_year_live"] = (d["cmp_construction_year"] + d["tipping_life_fraction_live"] * d["base_life"]).round(0)
    return d


# ------------------------------------------------------------- recommendation engine
def compute_recommendations(df: pd.DataFrame, life_maintain_max=0.55, life_plan_max=0.85,
                             risk_high_threshold=40.0, budget_cap=None):
    """Classify every component into a recommendation bucket using stakeholder-set
    thresholds (not the fixed thresholds baked into the original 'decision' column).
    Vectorised with np.select for speed across 100k+ rows."""
    d = df.copy()
    conditions = [
        d["already_overdue"],
        (d["life_fraction_used"] >= life_plan_max) & (d["risk_score"] >= risk_high_threshold),
        (d["life_fraction_used"] >= life_plan_max),
        (d["life_fraction_used"] >= life_maintain_max),
    ]
    choices = ["Replace Now (Overdue)", "Replace Now", "Defer Candidate", "Plan Renewal"]
    d["recommendation"] = np.select(conditions, choices, default="Maintain")

    if budget_cap:
        replace_mask = d["recommendation"].isin(["Replace Now", "Replace Now (Overdue)"])
        replace_df = d[replace_mask].sort_values("urgency_score", ascending=False)
        cum_cost = replace_df["cost"].cumsum()
        over_budget_ids = set(replace_df.loc[cum_cost > budget_cap, "cmp_id"])
        d.loc[d["cmp_id"].isin(over_budget_ids), "recommendation"] = "Replace \u2014 Budget Constrained"

    return d


RECOMMENDATION_ORDER = [
    "Replace Now (Overdue)", "Replace \u2014 Budget Constrained", "Replace Now",
    "Plan Renewal", "Defer Candidate", "Maintain",
]
RECOMMENDATION_COLORS = {
    "Replace Now (Overdue)": "#ED1C24",
    "Replace \u2014 Budget Constrained": "#F5A623",
    "Replace Now": "#5A69D6",
    "Plan Renewal": "#8AA0F0",
    "Defer Candidate": "#F5A623",
    "Maintain": "#2FBF7A",
}


# ------------------------------------------------------------- PDF report
def generate_pdf_report(scope_label: str, kpis: dict, insights: list, rec_summary: pd.DataFrame,
                         rec_samples: dict, params: dict) -> bytes:
    """Builds a summary PDF: KPIs, insights, recommendation counts/costs per
    category, and a small top-N sample per category -- never the full row set."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io as _io
    from datetime import datetime

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                             leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    navy = rl_colors.HexColor("#2B3797")
    muted = rl_colors.HexColor("#5B5F73")
    title_style = ParagraphStyle("TitleFM", parent=styles["Title"], textColor=navy, fontSize=20)
    h2 = ParagraphStyle("H2FM", parent=styles["Heading2"], textColor=navy, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("BodyFM", parent=styles["Normal"], fontSize=9.5, leading=13.5)
    small_muted = ParagraphStyle("SmallMuted", parent=styles["Normal"], fontSize=8.5, textColor=muted)

    story = []
    try:
        story.append(RLImage("assets/logo.png", width=28 * mm, height=9.4 * mm))
        story.append(Spacer(1, 6))
    except Exception:
        pass
    story.append(Paragraph("FM Asset Excellence \u2014 Recommendation Report", title_style))
    story.append(Paragraph(f"Scope: {scope_label}", small_muted))
    story.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}", small_muted))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Portfolio at a glance", h2))
    kpi_rows = [[k, v] for k, v in kpis.items()]
    kpi_table = Table(kpi_rows, colWidths=[75 * mm, 95 * mm])
    kpi_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), muted),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#E4E4EC")),
    ]))
    story.append(kpi_table)

    if insights:
        story.append(Paragraph("What this data is telling you", h2))
        for ins in insights:
            story.append(Paragraph(f"<b>{ins['headline']}</b>", body))
            story.append(Paragraph(ins["detail"], small_muted))
            story.append(Spacer(1, 4))

    story.append(Paragraph("Recommendation summary", h2))
    story.append(Paragraph(
        f"Thresholds used: maintain below {params['life_maintain_max']*100:.0f}% of life used, "
        f"plan renewal from {params['life_maintain_max']*100:.0f}\u2013{params['life_plan_max']*100:.0f}%, "
        f"high risk \u2265 {params['risk_high_threshold']:.0f}/100"
        + (f", budget cap {money(params['budget_cap'])}/yr" if params.get("budget_cap") else "") + ".",
        small_muted,
    ))
    story.append(Spacer(1, 6))
    summary_rows = [["Recommendation", "Assets", "Total cost"]] + [
        [r["Recommendation"], f"{int(r['Assets']):,}", r["Total cost"]] for _, r in rec_summary.iterrows()
    ]
    summary_table = Table(summary_rows, colWidths=[80 * mm, 40 * mm, 50 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F5F6FA")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
    ]))
    story.append(summary_table)

    for category, sample_df in rec_samples.items():
        if sample_df is None or len(sample_df) == 0:
            continue
        total_n = int(rec_summary.loc[rec_summary["Recommendation"] == category, "Assets"].values[0]) \
            if (rec_summary["Recommendation"] == category).any() else len(sample_df)
        story.append(Paragraph(f"{category} \u2014 top {len(sample_df)} of {total_n:,} by urgency", h2))
        rows = [["Component", "Portfolio", "Condition", "Est. cost"]] + [
            [str(r["component"])[:40], str(r["portfolio"])[:28], str(r["Condition"]), money(r["cost"])]
            for _, r in sample_df.iterrows()
        ]
        t = Table(rows, colWidths=[62 * mm, 48 * mm, 22 * mm, 38 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#E4E7F7")),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8F8FB")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
        ]))
        story.append(t)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "This report summarises model estimates from FM Asset Excellence and is not a committed capital plan. "
        "Full asset-level detail is available in the live app.", small_muted,
    ))
    doc.build(story)
    return buf.getvalue()
def run_budget_scenario(
    df: pd.DataFrame,
    annual_budget: float,
    budget_growth: float,
    years: list,
    escalation_rate: float,
    risk_weight: float,
    start_year: int = 2026,
):
    """
    Year-by-year simulation: each year, components whose best_estimate_year
    has arrived (or already has) compete for that year's budget, ranked by a
    blended urgency/cost-efficiency score. Anything not funded carries into
    next year with its cost escalated (deferral compounds) and its urgency
    increased.
    """
    work = df[["cmp_id", "portfolio", "comp. group", "component", "cost", "urgency_score",
               "risk_score", "best_estimate_year"]].copy()
    work["due_year"] = work["best_estimate_year"].clip(upper=years[-1])
    work["remaining_cost"] = work["cost"].astype(float)
    work["current_urgency"] = work["urgency_score"].astype(float)
    work["years_deferred"] = 0
    work["funded_year"] = np.nan
    pending = work[work["due_year"] <= start_year].copy()
    upcoming = work[work["due_year"] > start_year].copy()

    budget = annual_budget
    yearly_results = []
    for i, yr in enumerate(years):
        newly_due = upcoming[upcoming["due_year"] == yr]
        if len(newly_due):
            pending = pd.concat([pending, newly_due], ignore_index=True)
            upcoming = upcoming[upcoming["due_year"] != yr]

        if len(pending):
            cost_eff = pending["current_urgency"] / pending["remaining_cost"].clip(lower=1)
            pending["priority"] = risk_weight * pending["current_urgency"] + (1 - risk_weight) * (
                cost_eff / cost_eff.max() * 100
            )
            pending = pending.sort_values("priority", ascending=False)
            cum_cost = pending["remaining_cost"].cumsum()
            can_fund = cum_cost <= budget
            funded = pending[can_fund].copy()
            not_funded = pending[~can_fund].copy()
        else:
            funded, not_funded = pending.iloc[0:0].copy(), pending.iloc[0:0].copy()

        spend = funded["remaining_cost"].sum()
        yearly_results.append({
            "year": yr,
            "budget": budget,
            "spend": spend,
            "underspend": budget - spend,
            "assets_funded": len(funded),
            "assets_backlog": len(not_funded),
            "backlog_value": not_funded["remaining_cost"].sum(),
            "backlog_risk": not_funded["current_urgency"].sum(),
        })

        not_funded["remaining_cost"] *= (1 + escalation_rate)
        not_funded["current_urgency"] = np.clip(not_funded["current_urgency"] * (1 + escalation_rate * 0.5), 0, 100)
        not_funded["years_deferred"] += 1
        pending = not_funded

        budget *= (1 + budget_growth)

    return pd.DataFrame(yearly_results), pending
