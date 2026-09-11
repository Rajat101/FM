# -*- coding: utf-8 -*-
"""
Jundunmunnah Refurbishment LCCM engine.
Separate from common.py because the schema, scope, and lifecycle assumptions are
fundamentally different from the Pannawonica dataset: this is a small (~170 row),
brand-new refurbishment package (all Condition C1, built in a single year), not an
aged multi-thousand-asset portfolio. All calculations here are transparent formulas
(escalation, capital recovery factor, rule-based staging) -- no machine learning,
consistent with how the rest of FM Asset Excellence works.
"""
import io
import numpy as np
import pandas as pd

from common import COLORS, money  # reuse the shared Sodexo palette and $ formatter

CONSTRUCTION_YEAR = 2026  # every Jundunmunnah asset is freshly built/refurbished in this year

CONDITION_MAP = {"C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}

def cost_engine_breakdown(df: pd.DataFrame) -> dict:
    """
    SAMP cost-engine breakdown in real dollars. Per-room-rate columns must be extended by
    Rooms to reach package totals -- Package Cost = (Supply + Install + Equipment Cost/Room) x Rooms.
    """
    supply_total = (df["Supply Cost / Room"] * df["Rooms"]).sum()
    install_total = (df["Install Cost / Room"] * df["Rooms"]).sum()
    equip_total = (df["Equipment Cost / Room"] * df["Rooms"]).sum()
    return {
        "Supply (Base item)": supply_total,
        "Install (Labour)": install_total,
        "Equipment": equip_total,
        "Total package cost": df["Package Cost"].sum(),
    }


def load_missing_cost_inputs(file) -> pd.DataFrame:
    """
    Read the workbook's own 'Missing Cost Inputs' sheet (if present) rather than hardcoding
    the flagged item list -- self-updating if the stakeholder's own tracked gaps change.
    Returns empty DataFrame if the sheet is absent or unreadable.
    """
    try:
        raw = pd.read_excel(file, sheet_name="Missing Cost Inputs", header=None)
    except Exception:
        return pd.DataFrame(columns=["Asset / Component", "Status", "Missing Information"])
    header_row = None
    for i, row in raw.iterrows():
        if str(row.iloc[1]).strip() == "Asset / Component":
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame(columns=["Asset / Component", "Status", "Missing Information"])
    tbl = raw.iloc[header_row + 1:].copy()
    tbl.columns = raw.iloc[header_row]
    tbl = tbl.dropna(subset=["Asset / Component"])
    return tbl.reset_index(drop=True)


def flag_partial_cost_items(df: pd.DataFrame, missing_cost_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cross-reference the main asset register against the Missing Cost Inputs sheet.
    An item only counts as 'in register but cost-incomplete' if its name actually appears
    as a row -- items named there that DON'T appear in the register (e.g. Smart TV, Bar
    Fridge, Bed and Mattress in the source file) are a different, more serious gap: the
    asset is entirely absent, not just under-costed.
    """
    df = df.copy()
    df["is_known_partial_cost"] = False
    df["partial_cost_note"] = None
    not_in_register = []
    if len(missing_cost_df) == 0:
        return df, not_in_register

    register_names = set(df["Asset / Component"].str.lower())
    for _, r in missing_cost_df.iterrows():
        flagged_name = str(r["Asset / Component"]).strip()
        status = str(r.get("Status", "")).strip()
        fl = flagged_name.lower()
        matched = df["Asset / Component"].str.lower().apply(lambda n: fl in n or n in fl)
        if matched.any():
            df.loc[matched, "is_known_partial_cost"] = True
            df.loc[matched, "partial_cost_note"] = status
        else:
            not_in_register.append({"item": flagged_name, "status": status,
                                     "missing_info": str(r.get("Missing Information", ""))})
    return df, not_in_register

# Vision-text items, matched against Asset / Component values (case-insensitive, word-boundary safe).
VISION_ITEMS = [
    ("Bed and Mattress", r"\bbed\b", "Add in Bed and chair and exhaust replacement life 5 yrs"),
    ("Chair", r"\bchair\b", "Add in Bed and chair and exhaust replacement life 5 yrs"),
    ("Exhaust Fan", r"\bexhaust\b", "Add in Bed and chair and exhaust replacement life 5 yrs"),
    ("Painting", r"\bpaint", "10 yr paint HVAC and HWS"),
    ("Split System Air Conditioner", r"split system|air condition", "10 yr paint HVAC and HWS"),
    ("Hot Water Unit / Isolator", r"hot water", "10 yr paint HVAC and HWS"),
]

RECOMMENDATION_ORDER = [
    "Overdue \u2014 Replace Now", "Renewal Due (\u22642 yrs)", "Needs Cost Confirmation",
    "Needs Base Life", "Mid-Life \u2014 Monitor", "New \u2014 Monitor",
]
RECOMMENDATION_COLORS = {
    "Overdue \u2014 Replace Now": COLORS["critical"],
    "Renewal Due (\u22642 yrs)": COLORS["warn"],
    "Needs Cost Confirmation": "#B45FCE",
    "Needs Base Life": COLORS["steel"],
    "Mid-Life \u2014 Monitor": COLORS["accent"],
    "New \u2014 Monitor": COLORS["good"],
}


def load_jundu_workbook(file) -> pd.DataFrame:
    """Load and clean the 'LCCM Asset Components' sheet from an uploaded Jundunmunnah-format workbook."""
    df = pd.read_excel(file, sheet_name="LCCM Asset Components", header=3)
    df = df.dropna(how="all").reset_index(drop=True)
    df["Asset / Component"] = df["Asset / Component"].astype(str).str.strip()
    df["Asset Group"] = df["Asset Group"].astype(str).str.strip()

    # Condition may arrive as text ("C1") or already-blank; normalise to text.
    df["Condition"] = df["Condition"].apply(
        lambda v: str(v).strip().upper() if pd.notna(v) and str(v).strip() != "" else None
    )
    df["condition_numeric"] = df["Condition"].map(CONDITION_MAP)

    df["Base Life"] = pd.to_numeric(df["Base Life"], errors="coerce")
    df["has_base_life"] = df["Base Life"].notna() & (df["Base Life"] > 0)

    # Renewal Year: respect a supplied value; otherwise compute from construction year + base life.
    df["Renewal Year"] = pd.to_numeric(df.get("Renewal Year"), errors="coerce")
    computed_renewal = CONSTRUCTION_YEAR + df["Base Life"]
    df["Renewal Year"] = df["Renewal Year"].fillna(computed_renewal)
    df["renewal_year_is_calculated"] = df["Base Life"].notna() & df["Renewal Year"].notna()

    df["Package Cost"] = pd.to_numeric(df["Package Cost"], errors="coerce").fillna(0)
    df["Cost Status"] = df["Cost Status"].astype(str).str.strip()
    df["cost_confirmed"] = df["Cost Status"].str.lower() == "priced"

    return df


def compute_confidence(df: pd.DataFrame) -> pd.DataFrame:
    """SAMP-style confidence bucket, adapted from this file's 2-state Cost Status plus the base-life gap."""
    df = df.copy()

    def bucket(row):
        if not row["cost_confirmed"] or row["is_known_partial_cost"]:
            if not row["has_base_life"]:
                return "Not Ready \u2014 cost & lifecycle both incomplete"
            return "Partial \u2014 cost incomplete"
        if not row["has_base_life"]:
            return "Partial \u2014 lifecycle incomplete"
        return "Ready \u2014 cost & lifecycle confirmed"

    df["confidence"] = df.apply(bucket, axis=1)
    return df


def compute_lifecycle_stage(df: pd.DataFrame, view_year: int = CONSTRUCTION_YEAR) -> pd.DataFrame:
    """SAMP LCM: lifecycle stage per asset, based on proximity to renewal."""
    df = df.copy()
    df["years_to_renewal"] = df["Renewal Year"] - view_year
    df["life_fraction_used"] = np.where(
        df["has_base_life"], (view_year - CONSTRUCTION_YEAR) / df["Base Life"].replace(0, np.nan), np.nan
    ).clip(0, 2)

    def stage(row):
        if not row["has_base_life"]:
            return "Unassessed"
        if row["years_to_renewal"] < 0:
            return "Overdue"
        if row["years_to_renewal"] <= 2:
            return "Renewal Due"
        if row["life_fraction_used"] < 0.3:
            return "New"
        return "Mid-Life"

    df["lcm_stage"] = df.apply(stage, axis=1)
    return df


def compute_recommendation(df: pd.DataFrame) -> pd.DataFrame:
    """Rule-based recommendation, first match wins -- same style as the Pannawonica decision engine."""
    df = df.copy()

    def rec(row):
        if row["lcm_stage"] == "Overdue":
            return "Overdue \u2014 Replace Now"
        if row["lcm_stage"] == "Renewal Due":
            return "Renewal Due (\u22642 yrs)"
        if not row["cost_confirmed"] or row["is_known_partial_cost"]:
            return "Needs Cost Confirmation"
        if not row["has_base_life"]:
            return "Needs Base Life"
        if row["lcm_stage"] == "Mid-Life":
            return "Mid-Life \u2014 Monitor"
        return "New \u2014 Monitor"

    df["recommendation"] = df.apply(rec, axis=1)
    return df


def compute_escalated_cost(df: pd.DataFrame, escalation_rate: float, view_year: int = CONSTRUCTION_YEAR) -> pd.DataFrame:
    """Future nominal cost at renewal, compounding today's Package Cost forward by years_to_renewal."""
    df = df.copy()
    years = (df["Renewal Year"] - view_year).clip(lower=0)
    df["cost_at_renewal"] = np.where(
        df["has_base_life"], df["Package Cost"] * (1 + escalation_rate) ** years, np.nan
    )
    return df


def compute_tco(df: pd.DataFrame, discount_rate: float, escalation_rate: float,
                 view_year: int = CONSTRUCTION_YEAR) -> pd.DataFrame:
    """Present value of the future replacement cost, and an EAC of today's cost -- same CRF math as Pannawonica."""
    df = df.copy()
    years = (df["Renewal Year"] - view_year).clip(lower=0.1)
    df["pv_at_renewal"] = np.where(
        df["has_base_life"], df["cost_at_renewal"] / (1 + discount_rate) ** years, np.nan
    )
    n = df["Base Life"].replace(0, np.nan)
    crf = discount_rate * (1 + discount_rate) ** n / ((1 + discount_rate) ** n - 1)
    df["eac_today"] = np.where(df["has_base_life"], df["Package Cost"] * crf, np.nan)
    return df


def build_cycle_events(df: pd.DataFrame, horizon_end_year: int, escalation_rate: float,
                        view_year: int = CONSTRUCTION_YEAR, max_cycles: int = 15) -> pd.DataFrame:
    """
    Long-format table of every renewal event for every asset out to horizon_end_year,
    repeating every Base Life years (the '20yr refurb cost' vision point: a recurring
    package, not a one-off). Each cycle's cost compounds escalation from the base year.
    """
    rows = []
    valid = df[df["has_base_life"]]
    for _, r in valid.iterrows():
        cycle = 0
        event_year = r["Renewal Year"]
        while event_year <= horizon_end_year and cycle < max_cycles:
            years_out = event_year - view_year
            cost = r["Package Cost"] * (1 + escalation_rate) ** years_out
            rows.append({
                "cmp_id": r.name, "Asset Group": r["Asset Group"], "Asset / Component": r["Asset / Component"],
                "event_year": int(event_year), "cycle": cycle, "cost": cost, "base_life": r["Base Life"],
            })
            cycle += 1
            event_year += r["Base Life"]
    return pd.DataFrame(rows)


def run_jundu_scenario(events: pd.DataFrame, start_year: int, horizon_end_year: int,
                        annual_budget: float, budget_growth: float, deferral_escalation: float) -> pd.DataFrame:
    """
    Year-by-year budget-constrained simulation over the cycle-events table --
    same mechanic as Pannawonica's run_budget_scenario, adapted to repeating events.
    """
    events = events.copy()
    events["due_year"] = events["event_year"].clip(lower=start_year)
    events["remaining_cost"] = events["cost"]
    events["funded"] = False
    pending = events.copy()
    results = []
    budget = annual_budget

    for year in range(start_year, horizon_end_year + 1):
        due_now = pending[(~pending["funded"]) & (pending["due_year"] <= year)].copy()
        due_now = due_now.sort_values("remaining_cost")
        running = 0.0
        funded_idx = []
        for idx, row in due_now.iterrows():
            if running + row["remaining_cost"] <= budget:
                running += row["remaining_cost"]
                funded_idx.append(idx)
        pending.loc[funded_idx, "funded"] = True
        backlog = pending[(~pending["funded"]) & (pending["due_year"] <= year)]
        pending.loc[backlog.index, "remaining_cost"] *= (1 + deferral_escalation)

        results.append({
            "year": year, "budget": budget, "spend": running,
            "assets_funded": len(funded_idx), "assets_backlog": len(backlog),
            "backlog_value": backlog["remaining_cost"].sum(),
        })
        budget *= (1 + budget_growth)

    return pd.DataFrame(results)


def vision_point_status(df: pd.DataFrame) -> list:
    """Cross-check each vision-text item against the live data: exists? has base life? has confirmed cost?"""
    out = []
    seen = set()
    for name, pattern, vision_text in VISION_ITEMS:
        if name in seen:
            continue
        seen.add(name)
        matches = df[df["Asset / Component"].str.contains(pattern, case=False, na=False, regex=True)]
        if len(matches) == 0:
            status, detail = "Missing entirely", "No line item exists yet \u2014 needs adding from scratch."
        else:
            has_life = matches["has_base_life"].any()
            has_cost = matches["cost_confirmed"].all() and not matches["is_known_partial_cost"].any()
            if has_life and has_cost:
                status, detail = "Ready", f"{len(matches)} row(s), base life and cost both confirmed."
            elif has_life:
                status, detail = "Cost incomplete", f"{len(matches)} row(s), base life set but cost needs confirmation."
            else:
                status, detail = "Needs base life", f"{len(matches)} row(s) exist, no base life set yet."
        out.append({"item": name, "vision_text": vision_text, "status": status, "detail": detail})
    return out


def generate_jundu_pptx(scope_label: str, kpis: dict, confidence_summary: pd.DataFrame,
                         cost_engine_totals: dict, rec_summary: pd.DataFrame, vision_status: list,
                         scenario_results: pd.DataFrame, params: dict) -> bytes:
    """
    SAMP-format deck for the Jundunmunnah refurbishment package, mirroring the section structure
    of the SAMP Integrated Lifecycle Investment Planning concept deck: Purpose, Scope, Inputs,
    Cost Engine, Decision Logic, Scenarios, Governance. Built with python-pptx (pure Python) so
    it can run inside the deployed Streamlit app, not just this sandbox.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE

    NAVY = RGBColor(0x2B, 0x37, 0x97)
    NAVY_DARK = RGBColor(0x18, 0x1F, 0x5C)
    RED = RGBColor(0xED, 0x1C, 0x24)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    MUTED = RGBColor(0x8A, 0x90, 0xC7)
    LIGHT = RGBColor(0xF0, 0xF1, 0xF9)
    GOOD = RGBColor(0x2E, 0xB8, 0x6B)
    WARN = RGBColor(0xD9, 0xA6, 0x2A)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def add_slide():
        return prs.slides.add_slide(blank)

    def fill_bg(slide, color):
        rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        rect.fill.solid()
        rect.fill.fore_color.rgb = color
        rect.line.fill.background()
        rect.shadow.inherit = False
        slide.shapes._spTree.remove(rect._element)
        slide.shapes._spTree.insert(2, rect._element)
        return rect

    def add_text(slide, x, y, w, h, text, size=18, color=NAVY_DARK, bold=False, align=PP_ALIGN.LEFT,
                 font="Calibri", anchor=None):
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = box.text_frame
        tf.word_wrap = True
        if anchor:
            tf.vertical_anchor = anchor
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = font
        return box

    def running_header(slide, title):
        add_text(slide, 0.5, 0.28, 8, 0.35, "IFM SERVICES STRATEGIC ASSET MANAGEMENT PROGRAM",
                  size=10, color=MUTED, bold=True)
        add_text(slide, 0.5, 0.62, 10, 0.5, title, size=24, color=NAVY_DARK, bold=True)
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1.18), Inches(1.1), Pt(3))
        line.fill.solid()
        line.fill.fore_color.rgb = RED
        line.line.fill.background()
        line.shadow.inherit = False

    def kpi_card(slide, x, y, w, h, label, value, color=NAVY):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        card.fill.solid()
        card.fill.fore_color.rgb = LIGHT
        card.line.color.rgb = RGBColor(0xDA, 0xDC, 0xE8)
        card.line.width = Pt(0.75)
        card.shadow.inherit = False
        try:
            card.adjustments[0] = 0.08
        except Exception:
            pass
        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_left = Pt(10); tf.margin_right = Pt(10); tf.margin_top = Pt(8); tf.margin_bottom = Pt(8)
        p0 = tf.paragraphs[0]
        p0.alignment = PP_ALIGN.LEFT
        r0 = p0.add_run(); r0.text = value; r0.font.size = Pt(24); r0.font.bold = True; r0.font.color.rgb = color
        r0.font.name = "Calibri"
        p1 = tf.add_paragraph()
        p1.alignment = PP_ALIGN.LEFT
        r1 = p1.add_run(); r1.text = label; r1.font.size = Pt(11); r1.font.color.rgb = NAVY_DARK
        r1.font.name = "Calibri"

    # ---------------------------------------------------------- SLIDE 1: TITLE
    s = add_slide()
    fill_bg(s, NAVY_DARK)
    try:
        s.shapes.add_picture("assets/logo.png", Inches(0.6), Inches(0.5), height=Inches(0.5))
    except Exception:
        pass
    add_text(s, 0.6, 2.6, 11, 1.0, "Jundunmunnah Refurbishment", size=40, color=WHITE, bold=True)
    add_text(s, 0.6, 3.5, 11, 0.6, "Lifecycle & Investment Model \u2014 SAMP Framework Applied", size=20, color=MUTED)
    add_text(s, 0.6, 6.5, 11, 0.4, f"Scope: {scope_label}", size=12, color=MUTED)
    line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(2.35), Inches(1.4), Pt(4))
    line.fill.solid(); line.fill.fore_color.rgb = RED; line.line.fill.background(); line.shadow.inherit = False

    # ---------------------------------------------------------- SLIDE 2: PURPOSE
    s = add_slide()
    fill_bg(s, WHITE)
    running_header(s, "Purpose")
    add_text(s, 0.5, 1.5, 11.5, 0.6,
              "Turn the Jundunmunnah refurbishment package into a governed investment decision",
              size=16, color=NAVY_DARK, bold=True)
    steps = [("EVIDENCE", "168 priced asset lines from the refurb scope"),
             ("ASSESS", "Base life, condition, and confidence per asset"),
             ("MODEL", "Cost engine, escalation, TCO/NPV"),
             ("DECIDE", "Rule-based renewal recommendations"),
             ("GOVERN", "Scenario-tested, assumptions visible")]
    col_w = 2.2
    for i, (label, desc) in enumerate(steps):
        x = 0.5 + i * (col_w + 0.15)
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.6), Inches(col_w), Inches(2.0))
        card.fill.solid(); card.fill.fore_color.rgb = NAVY if i % 2 == 0 else NAVY_DARK
        card.line.fill.background(); card.shadow.inherit = False
        tf = card.text_frame; tf.word_wrap = True
        tf.margin_left = Pt(10); tf.margin_right = Pt(10); tf.margin_top = Pt(14)
        p0 = tf.paragraphs[0]; p0.alignment = PP_ALIGN.LEFT
        r0 = p0.add_run(); r0.text = label; r0.font.bold = True; r0.font.size = Pt(14); r0.font.color.rgb = WHITE
        p1 = tf.add_paragraph()
        r1 = p1.add_run(); r1.text = desc; r1.font.size = Pt(11); r1.font.color.rgb = RGBColor(0xC7, 0xCC, 0xEE)
    add_text(s, 0.5, 5.0, 11.5, 1.2,
              "Every figure in this deck traces to a stated assumption \u2014 escalation rate, discount rate, "
              "or a rule threshold \u2014 consistent with SAMP's own governing principle: transparent "
              "recommendations and confidence levels, with funding decisions remaining governed.",
              size=13, color=NAVY_DARK)

    # ---------------------------------------------------------- SLIDE 3: SCOPE / KPIs
    s = add_slide()
    fill_bg(s, WHITE)
    running_header(s, "Scope \u2014 at a glance")
    kx = 0.5
    for i, (label, val) in enumerate(kpis.items()):
        kpi_card(s, kx + i * 2.85, 1.6, 2.7, 1.4, label, val, color=NAVY if i % 2 == 0 else RED)
    add_text(s, 0.5, 3.3, 11.5, 0.4, "SAMP scope mapping for this dataset", size=14, color=NAVY_DARK, bold=True)
    scope_rows = [
        ("CAPEX", "Covered \u2014 full asset-level replacement package costs", GOOD),
        ("OPEX", "Not yet available \u2014 no PM/maintenance data in this file", WARN),
        ("LCCM", "Partial \u2014 possible once base life is supplied per asset", WARN),
        ("LCM / TCO", "Calculated where base life exists (escalation, NPV, EAC)", GOOD),
    ]
    for i, (label, desc, color) in enumerate(scope_rows):
        y = 3.8 + i * 0.62
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.5), Inches(y + 0.05), Inches(0.18), Inches(0.18))
        dot.fill.solid(); dot.fill.fore_color.rgb = color; dot.line.fill.background(); dot.shadow.inherit = False
        add_text(s, 0.85, y, 1.6, 0.4, label, size=13, color=NAVY_DARK, bold=True)
        add_text(s, 2.5, y, 9.3, 0.4, desc, size=12, color=NAVY_DARK)

    # ---------------------------------------------------------- SLIDE 4: INPUTS / CONFIDENCE (native chart)
    s = add_slide()
    fill_bg(s, WHITE)
    running_header(s, "Inputs \u2014 data confidence")
    chart_data = CategoryChartData()
    chart_data.categories = list(confidence_summary.index)
    chart_data.add_series("Assets", [int(v) for v in confidence_summary["count"]])
    gframe = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.5), Inches(8.0), Inches(5.2), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.number_format = '#,##0'
    plot.data_labels.number_format_is_linked = False
    try:
        series = plot.series[0]
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = NAVY
    except Exception:
        pass
    add_text(s, 8.9, 1.6, 3.9, 5.0,
              "Confidence combines two states from the source file: whether cost is Priced, and "
              "whether Base Life has been supplied. Both must be true for an asset to be forecast-ready.",
              size=12, color=NAVY_DARK)

    # ---------------------------------------------------------- SLIDE 5: COST ENGINE (native chart)
    s = add_slide()
    fill_bg(s, WHITE)
    running_header(s, "Cost engine \u2014 today's dollars")
    ce_items = [(k, v) for k, v in cost_engine_totals.items() if k != "Total package cost"]
    chart_data = CategoryChartData()
    chart_data.categories = [k for k, v in ce_items]
    chart_data.add_series("$", [round(v) for k, v in ce_items])
    gframe = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.5), Inches(7.5), Inches(4.6), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.number_format = '$#,##0,,"M"'
    plot.data_labels.number_format_is_linked = False
    chart.value_axis.tick_labels.number_format = '$#,##0,,"M"'
    chart.value_axis.tick_labels.number_format_is_linked = False
    try:
        plot.series[0].format.fill.solid()
        plot.series[0].format.fill.fore_color.rgb = RED
    except Exception:
        pass
    kpi_card(s, 8.4, 1.6, 4.3, 1.3, "Total package cost", money(cost_engine_totals["Total package cost"]), color=NAVY)
    add_text(s, 8.4, 3.2, 4.3, 3.0,
              "SAMP's cost engine also names Delivery, Project, and Disposal steps. These are deliberately "
              "excluded from this asset register per the source workbook's own scope notes and tracked "
              "separately as project on-costs, not asset lines.",
              size=12, color=NAVY_DARK)

    # ---------------------------------------------------------- SLIDE 6: DECISION LOGIC (native chart)
    s = add_slide()
    fill_bg(s, WHITE)
    running_header(s, "Decision logic \u2014 recommendations")
    chart_data = CategoryChartData()
    chart_data.categories = list(rec_summary.index)
    chart_data.add_series("Assets", [int(v) for v in rec_summary["count"]])
    gframe = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.5), Inches(8.0), Inches(5.2), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.number_format = '#,##0'
    plot.data_labels.number_format_is_linked = False
    try:
        plot.series[0].format.fill.solid()
        plot.series[0].format.fill.fore_color.rgb = NAVY_DARK
    except Exception:
        pass
    add_text(s, 8.9, 1.6, 3.9, 5.0,
              "Each asset is classified by a fixed rule, evaluated in order: overdue first, then due within "
              "2 years, then cost/lifecycle data gaps, then monitored by life stage. No machine learning "
              "\u2014 every category traces to a visible threshold.",
              size=12, color=NAVY_DARK)

    # ---------------------------------------------------------- SLIDE 7: SCENARIOS (native chart)
    s = add_slide()
    fill_bg(s, WHITE)
    running_header(s, "Scenarios \u2014 budget simulation")
    chart_data = CategoryChartData()
    chart_data.categories = [str(int(y)) for y in scenario_results["year"]]
    chart_data.add_series("Unfunded backlog ($)", [round(v) for v in scenario_results["backlog_value"]])
    gframe = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(0.6), Inches(1.5), Inches(11.5), Inches(4.6), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    chart.value_axis.tick_labels.number_format = '$#,##0,,"M"'
    chart.value_axis.tick_labels.number_format_is_linked = False
    try:
        chart.series[0].format.line.color.rgb = RED
        chart.series[0].format.line.width = Pt(2.5)
    except Exception:
        pass
    add_text(s, 0.6, 6.3, 11.5, 0.9,
              f"Annual budget {money(params['budget'])}, growing {params['growth']*100:.0f}%/yr; unfunded "
              f"items escalate {params['escalation']*100:.0f}%/yr while deferred; each asset repeats every "
              f"own base life through {params['horizon']}.",
              size=12, color=NAVY_DARK)

    # ---------------------------------------------------------- SLIDE 8: VISION TRACKER
    s = add_slide()
    fill_bg(s, WHITE)
    running_header(s, "Vision-text item tracker")
    rows = len(vision_status) + 1
    table_shape = s.shapes.add_table(rows, 3, Inches(0.5), Inches(1.5), Inches(12.3), Inches(5.0))
    table = table_shape.table
    table.columns[0].width = Inches(2.8)
    table.columns[1].width = Inches(6.5)
    table.columns[2].width = Inches(3.0)
    headers = ["Item", "Vision statement", "Status"]
    for c, h in enumerate(headers):
        cell = table.cell(0, c)
        cell.text = h
        cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.color.rgb = WHITE; r.font.bold = True; r.font.size = Pt(12)
    status_color = {"Ready": GOOD, "Cost incomplete": WARN, "Needs base life": WARN, "Missing entirely": RED}
    for i, v in enumerate(vision_status, start=1):
        table.cell(i, 0).text = v["item"]
        table.cell(i, 1).text = v["vision_text"]
        table.cell(i, 2).text = v["status"]
        for c in range(3):
            cell = table.cell(i, c)
            cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT if i % 2 == 0 else WHITE
            for p in cell.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(11)
                    r.font.color.rgb = NAVY_DARK
        status_cell = table.cell(i, 2)
        for p in status_cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.color.rgb = status_color.get(v["status"], NAVY_DARK)

    # ---------------------------------------------------------- SLIDE 9: GOVERNANCE / CLOSING
    s = add_slide()
    fill_bg(s, NAVY_DARK)
    add_text(s, 0.6, 0.8, 11.5, 0.8, "Governance", size=28, color=WHITE, bold=True)
    add_text(s, 0.6, 1.8, 11.5, 0.7,
              "Every number here is a stated-assumption calculation, not a prediction.", size=16, color=MUTED)
    principles = [
        "Base life is supplied by the asset owner, not inferred automatically \u2014 category averages "
        "across dissimilar asset types were tested and rejected as unreliable.",
        "Escalation and discount rates are visible sliders, not fixed constants.",
        "Confidence flags surface every cost or lifecycle gap rather than hiding it behind a forecast.",
        "This is a rules-based decision-support model. It is not machine learning: no historical "
        "outcomes exist yet for a model to learn from \u2014 every asset here is brand new.",
    ]
    for i, txt in enumerate(principles):
        y = 2.7 + i * 0.95
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.6), Inches(y + 0.05), Inches(0.15), Inches(0.15))
        dot.fill.solid(); dot.fill.fore_color.rgb = RED; dot.line.fill.background(); dot.shadow.inherit = False
        add_text(s, 0.95, y - 0.1, 11.5, 0.9, txt, size=13, color=WHITE)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
def generate_jundu_pdf_report(scope_label: str, kpis: dict, confidence_summary: pd.DataFrame,
                               rec_summary: pd.DataFrame, vision_status: list, cost_engine_totals: dict,
                               scenario_results: pd.DataFrame, params: dict) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                     Image as RLImage, HRFlowable, PageBreak)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from datetime import datetime

    navy = rl_colors.HexColor("#2B3797")
    navy_dark = rl_colors.HexColor("#181F5C")
    muted = rl_colors.HexColor("#5B5F73")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleJ", parent=styles["Title"], textColor=navy, fontSize=20)
    h1 = ParagraphStyle("H1J", parent=styles["Heading1"], textColor=navy, fontSize=14, spaceBefore=14, spaceAfter=7)
    h2 = ParagraphStyle("H2J", parent=styles["Heading2"], textColor=navy_dark, fontSize=11.5, spaceBefore=10, spaceAfter=5)
    body = ParagraphStyle("BodyJ", parent=styles["Normal"], fontSize=9.6, leading=14)
    small = ParagraphStyle("SmallJ", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=muted)
    small_white = ParagraphStyle("SmallWJ", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=rl_colors.white)

    def styled_table(rows, col_widths, header_bg=navy):
        data = [[Paragraph(f"<b>{c}</b>", small_white) for c in rows[0]]] + \
               [[Paragraph(str(c), small) for c in r] for r in rows[1:]]
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F5F6FA")]),
            ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#E4E4EC")),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ]))
        return t

    story = []
    try:
        story.append(RLImage("assets/logo.png", width=28 * mm, height=9.4 * mm))
        story.append(Spacer(1, 6))
    except Exception:
        pass
    story.append(Paragraph("Jundunmunnah Refurbishment", title_style))
    story.append(Paragraph("Lifecycle &amp; Investment Model \u2014 SAMP Alignment Report", h2))
    story.append(Paragraph(f"Scope: {scope_label}", small))
    story.append(Paragraph(f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}", small))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "This report applies the SAMP Integrated Lifecycle Investment Planning framework to the "
        "Jundunmunnah refurbishment package. All figures are transparent formula-based calculations "
        "(escalation, capital recovery factor, rule-based staging) from stated assumptions below \u2014 "
        "not machine learning or predictive modelling, consistent with the rest of FM Asset Excellence.", body,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("At a glance", h1))
    kt = Table([[k, v] for k, v in kpis.items()], colWidths=[95 * mm, 75 * mm])
    kt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("TEXTCOLOR", (0, 0), (0, -1), muted),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#E4E4EC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(kt)

    story.append(Paragraph("SAMP Inputs: data confidence", h1))
    conf_rows = [["Confidence", "Assets", "Package cost"]] + [
        [i, f"{int(r['count']):,}", money(r["cost"])] for i, r in confidence_summary.iterrows()
    ]
    story.append(styled_table(conf_rows, [90 * mm, 35 * mm, 45 * mm]))

    story.append(Paragraph("SAMP Cost Engine: today's dollars", h1))
    ce_rows = [["Component", "Amount"]] + [[k, money(v)] for k, v in cost_engine_totals.items()]
    story.append(styled_table(ce_rows, [95 * mm, 75 * mm], header_bg=navy_dark))
    story.append(Paragraph(
        "Delivery, Project, and Disposal cost steps in SAMP's cost engine are deliberately excluded from "
        "this asset register per the source workbook's own scope notes (treated as separate project on-costs).",
        small,
    ))

    story.append(PageBreak())
    story.append(Paragraph("SAMP Decision Logic: recommendations", h1))
    rec_rows = [["Recommendation", "Assets", "Package cost"]] + [
        [i, f"{int(r['count']):,}", money(r["cost"])] for i, r in rec_summary.iterrows()
    ]
    story.append(styled_table(rec_rows, [90 * mm, 35 * mm, 45 * mm]))

    story.append(Paragraph("Vision-text item tracker", h1))
    v_rows = [["Item", "Vision statement", "Status"]] + [
        [v["item"], v["vision_text"], v["status"]] for v in vision_status
    ]
    story.append(styled_table(v_rows, [40 * mm, 90 * mm, 40 * mm]))

    story.append(Paragraph("SAMP Scenarios: budget simulation", h1))
    story.append(Paragraph(
        f"Annual budget {money(params['budget'])}, growing {params['growth']*100:.0f}%/yr; unfunded items "
        f"escalate {params['escalation']*100:.0f}%/yr while deferred; repeating every asset's own base life "
        f"out to {params['horizon']}.", body,
    ))
    fig, ax = plt.subplots(figsize=(6.6, 2.8), dpi=160)
    ax.plot(scenario_results["year"], scenario_results["backlog_value"] / 1000, color="#5A69D6", linewidth=2.3)
    ax.fill_between(scenario_results["year"], 0, scenario_results["backlog_value"] / 1000, color="#5A69D6", alpha=0.15)
    ax.set_ylabel("Unfunded backlog ($K)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    story.append(RLImage(buf, width=160 * mm, height=68 * mm))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.6, color=rl_colors.HexColor("#DADCE8")))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Figures are model estimates from stated assumptions, not a committed capital plan or a guarantee "
        "of future cost. Per SAMP's own governance principle: outputs provide transparent recommendations "
        "and confidence levels; funding decisions remain governed.", small,
    ))

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    doc.build(story)
    return out.getvalue()
