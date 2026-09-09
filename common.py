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


def generate_scenario_pdf_report(scope_label: str, params_a: dict, params_b: dict,
                                  results_a: pd.DataFrame, results_b: pd.DataFrame,
                                  compare_on: bool) -> bytes:
    """Scenario A vs B business case: the backlog/spend delta as a funding-request document."""
    import io as _io
    from datetime import datetime
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                     Image as RLImage, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    navy = rl_colors.HexColor("#2B3797")
    muted = rl_colors.HexColor("#5B5F73")
    good = rl_colors.HexColor("#1F8A4C")
    bad = rl_colors.HexColor("#C23A3A")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleSC", parent=styles["Title"], textColor=navy, fontSize=19)
    h2 = ParagraphStyle("H2SC", parent=styles["Heading2"], textColor=navy, fontSize=13, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("BodySC", parent=styles["Normal"], fontSize=9.8, leading=14.5)
    small = ParagraphStyle("SmallSC", parent=styles["Normal"], fontSize=8.6, leading=12, textColor=muted)
    callout_num = ParagraphStyle("CalloutNum", parent=styles["Normal"], fontSize=22, leading=26,
                                  fontName="Helvetica-Bold")

    # --- chart: backlog over time, both scenarios, rendered with matplotlib -> PNG ---
    fig, ax = plt.subplots(figsize=(6.6, 3.0), dpi=160)
    ax.plot(results_a["year"], results_a["backlog_value"] / 1_000_000, color="#5A69D6", linewidth=2.4, label="Scenario A")
    ax.fill_between(results_a["year"], 0, results_a["backlog_value"] / 1_000_000, color="#5A69D6", alpha=0.15)
    if compare_on and results_b is not None:
        ax.plot(results_b["year"], results_b["backlog_value"] / 1_000_000, color="#ED1C24", linewidth=2.4, label="Scenario B")
    ax.set_ylabel("Unfunded backlog ($M)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    chart_buf = _io.BytesIO()
    fig.savefig(chart_buf, format="png")
    plt.close(fig)
    chart_buf.seek(0)

    story = []
    try:
        story.append(RLImage("assets/logo.png", width=28 * mm, height=9.4 * mm))
        story.append(Spacer(1, 6))
    except Exception:
        pass
    story.append(Paragraph("Scenario Business Case", title_style))
    story.append(Paragraph(f"Scope: {scope_label}", small))
    story.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}", small))
    story.append(Spacer(1, 12))

    end_a = results_a.iloc[-1]
    if compare_on and results_b is not None:
        end_b = results_b.iloc[-1]
        delta_backlog = end_b["backlog_value"] - end_a["backlog_value"]
        delta_color = good if delta_backlog < 0 else bad
        direction = "lower" if delta_backlog < 0 else "higher"
        story.append(Paragraph("The headline number", h2))
        story.append(Paragraph(
            f'<font color="{delta_color.hexval()}">{money(abs(delta_backlog))} {direction}</font> backlog by 2045 '
            f"under Scenario B (budget {money(params_b['budget'])}/yr) versus Scenario A "
            f"(budget {money(params_a['budget'])}/yr).", callout_num,
        ))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"Scenario A ends 2045 with {end_a['assets_backlog']:,.0f} assets never funded "
            f"({money(end_a['backlog_value'])} backlog). Scenario B ends with {end_b['assets_backlog']:,.0f} "
            f"({money(end_b['backlog_value'])} backlog).", body,
        ))
    else:
        story.append(Paragraph("The headline number", h2))
        story.append(Paragraph(
            f"{money(end_a['backlog_value'])} unfunded backlog by 2045", callout_num,
        ))
        story.append(Paragraph(
            f"Under a {money(params_a['budget'])}/yr budget, {end_a['assets_backlog']:,.0f} assets remain "
            f"unfunded by the end of the 20-year window.", body,
        ))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.6, color=rl_colors.HexColor("#DADCE8")))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Scenario parameters", h2))
    param_rows = [["Parameter", "Scenario A", "Scenario B" if compare_on else ""]]
    keys = [
        ("Annual budget", "budget", money),
        ("Budget growth / yr", "growth", lambda v: f"{v*100:.0f}%"),
        ("Deferral cost escalation / yr", "escalation", lambda v: f"{v*100:.0f}%"),
        ("Priority: risk vs. cost-efficiency", "risk_weight", lambda v: f"{v:.2f}"),
    ]
    for label, key, fmt in keys:
        row = [label, fmt(params_a[key])]
        if compare_on:
            row.append(fmt(params_b[key]))
        param_rows.append(row)
    param_table = Table(param_rows, colWidths=[65 * mm, 50 * mm, 50 * mm] if compare_on else [90 * mm, 75 * mm])
    param_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F5F6FA")]),
        ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(param_table)

    story.append(Spacer(1, 14))
    story.append(Paragraph("Unfunded backlog over time", h2))
    story.append(RLImage(chart_buf, width=160 * mm, height=72.7 * mm))

    story.append(Spacer(1, 10))
    story.append(Paragraph("20-year outcome summary", h2))
    summary_rows = [["Metric", "Scenario A", "Scenario B" if compare_on else ""]]
    metrics = [
        ("Total spend, 2026\u20132045", results_a["spend"].sum(), results_b["spend"].sum() if compare_on else None),
        ("Backlog value by 2045", end_a["backlog_value"], end_b["backlog_value"] if compare_on else None),
        ("Assets never funded", end_a["assets_backlog"], end_b["assets_backlog"] if compare_on else None),
        ("Peak annual spend", results_a["spend"].max(), results_b["spend"].max() if compare_on else None),
    ]
    for label, a_val, b_val in metrics:
        row = [label, money(a_val) if "spend" in label.lower() or "backlog" in label.lower() else f"{a_val:,.0f}"]
        if compare_on:
            row.append(money(b_val) if "spend" in label.lower() or "backlog" in label.lower() else f"{b_val:,.0f}")
        summary_rows.append(row)
    sm_table = Table(summary_rows, colWidths=[65 * mm, 50 * mm, 50 * mm] if compare_on else [90 * mm, 75 * mm])
    sm_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F5F6FA")]),
        ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(sm_table)

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "This report is a model estimate from FM Asset Excellence, not a committed capital plan. Figures "
        "reflect the assumptions and filters in place when this document was generated.", small,
    ))

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    doc.build(story)
    return buf.getvalue()


def generate_component_group_pdf(scope_label: str, group_name: str, sub: pd.DataFrame, params: dict,
                                  top_assets: pd.DataFrame) -> bytes:
    """Component-Group Replacement Business Case: focused on one asset type, e.g. an equipment fleet."""
    import io as _io
    from datetime import datetime
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                     Image as RLImage, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    navy = rl_colors.HexColor("#2B3797")
    muted = rl_colors.HexColor("#5B5F73")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCG", parent=styles["Title"], textColor=navy, fontSize=19)
    h2 = ParagraphStyle("H2CG", parent=styles["Heading2"], textColor=navy, fontSize=13, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("BodyCG", parent=styles["Normal"], fontSize=9.8, leading=14.5)
    small = ParagraphStyle("SmallCG", parent=styles["Normal"], fontSize=8.6, leading=12, textColor=muted)
    callout_num = ParagraphStyle("CalloutCG", parent=styles["Normal"], fontSize=22, leading=26, fontName="Helvetica-Bold")

    past_tip = sub[sub["life_fraction_used"] >= sub["tipping_life_fraction_live"]]
    n_total = len(sub)
    n_past = len(past_tip)
    cost_exposure = past_tip["cost"].sum()

    life_pct = np.linspace(0, 1.5, 60)
    avg_cost = sub["cost"].mean()
    avg_eac = sub["eac_replace_live"].mean()
    maint_curve = params["maint_base_pct"] * avg_cost * np.exp(params["maint_growth_k"] * life_pct)
    tip_x = sub["tipping_life_fraction_live"].mean()

    fig, ax = plt.subplots(figsize=(6.6, 3.0), dpi=160)
    ax.plot(life_pct * 100, maint_curve, color="#D4A017", linewidth=2.4, label="Rising maintenance cost")
    ax.axhline(avg_eac, color="#5A69D6", linewidth=2.2, linestyle="--", label="EAC of replacement")
    ax.axvline(tip_x * 100, color="#ED1C24", linewidth=1.6, linestyle=":", label=f"Tipping point ({tip_x*100:.0f}%)")
    ax.set_xlabel("% of base life used")
    ax.set_ylabel("$ / year")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=8.5)
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    chart_buf = _io.BytesIO()
    fig.savefig(chart_buf, format="png")
    plt.close(fig)
    chart_buf.seek(0)

    story = []
    try:
        story.append(RLImage("assets/logo.png", width=28 * mm, height=9.4 * mm))
        story.append(Spacer(1, 6))
    except Exception:
        pass
    story.append(Paragraph(f"{group_name} \u2014 Replacement Business Case", title_style))
    story.append(Paragraph(f"Scope: {scope_label}", small))
    story.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}", small))
    story.append(Spacer(1, 12))

    story.append(Paragraph("The headline number", h2))
    story.append(Paragraph(f"{money(cost_exposure)} in replacement cost is already past its tipping point", callout_num))
    story.append(Paragraph(
        f"{n_past:,} of {n_total:,} units in this component group ({n_past/max(n_total,1)*100:.0f}%) have "
        f"already crossed the point where replacing is cheaper than continuing to maintain, under the "
        f"assumptions below.", body,
    ))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.6, color=rl_colors.HexColor("#DADCE8")))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Assumptions used", h2))
    assum_rows = [
        ["Discount rate", f"{params['discount_rate']*100:.1f}%"],
        ["Starting maintenance cost", f"{params['maint_base_pct']*100:.1f}% of replacement cost/yr"],
        ["Maintenance escalation factor", f"{params['maint_growth_k']:.2f}"],
    ]
    at = Table(assum_rows, colWidths=[90 * mm, 75 * mm])
    at.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("TEXTCOLOR", (0, 0), (0, -1), muted),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#E4E4EC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(at)

    story.append(Spacer(1, 12))
    story.append(Paragraph("Maintain-vs-replace curve for this group", h2))
    story.append(RLImage(chart_buf, width=160 * mm, height=72.7 * mm))

    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Highest-priority units in {group_name}", h2))
    rows = [["Component", "Portfolio", "Condition", "Life used", "Est. cost"]] + [
        [str(r["component"])[:32], str(r["portfolio"])[:26], str(r["Condition"]),
         f"{r['life_fraction_used']*100:.0f}%", money(r["cost"])]
        for _, r in top_assets.iterrows()
    ]
    tt = Table(rows, colWidths=[48 * mm, 42 * mm, 22 * mm, 22 * mm, 31 * mm])
    tt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F5F6FA")]),
        ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tt)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "This report is a model estimate from FM Asset Excellence, not a committed capital plan.", small,
    ))

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    doc.build(story)
    return buf.getvalue()


def generate_data_quality_audit_pdf(scope_label: str, kpis: dict, confidence_by_portfolio: pd.DataFrame,
                                     confidence_by_group: pd.DataFrame, gaps: pd.DataFrame,
                                     faults: pd.DataFrame, overrides: pd.DataFrame) -> bytes:
    """Data Quality Audit: aimed inward, at whoever owns the source data -- a punch list for re-surveying."""
    import io as _io
    from datetime import datetime
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    navy = rl_colors.HexColor("#2B3797")
    muted = rl_colors.HexColor("#5B5F73")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleDQ", parent=styles["Title"], textColor=navy, fontSize=19)
    h2 = ParagraphStyle("H2DQ", parent=styles["Heading2"], textColor=navy, fontSize=13, spaceBefore=14, spaceAfter=6)
    small = ParagraphStyle("SmallDQ", parent=styles["Normal"], fontSize=8.6, leading=12, textColor=muted)
    body = ParagraphStyle("BodyDQ", parent=styles["Normal"], fontSize=9.6, leading=14)

    def styled_table(rows, col_widths, header_bg=None):
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_bg or navy),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F5F6FA")]),
            ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    story = []
    try:
        story.append(RLImage("assets/logo.png", width=28 * mm, height=9.4 * mm))
        story.append(Spacer(1, 6))
    except Exception:
        pass
    story.append(Paragraph("Data Quality Audit", title_style))
    story.append(Paragraph(f"Scope: {scope_label}", small))
    story.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}", small))
    story.append(Paragraph(
        "This report flags where the underlying source data is weakest, so it can be prioritised for a "
        "real survey rather than relying on system defaults.", body,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("At a glance", h2))
    kpi_rows = [[k, v] for k, v in kpis.items()]
    kt = Table(kpi_rows, colWidths=[85 * mm, 85 * mm])
    kt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("TEXTCOLOR", (0, 0), (0, -1), muted),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#E4E4EC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(kt)

    story.append(Spacer(1, 10))
    story.append(Paragraph("Confidence by portfolio", h2))
    rows = [["Portfolio", "High", "Medium", "Low"]] + confidence_by_portfolio.reset_index().values.tolist()
    rows = [rows[0]] + [[str(r[0])] + [f"{int(v):,}" for v in r[1:]] for r in rows[1:]]
    story.append(styled_table(rows, [65 * mm, 35 * mm, 35 * mm, 35 * mm]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Confidence by component group (top 10 by volume)", h2))
    rows2 = [["Component group", "High", "Medium", "Low"]] + confidence_by_group.reset_index().values.tolist()
    rows2 = [rows2[0]] + [[str(r[0])] + [f"{int(v):,}" for v in r[1:]] for r in rows2[1:]]
    story.append(styled_table(rows2, [65 * mm, 35 * mm, 35 * mm, 35 * mm]))

    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Biggest gaps \u2014 top {len(gaps)} highest-cost Low/Medium confidence assets", h2))
    rows3 = [["Component", "Portfolio", "Confidence", "Cost"]] + [
        [str(r["component"])[:32], str(r["portfolio"])[:26], r["data_confidence"], money(r["cost"])]
        for _, r in gaps.iterrows()
    ]
    story.append(styled_table(rows3, [55 * mm, 45 * mm, 28 * mm, 42 * mm]))

    if len(faults):
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"Active fault flags on file (top {len(faults)})", h2))
        rows4 = [["Component", "Portfolio", "Comment"]] + [
            [str(r["component"])[:28], str(r["portfolio"])[:22], str(r["comment"])[:60]]
            for _, r in faults.iterrows()
        ]
        story.append(styled_table(rows4, [42 * mm, 38 * mm, 90 * mm], header_bg=rl_colors.HexColor("#C23A3A")))

    if len(overrides):
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"Human overrides on file (top {len(overrides)})", h2))
        rows5 = [["Component", "System says", "Override says"]] + [
            [str(r["component"])[:40], str(int(r["next_renewal_year"])), str(int(r["replace_override_year"]))]
            for _, r in overrides.iterrows()
        ]
        story.append(styled_table(rows5, [90 * mm, 40 * mm, 40 * mm]))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Confidence combines missing survey data, a uniform construction year across a whole property, and "
        "the C-model condition-reset pattern. It is a heuristic, not a certainty.", small,
    ))

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    doc.build(story)
    return buf.getvalue()


def generate_work_order_pdf(scope_label: str, window_label: str, due_df: pd.DataFrame,
                             by_portfolio: pd.DataFrame, max_rows_per_portfolio: int = 40) -> bytes:
    """Next-12-Months Work Order Report: operational, grouped by portfolio, for whoever dispatches the work."""
    import io as _io
    from datetime import datetime
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    navy = rl_colors.HexColor("#2B3797")
    muted = rl_colors.HexColor("#5B5F73")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleWO", parent=styles["Title"], textColor=navy, fontSize=19)
    h2 = ParagraphStyle("H2WO", parent=styles["Heading2"], textColor=navy, fontSize=13, spaceBefore=14, spaceAfter=6)
    h3 = ParagraphStyle("H3WO", parent=styles["Heading3"], textColor=navy, fontSize=10.5, spaceBefore=10, spaceAfter=4)
    small = ParagraphStyle("SmallWO", parent=styles["Normal"], fontSize=8.6, leading=12, textColor=muted)
    body = ParagraphStyle("BodyWO", parent=styles["Normal"], fontSize=9.6, leading=14)

    story = []
    try:
        story.append(RLImage("assets/logo.png", width=28 * mm, height=9.4 * mm))
        story.append(Spacer(1, 6))
    except Exception:
        pass
    story.append(Paragraph("Work Order Report", title_style))
    story.append(Paragraph(f"Window: {window_label}", small))
    story.append(Paragraph(f"Scope: {scope_label}", small))
    story.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}", small))
    story.append(Paragraph(
        f"{len(due_df):,} components due, {money(due_df['cost'].sum())} total, across "
        f"{due_df['portfolio'].nunique()} portfolio(s).", body,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Summary by portfolio", h2))
    rows = [["Portfolio", "Components", "Total cost"]] + [
        [p, f"{int(r['components']):,}", money(r["cost"])] for p, r in by_portfolio.iterrows()
    ]
    st_table = Table(rows, colWidths=[85 * mm, 42 * mm, 43 * mm])
    st_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F5F6FA")]),
        ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(st_table)

    for portfolio in by_portfolio.index:
        subset = due_df[due_df["portfolio"] == portfolio].sort_values("urgency_score", ascending=False)
        shown = subset.head(max_rows_per_portfolio)
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"{portfolio} \u2014 {len(subset):,} due, {money(subset['cost'].sum())}", h3))
        rows2 = [["Component", "Site", "Condition", "Est. cost"]] + [
            [str(r["component"])[:38], str(r.get("site", ""))[:24], str(r["Condition"]), money(r["cost"])]
            for _, r in shown.iterrows()
        ]
        t2 = Table(rows2, colWidths=[70 * mm, 45 * mm, 22 * mm, 33 * mm])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#E4E7F7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8F8FB")]),
            ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t2)
        if len(subset) > max_rows_per_portfolio:
            story.append(Paragraph(f"Showing top {max_rows_per_portfolio} of {len(subset):,} by urgency.", small))

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    doc.build(story)
    return buf.getvalue()


def generate_asset_dossier_pdf(row: pd.Series) -> bytes:
    """Single-Asset Dossier: everything about one component, one page, for the 'why does this need $50K' question."""
    import io as _io
    from datetime import datetime
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    navy = rl_colors.HexColor("#2B3797")
    muted = rl_colors.HexColor("#5B5F73")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleAD", parent=styles["Title"], textColor=navy, fontSize=17)
    h2 = ParagraphStyle("H2AD", parent=styles["Heading2"], textColor=navy, fontSize=12.5, spaceBefore=12, spaceAfter=5)
    small = ParagraphStyle("SmallAD", parent=styles["Normal"], fontSize=8.6, leading=12, textColor=muted)
    body = ParagraphStyle("BodyAD", parent=styles["Normal"], fontSize=9.6, leading=14)

    years = [str(y) for y in range(2026, 2046)]
    values = [row.get(y, 0) or 0 for y in years]
    fig, ax = plt.subplots(figsize=(6.6, 2.2), dpi=160)
    ax.bar(years, values, color="#5A69D6")
    ax.set_ylabel("$")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    plt.tight_layout()
    chart_buf = _io.BytesIO()
    fig.savefig(chart_buf, format="png")
    plt.close(fig)
    chart_buf.seek(0)

    def kv_table(pairs, col_widths=(55 * mm, 115 * mm)):
        t = Table([[k, v] for k, v in pairs], colWidths=list(col_widths))
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("TEXTCOLOR", (0, 0), (0, -1), muted),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#E4E4EC")),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        return t

    story = []
    try:
        story.append(RLImage("assets/logo.png", width=26 * mm, height=8.7 * mm))
        story.append(Spacer(1, 6))
    except Exception:
        pass
    story.append(Paragraph(str(row["component"]), title_style))
    story.append(Paragraph(f"{row['property']} \u2014 {row.get('location', '')}", small))
    story.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}", small))

    story.append(Paragraph("Identity", h2))
    story.append(kv_table([
        ("Portfolio / Site", f"{row['portfolio']} / {row['site']}"),
        ("Group / Type", f"{row['comp. group']} / {row['comp. type']}"),
        ("Component ID", str(row["cmp_id"])),
    ]))

    story.append(Paragraph("Condition & dates", h2))
    survey_str = str(int(row["cmp_survey_year"])) if row["cmp_survey_year"] else "Missing"
    story.append(kv_table([
        ("Condition", str(row["Condition"])),
        ("Construction year", str(int(row["cmp_construction_year"]))),
        ("Survey year", survey_str),
        ("Data confidence", str(row["data_confidence"])),
    ]))

    story.append(Paragraph("Forecast & decision", h2))
    story.append(kv_table([
        ("System renewal year", str(int(row["next_renewal_year"]))),
        ("Age-based cross-check", str(int(row["est_replacement_year_age_based"]))),
        ("Best estimate year", str(int(row["best_estimate_year"]))),
        ("Decision", str(row["decision"])),
        ("Risk score", f"{row['risk_score']:.1f} / 100"),
        ("Urgency score", f"{row['urgency_score']:.1f} / 100"),
    ]))

    story.append(Paragraph("Economics", h2))
    story.append(kv_table([
        ("Replacement cost", money(row["cost"])),
        ("Equivalent annual cost", money(row["eac_replace"])),
        ("Life used", f"{row['life_fraction_used']*100:.0f}%"),
        ("Modelled tipping year", str(int(row["tipping_year"])) if pd.notna(row["tipping_year"]) else "n/a"),
    ]))

    if row.get("has_replace_override"):
        story.append(Paragraph(
            f"<b>Human override on file:</b> targets {int(row['replace_override_year'])}.", body,
        ))
    if row.get("comment"):
        story.append(Paragraph(f"<b>Comment on file:</b> \u201c{row['comment']}\u201d", body))

    story.append(Paragraph("Forecast profile, 2026\u20132045", h2))
    story.append(RLImage(chart_buf, width=160 * mm, height=53 * mm))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "This dossier is a model estimate from FM Asset Excellence, not a committed capital plan.", small,
    ))

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
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
