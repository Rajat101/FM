"""Shared helpers used by every page of the app."""
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

DATA_PATH = "data/processed.parquet"
YEARS_INT = list(range(2026, 2046))
YEARS = [str(y) for y in YEARS_INT]  # parquet stores column names as strings

# ---------------------------------------------------------------- design tokens
COLORS = {
    "bg": "#14171A",
    "surface": "#1E2226",
    "surface_2": "#262B30",
    "border": "#33393F",
    "text": "#EDEAE3",
    "text_muted": "#9AA0A6",
    "accent": "#C1622D",      # Pilbara iron-ore rust -- primary accent
    "accent_soft": "#8A4A26",
    "steel": "#4A7A94",       # secondary data series
    "good": "#6B8F71",        # spinifex green
    "warn": "#D4A017",        # amber
    "critical": "#A83232",    # deep red
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
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        html, body, [class*="css"] {{
            font-family: 'IBM Plex Sans', sans-serif;
        }}
        .stApp {{
            background-color: {COLORS['bg']};
            color: {COLORS['text']};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {COLORS['surface']};
            border-right: 1px solid {COLORS['border']};
        }}
        h1, h2, h3 {{
            font-family: 'IBM Plex Sans', sans-serif;
            font-weight: 600;
            letter-spacing: -0.01em;
        }}
        h1 {{ color: {COLORS['text']}; border-bottom: 2px solid {COLORS['accent']}; padding-bottom: 0.4rem; }}
        [data-testid="stMetricValue"] {{
            font-family: 'IBM Plex Mono', monospace;
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
            border-radius: 2px;
        }}
        .block-container {{ padding-top: 2rem; }}
        div[data-testid="stExpander"] {{
            background-color: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-radius: 2px;
        }}
        .stTabs [data-baseweb="tab"] {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.85rem;
        }}
        .panel-note {{
            background-color: {COLORS['surface']};
            border-left: 3px solid {COLORS['steel']};
            padding: 0.7rem 1rem;
            color: {COLORS['text_muted']};
            font-size: 0.88rem;
            margin-bottom: 1rem;
        }}
        hr {{ border-color: {COLORS['border']}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_template():
    tmpl = pio.templates["plotly_dark"].to_plotly_json()
    tmpl["layout"]["paper_bgcolor"] = COLORS["bg"]
    tmpl["layout"]["plot_bgcolor"] = COLORS["surface"]
    tmpl["layout"]["font"] = {"family": "IBM Plex Sans, sans-serif", "color": COLORS["text"]}
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
        font=dict(family="IBM Plex Sans, sans-serif", color=COLORS["text"]),
    )
    fig.update_xaxes(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"], linecolor=COLORS["border"])
    fig.update_yaxes(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"], linecolor=COLORS["border"])
    st.plotly_chart(fig, width="stretch", theme=None, **kwargs)


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_parquet(DATA_PATH)
    return df


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


# ------------------------------------------------------------- scenario engine
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
