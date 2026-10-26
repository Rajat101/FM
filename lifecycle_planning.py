"""Lifecycle planning engine for the 'Lifecycle Planning' pages (15-24).

Adds a second, independent view of every component's lifecycle -- the
*standard-life* view (construction year + average life from the Asset Life
reference file) -- alongside the *system forecast* the source system exports.
Neither is treated as the truth: every page can switch between the two, and
the gap between them is surfaced as an insight in its own right.

This module only READS from common.py (load_data, helpers). It never changes
the data the existing pages use.
"""
import io
import math
import re

import numpy as np
import pandas as pd
import streamlit as st

from common import CURRENT_YEAR, YEARS, YEARS_INT, CONDITION_NUM

CY = CURRENT_YEAR
BASES = {"System forecast": "sys", "Standard life": "std"}
STATUS_ORDER = ["Overdue", "Approaching EOL", "Healthy", "Unknown"]
STATUS_COLORS = {"Overdue": "#ED1C24", "Approaching EOL": "#F5A623", "Healthy": "#2FBF7A", "Unknown": "#7A8B99"}
CRIT_ORDER = ["Critical", "High", "Medium", "Low"]
CRIT_COLORS = {"Critical": "#ED1C24", "High": "#F5A623", "Medium": "#8AA0F0", "Low": "#2FBF7A"}
STD_YEARS = [f"std_{y}" for y in YEARS_INT]

# source-system component groups -> Asset Life taxonomy groups
GROUP_MAP = {
    "exterior wks, sundries": "Exterior Works & Sundries",
    "roads": "Exterior Works & Sundries",
    "fpe-electrical services": "Electrical Services",
    "fpe-fire services": "Fire Services",
    "fpe-mechanical services": "Mechanical Services",
    "fpe-water services": "Water Services",
    "fpe-wastewater": "FPE-Wastewater",
    "ffe-other equipment": "Equipment",
    "ffe-appliances": "Appliance",
    "external fabric": "External Fabric",
    "interior finishes": "Interior Finishes",
    "structure": "Structure",
    "special": "Special",
    "asbestos sample": "Asbestos Sample",
}

KEEP_COLS = [
    "cmp_id", "mnt_id", "source_site", "source_file", "area", "portfolio", "site", "property", "property code",
    "property_type", "comp. group", "comp. type", "component", "location", "qty", "unit", "rate",
    "calc_method", "exp_type", "Condition", "condition_numeric", "consequence", "safety", "cost", "deferred",
    "base_life", "cmp_construction_year", "cmp_survey_year", "next_renewal_year", "best_estimate_year",
    "data_confidence", "data_confidence_score", "construction_year_uniform_property", "survey_missing",
    "condition_reset_risk", "has_fault_note", "has_replace_override", "has_maintenance_record", "comment",
]


# =============================================================================== Asset Life reference
def _key(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _key_loose(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def parse_asset_life(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Reads the Asset Life file (xlsx or csv), finding the header row and the
    name / group / life columns by name, wherever they sit."""
    if filename.lower().endswith(".csv"):
        raw = pd.read_csv(io.BytesIO(file_bytes), header=None, encoding="utf-8-sig")
    else:
        raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, header=None)
    header_row = None
    for i in range(min(25, len(raw))):
        vals = [str(v).strip().lower() for v in raw.iloc[i].tolist()]
        if any("asset name" in v or v == "name" for v in vals) and any("life" in v for v in vals):
            header_row = i
            break
    if header_row is None:
        raise ValueError("Couldn't find a header row with 'Asset Name' and an 'Average Life' column.")
    ref = raw.iloc[header_row + 1:].copy()
    ref.columns = [str(c).strip() for c in raw.iloc[header_row].tolist()]
    cols = {c.lower(): c for c in ref.columns}
    name_col = next(cols[c] for c in cols if "asset name" in c or c == "name")
    life_col = next(cols[c] for c in cols if "life" in c)
    group_col = next((cols[c] for c in cols if c == "group" or (c.endswith("group") and "id" not in c)), None)
    out = pd.DataFrame({
        "asset_name": ref[name_col].astype(str).str.strip(),
        "taxonomy_group": ref[group_col].astype(str).str.strip() if group_col else "",
        "avg_life": pd.to_numeric(ref[life_col], errors="coerce"),
    })
    out = out[out["asset_name"].ne("") & out["asset_name"].ne("nan")].drop_duplicates("asset_name")
    return out.reset_index(drop=True)


def asset_life_sidebar():
    """Sidebar uploader for the Asset Life reference. Kept in session memory only."""
    ss = st.session_state
    st.sidebar.markdown("### Asset Life reference")
    if "lp_asset_life" in ss:
        st.sidebar.caption(f"Loaded: **{ss.get('lp_asset_life_name', 'Asset Life')}** "
                           f"({len(ss['lp_asset_life']):,} asset types)")
        if st.sidebar.button("Change Asset Life file", key="lp_change_life"):
            for k in ["lp_asset_life", "lp_asset_life_name", "lp_core_cache"]:
                ss.pop(k, None)
            st.rerun()
        return ss["lp_asset_life"]
    up = st.sidebar.file_uploader("Upload Asset Life file (.xlsx or .csv)", type=["xlsx", "csv"],
                                  key="lp_life_uploader",
                                  help="Columns needed: Asset Name, Group, Average Life (Years).")
    if up is None:
        st.sidebar.caption("Without it, only the System forecast view is available.")
        return None
    try:
        ref = parse_asset_life(up.getvalue(), up.name)
    except Exception as e:
        st.sidebar.error(f"Couldn't read that file: {e}")
        return None
    ss["lp_asset_life"] = ref
    ss["lp_asset_life_name"] = up.name
    ss.pop("lp_core_cache", None)
    st.rerun()


def _map_group(g: str, tax_groups: set) -> str:
    k = _key(g)
    if k in GROUP_MAP:
        return GROUP_MAP[k]
    stripped = re.sub(r"^(fpe|ffe)-", "", k)
    for tg in tax_groups:
        if _key(tg) in (k, stripped):
            return tg
    return ""


def attach_avg_life(core: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    if ref is None or len(ref) == 0:
        core["avg_life"] = np.nan
        core["avg_life_source"] = "No reference loaded"
        core["taxonomy_group"] = ""
        return core
    r = ref.dropna(subset=["avg_life"])
    exact = dict(zip(r["asset_name"].map(_key), r["avg_life"]))
    loose = dict(zip(r["asset_name"].map(_key_loose), r["avg_life"]))
    tax_of = dict(zip(ref["asset_name"].map(_key), ref["taxonomy_group"]))
    group_median = r.groupby("taxonomy_group")["avg_life"].median().to_dict()
    tax_groups = set(ref["taxonomy_group"].dropna())

    comp = core["component"].astype(str)
    uniq = pd.Series(comp.unique())
    k1, k2 = uniq.map(_key), uniq.map(_key_loose)
    life_exact = k1.map(exact)
    life_loose = k2.map(loose)
    life_u = life_exact.fillna(life_loose)
    src_u = np.where(life_exact.notna(), "Exact match", np.where(life_loose.notna(), "Name match (loose)", ""))
    lut_life = dict(zip(uniq, life_u))
    lut_src = dict(zip(uniq, src_u))
    lut_tax = dict(zip(uniq, k1.map(tax_of)))

    core["avg_life"] = comp.map(lut_life)
    core["avg_life_source"] = comp.map(lut_src)
    grp_tax = core["comp. group"].astype(str).map(
        {g: _map_group(g, tax_groups) for g in core["comp. group"].astype(str).unique()})
    core["taxonomy_group"] = comp.map(lut_tax).fillna(grp_tax).replace("", np.nan).fillna(grp_tax)
    fallback = grp_tax.map(group_median)
    need = core["avg_life"].isna()
    core.loc[need & fallback.notna(), "avg_life_source"] = "Group median"
    core.loc[need, "avg_life"] = fallback[need]
    core.loc[core["avg_life"].isna(), "avg_life_source"] = "Not found"
    return core


# =============================================================================== settings (shared across pages)
def _persist(widget_key, store_key):
    st.session_state[store_key] = st.session_state[widget_key]


def settings_sidebar(has_ref: bool) -> dict:
    """Life basis + EOL threshold, persisted across every Lifecycle Planning page."""
    ss = st.session_state
    ss.setdefault("lp_basis", "System forecast")
    ss.setdefault("lp_approach_pct", 80)
    if not has_ref:
        ss["lp_basis"] = "System forecast"
    st.sidebar.markdown("### Lifecycle settings")
    ss["_w_lp_basis"] = ss["lp_basis"]
    st.sidebar.radio(
        "Life basis", list(BASES), key="_w_lp_basis", on_change=_persist, args=("_w_lp_basis", "lp_basis"),
        disabled=not has_ref,
        help="System forecast = the source system's own renewal dates. Standard life = construction year "
             "+ average life from the Asset Life file. Upload the Asset Life file to enable it.",
    )
    ss["_w_lp_approach"] = ss["lp_approach_pct"]
    st.sidebar.slider(
        "'Approaching EOL' from % of life used", 50, 95, step=5, key="_w_lp_approach",
        on_change=_persist, args=("_w_lp_approach", "lp_approach_pct"),
    )
    return {"basis": BASES[ss["lp_basis"]], "basis_label": ss["lp_basis"], "approach": ss["lp_approach_pct"] / 100}


# =============================================================================== core lifecycle calculations
def _life_band(consumed: pd.Series) -> pd.Series:
    band = pd.cut(consumed, bins=[-np.inf, 0.5, 0.8, 1.0, 1.5, np.inf], labels=[1, 2, 3, 4, 5])
    return band.astype(float)


def _status(rul, consumed, valid, approach):
    return np.select(
        [~valid, rul < 0, consumed >= approach],
        ["Unknown", "Overdue", "Approaching EOL"],
        default="Healthy",
    )


def build_core(df: pd.DataFrame, ref, approach: float) -> pd.DataFrame:
    cols = [c for c in KEEP_COLS if c in df.columns] + [y for y in YEARS if y in df.columns]
    core = df[cols].copy()
    if "source_site" not in core.columns:
        core["source_site"] = "Workbook"
    core = attach_avg_life(core, ref)

    cy = pd.to_numeric(core["cmp_construction_year"], errors="coerce")
    core["construction_year_valid"] = cy.between(1900, CY)
    core["asset_age"] = np.where(core["construction_year_valid"], CY - cy, np.nan)
    bl = pd.to_numeric(core["base_life"], errors="coerce")
    core["base_life_valid"] = bl.between(1, 150)
    core["sys_life"] = bl.where(core["base_life_valid"])
    core["std_life"] = core["avg_life"].where(core["avg_life"].between(1, 150))

    # --- per-basis end-of-life and status
    core["sys_due"] = pd.to_numeric(core["best_estimate_year"], errors="coerce")
    core["std_due"] = cy + core["std_life"]
    for b in ("sys", "std"):
        life, due = core[f"{b}_life"], core[f"{b}_due"]
        valid = core["construction_year_valid"] & life.notna() & due.notna()
        rul = due - CY
        if b == "std":
            consumed = core["asset_age"] / life
        else:  # what the system's own date implies about life used
            consumed = (1 - rul / life).clip(lower=0)
        core[f"{b}_valid"] = valid
        core[f"{b}_rul"] = rul.where(valid)
        core[f"{b}_consumed"] = consumed.where(valid)
        core[f"{b}_status"] = _status(rul, consumed, valid, approach)
        core[f"{b}_years_overdue"] = (-rul).clip(lower=0).where(valid, 0)
        core[f"{b}_planned_year"] = due.clip(lower=CY).where(valid)

    core["age_vs_avg_life"] = core["asset_age"] / core["std_life"]
    core["forecast_gap_years"] = core["sys_due"] - core["std_due"]
    core["life_gap_years"] = core["sys_life"] - core["std_life"]

    # --- criticality and lifecycle risk
    cons = pd.to_numeric(core["consequence"], errors="coerce").fillna(3).clip(1, 5)
    saf = pd.to_numeric(core["safety"], errors="coerce").fillna(3).clip(1, 5)
    crit = cons * saf
    core["criticality"] = crit
    core["criticality_score"] = (crit / 25 * 100).round(1)
    core["criticality_tier"] = pd.cut(crit, bins=[0, 3, 8, 15, 25], labels=["Low", "Medium", "High", "Critical"]).astype(str)
    cond = core["condition_numeric"].astype(float).fillna(3)
    for b in ("sys", "std"):
        band = _life_band(core[f"{b}_consumed"]).fillna(cond)
        likelihood = np.maximum(cond, band)
        core[f"{b}_likelihood"] = likelihood
        core[f"{b}_risk"] = (likelihood * crit / 125 * 100).round(1)

    # --- survey age
    sy = pd.to_numeric(core["cmp_survey_year"], errors="coerce").fillna(0)
    core["survey_age"] = np.where(sy > 0, CY - sy, np.nan)

    # --- completeness (6 checks)
    checks = pd.DataFrame({
        "construction_year": core["construction_year_valid"] & ~core["construction_year_uniform_property"].fillna(False),
        "base_life": core["base_life_valid"],
        "avg_life": core["avg_life_source"].isin(["Exact match", "Name match (loose)"]),
        "survey": sy > 0,
        "cost": pd.to_numeric(core["cost"], errors="coerce").fillna(0) > 0,
        "condition": core["Condition"].isin(CONDITION_NUM.keys()),
    })
    scored = checks if ref is not None else checks.drop(columns=["avg_life"])  # no reference = not applicable
    core["completeness_score"] = (scored.mean(axis=1) * 100).round(0)
    for c in checks.columns:
        core[f"has_{c}"] = checks[c]

    # --- next action per basis
    for b in ("sys", "std"):
        st_, tier = core[f"{b}_status"], core["criticality_tier"]
        hi = tier.isin(["Critical", "High"])
        stale = core["survey_age"].isna() | (core["survey_age"] > 5)
        big_gap = core["forecast_gap_years"].abs() >= 10
        core[f"{b}_next_action"] = np.select(
            [st_.eq("Unknown"),
             st_.eq("Overdue") & hi,
             st_.eq("Overdue"),
             st_.eq("Approaching EOL") & hi,
             st_.eq("Approaching EOL"),
             big_gap & hi,
             stale & hi],
            ["Verify data / re-survey",
             "Replace now",
             "Plan replacement or justify deferral",
             "Inspect and budget replacement",
             "Monitor; include in forward plan",
             "Validate life assumption",
             "Inspect (survey out of date)"],
            default="Maintain",
        )

    # --- standard-life cashflows, built the same way the system builds its own:
    #     replacement cost in the due year, repeated every life-cycle within the window;
    #     anything due before the window goes to backlog (the system's 'deferred').
    due = core["std_due"].to_numpy(dtype=float)
    life = np.round(core["std_life"].to_numpy(dtype=float))
    cost = pd.to_numeric(core["cost"], errors="coerce").fillna(0).to_numpy(dtype=float)
    ok = core["std_valid"].to_numpy() & (life >= 1)
    for y, col in zip(YEARS_INT, STD_YEARS):
        k = (y - due)
        hit = ok & (k >= 0) & (np.mod(np.where(ok, k, 0), np.where(ok, life, 1)) == 0)
        core[col] = np.where(hit, cost, 0).astype("float32")
    core["std_backlog"] = np.where(ok & (due < CY), cost, 0.0)
    core["sys_backlog"] = pd.to_numeric(core.get("deferred", 0), errors="coerce").fillna(0)
    return core


def get_core(df: pd.DataFrame, ref, settings: dict) -> pd.DataFrame:
    """Builds the enriched table once per session (per data + reference + threshold)
    and returns it with the active basis applied to generic column names."""
    ss = st.session_state
    key = (id(df), len(df), id(ref) if ref is not None else None, settings["approach"])
    cache = ss.get("lp_core_cache")
    if not cache or cache[0] != key:
        with st.spinner("Calculating lifecycle metrics..."):
            core = build_core(df, ref, settings["approach"])
        ss["lp_core_cache"] = (key, core)
    else:
        core = cache[1]
    return apply_basis(core, settings["basis"])


GENERIC = ["life", "due", "rul", "consumed", "status", "years_overdue", "planned_year", "likelihood", "risk",
           "next_action", "backlog", "valid"]


def apply_basis(core: pd.DataFrame, b: str) -> pd.DataFrame:
    out = core.copy(deep=False)
    for g in GENERIC:
        out[g] = core[f"{b}_{g}"]
    out.attrs["basis"] = b
    return out


def year_cols(b: str) -> list:
    return YEARS if b == "sys" else STD_YEARS


def annual(d: pd.DataFrame, b: str, by: str = None) -> pd.DataFrame:
    """Annual replacement cost (rows = years) optionally split by a column."""
    cols = year_cols(b)
    if by is None:
        s = d[cols].sum()
        s.index = YEARS_INT
        return s.to_frame("cost")
    g = d.groupby(by, observed=True)[cols].sum().T
    g.index = YEARS_INT
    return g


def annual_counts(d: pd.DataFrame, b: str) -> pd.Series:
    s = (d[year_cols(b)] > 0).sum()
    s.index = YEARS_INT
    return s


def top_n_other(d: pd.DataFrame, col: str, value: str, n: int = 7) -> pd.Series:
    top = d.groupby(col)[value].sum().nlargest(n).index
    return d[col].where(d[col].isin(top), "Other")


# =============================================================================== prioritisation
def priority_score(d: pd.DataFrame, w_risk=0.4, w_overdue=0.25, w_condition=0.15, w_crit=0.1, w_eff=0.1) -> pd.Series:
    """0-100 weighted score. Every component is 0-100 before weighting."""
    risk = d["risk"].fillna(0)
    overdue = d["years_overdue"].clip(upper=20) / 20 * 100
    condition = (d["condition_numeric"].astype(float).fillna(3) - 1) / 4 * 100
    crit = d["criticality_score"]
    eff = (risk / pd.to_numeric(d["cost"], errors="coerce").clip(lower=1)).rank(pct=True) * 100
    total = w_risk + w_overdue + w_condition + w_crit + w_eff
    if total <= 0:
        return pd.Series(0.0, index=d.index)
    return ((w_risk * risk + w_overdue * overdue + w_condition * condition + w_crit * crit + w_eff * eff) / total).round(1)


STRATEGIES = {
    "Priority score (risk-weighted)": "priority",
    "Most risk reduced per $": "risk_per_dollar",
    "Most overdue first": "fifo",
    "Oldest (most life used) first": "consumed",
    "Cheapest first": "cheapest",
}


def _order(d: pd.DataFrame, strategy: str, prio: pd.Series) -> np.ndarray:
    cost = pd.to_numeric(d["cost"], errors="coerce").fillna(0).clip(lower=1).to_numpy()
    if strategy == "priority":
        key = -prio.to_numpy()
    elif strategy == "risk_per_dollar":
        key = -(d["risk"].fillna(0).to_numpy() / cost)
    elif strategy == "fifo":
        key = d["due"].fillna(9999).to_numpy()
    elif strategy == "consumed":
        key = -d["consumed"].fillna(0).to_numpy()
    else:
        key = cost
    return np.argsort(key, kind="stable")


def schedule(d: pd.DataFrame, annual_budget: float, budget_growth: float = 0.0, max_jobs: int = None,
             escalation: float = 0.0, strategy: str = "priority", prio: pd.Series = None,
             years: list = None, life_mult: float = 1.0):
    """Budget- (and optionally crew-) constrained replacement schedule.

    Every component whose (first) replacement falls due by the last year competes for
    each year's budget once it is due. Items are funded in strategy order; anything
    that doesn't fit is deferred, its cost escalating each year it waits. Up to three
    passes per year let smaller items use budget left over after a large one won't fit.
    Returns (yearly results, per-item schedule)."""
    years = years or YEARS_INT
    if life_mult != 1.0 and d.attrs.get("basis") == "std":
        due = (d["cmp_construction_year"] + d["std_life"] * life_mult)
    else:
        due = d["due"]
    item = d["valid"].fillna(False) & due.notna() & (due <= years[-1])
    items = d[item]
    if prio is None:
        prio = priority_score(items) if strategy == "priority" else pd.Series(0, index=items.index)
    else:
        prio = prio.reindex(items.index).fillna(0)
    order = _order(items.assign(due=due[item]), strategy, prio)
    due_eff = np.maximum(due[item].to_numpy(dtype=float), years[0])[order]
    base_cost = pd.to_numeric(items["cost"], errors="coerce").fillna(0).to_numpy(dtype=float)[order]
    risk = items["risk"].fillna(0).to_numpy(dtype=float)[order]
    crit_hi = items["criticality_tier"].isin(["Critical", "High"]).to_numpy()[order]
    n = len(order)
    funded_year = np.full(n, np.nan)
    paid = np.zeros(n)

    rows = []
    budget = annual_budget
    for yr in years:
        open_ = np.isnan(funded_year) & (due_eff <= yr)
        cost_now = base_cost * (1 + escalation) ** np.clip(yr - due_eff, 0, None)
        left, jobs_left = budget, (max_jobs if max_jobs else n)
        for _ in range(3):
            cand = open_ & np.isnan(funded_year)
            if not cand.any() or left <= 0 or jobs_left <= 0:
                break
            c = np.where(cand, cost_now, 0).cumsum()
            j = np.where(cand, 1, 0).cumsum()
            pick = cand & (c <= left) & (j <= jobs_left)
            if not pick.any():
                # nothing fits in order -- try the items that individually fit
                fits = cand & (cost_now <= left)
                if not fits.any():
                    break
                c = np.where(fits, cost_now, 0).cumsum()
                j = np.where(fits, 1, 0).cumsum()
                pick = fits & (c <= left) & (j <= jobs_left)
            funded_year[pick] = yr
            paid[pick] = cost_now[pick]
            left -= cost_now[pick].sum()
            jobs_left -= int(pick.sum())
        still = np.isnan(funded_year) & (due_eff <= yr)
        rows.append({
            "year": yr, "budget": budget, "spend": budget - left,
            "funded": int((funded_year == yr).sum()),
            "due_this_year": int((due_eff == yr).sum()),
            "backlog_count": int(still.sum()),
            "backlog_value": float(cost_now[still].sum()),
            "backlog_risk": float(risk[still].sum()),
            "critical_backlog": int((still & crit_hi).sum()),
        })
        budget *= (1 + budget_growth)

    plan = items.iloc[order][["cmp_id", "source_site", "site", "property", "comp. group", "component",
                              "Condition", "criticality_tier", "risk", "cost"]].copy()
    plan["due_year"] = due_eff
    plan["scheduled_year"] = funded_year
    plan["paid_cost"] = np.where(np.isnan(funded_year), np.nan, paid)
    plan["slip_years"] = plan["scheduled_year"] - plan["due_year"]
    plan["priority"] = prio.to_numpy()[order] if len(prio) == len(order) else np.nan
    plan["rank"] = np.arange(1, n + 1)
    return pd.DataFrame(rows), plan


def suggested_budget(d: pd.DataFrame) -> float:
    """$M: average annual forecast + backlog spread over 10 years, rounded to 0.5."""
    b = d.attrs.get("basis", "sys")
    need = d[year_cols(b)].sum().sum() / len(YEARS_INT) + d["backlog"].sum() / 10
    return float(max(0.5, round(need / 1e6 * 2) / 2))


def min_budget_to_clear(d, target_year: int, strategy="priority", escalation=0.0, budget_growth=0.0,
                        max_iter=18):
    """Smallest flat annual budget that leaves no backlog by target_year (binary search)."""
    years = [y for y in YEARS_INT if y <= target_year]
    total = pd.to_numeric(d.loc[d["valid"].fillna(False) & (d["due"] <= target_year), "cost"],
                          errors="coerce").sum()
    if total <= 0:
        return 0.0
    lo, hi = 0.0, total * (1 + escalation) ** len(years)
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        res, _ = schedule(d, mid, budget_growth, strategy=strategy, escalation=escalation, years=years)
        if res.iloc[-1]["backlog_value"] <= 1:
            hi = mid
        else:
            lo = mid
        if hi - lo < max(1000, hi * 0.005):
            break
    return hi


def memo(key, fn, *args, **kwargs):
    """Small session-level memo for expensive simulations."""
    ss = st.session_state
    store = ss.setdefault("lp_memo", {})
    if key not in store:
        if len(store) > 40:
            store.clear()
        store[key] = fn(*args, **kwargs)
    return store[key]


def data_key(d: pd.DataFrame) -> tuple:
    return (len(d), float(pd.to_numeric(d["cost"], errors="coerce").sum()), d.attrs.get("basis"),
            int(np.asarray(d.index, dtype="int64").sum()) if len(d) else 0,
            id(st.session_state.get("lp_core_cache", (None, None))[1]))


# =============================================================================== reliability (modelled)
def weibull_scale(mean_life, k):
    return mean_life / math.gamma(1 + 1 / k)


def survival(t, mean_life, k):
    lam = weibull_scale(mean_life, k)
    return np.exp(-np.power(np.clip(t, 0, None) / lam, k))


CONDITION_AGE_FACTOR = {"C1": 0.6, "C2": 0.85, "C3": 1.0, "C4": 1.25, "C5": 1.6}


def failure_probability(d: pd.DataFrame, horizon: int, k: float, condition_adjust: bool) -> pd.Series:
    """P(component reaches end of life within `horizon` years | it has survived to its current age),
    from a Weibull curve whose mean equals the selected life. A modelled estimate, not a prediction
    learned from failure history."""
    life = d["life"].astype(float)
    age = d["asset_age"].astype(float)
    if condition_adjust:
        age = age * d["Condition"].map(CONDITION_AGE_FACTOR).fillna(1.0)
    lam = life / math.gamma(1 + 1 / k)
    s_now = np.exp(-np.power(age / lam, k))
    s_later = np.exp(-np.power((age + horizon) / lam, k))
    with np.errstate(divide="ignore", invalid="ignore"):
        p = 1 - s_later / s_now
    p = pd.Series(p, index=d.index)
    p[s_now < 1e-9] = 1.0
    return p.clip(0, 1).where(life.notna() & age.notna())


# =============================================================================== clustering / outliers
def kmeans(X: np.ndarray, k: int, seed: int = 7, iters: int = 40):
    rng = np.random.default_rng(seed)
    centers = [X[rng.integers(len(X))]]
    for _ in range(1, k):
        d2 = np.min(((X[:, None, :] - np.array(centers)[None]) ** 2).sum(-1), axis=1)
        centers.append(X[rng.choice(len(X), p=d2 / d2.sum())])
    C = np.array(centers)
    for _ in range(iters):
        lab = np.argmin(((X[:, None, :] - C[None]) ** 2).sum(-1), axis=1)
        newC = np.array([X[lab == i].mean(0) if (lab == i).any() else C[i] for i in range(k)])
        if np.allclose(newC, C):
            break
        C = newC
    return C


def robust_z(x: pd.Series, groups: pd.Series) -> pd.Series:
    med = x.groupby(groups).transform("median")
    mad = (x - med).abs().groupby(groups).transform("median")
    with np.errstate(divide="ignore", invalid="ignore"):
        z = 0.6745 * (x - med) / mad.replace(0, np.nan)
    return z


# =============================================================================== comments -> maintenance history
def last_maintenance_year(comment: pd.Series) -> pd.Series:
    c = comment.fillna("").astype(str)
    order = c.str.extract(r"[Dd]ate:\s*\d{1,2}[./-]\d{1,2}[./-](\d{4})", expand=False)
    repl = c.str.extract(r"(?i)replaced[^0-9]{0,40}(?:\d{1,2}[./-]\d{1,2}[./-])?((?:19|20)\d{2})", expand=False)
    a = pd.to_numeric(order, errors="coerce")
    b = pd.to_numeric(repl, errors="coerce")
    out = pd.concat([a, b], axis=1).max(axis=1)
    return out.where(out.between(1950, CY))


# =============================================================================== page helpers
def basis_note(settings: dict):
    if settings["basis"] == "std":
        txt = ("<b>Standard life view</b> &mdash; end of life = construction year + average life from the Asset "
               "Life file. Compare with the System forecast using the switch in the sidebar.")
    else:
        txt = ("<b>System forecast view</b> &mdash; the source system's own renewal dates (including its "
               "condition-based resets). Upload the Asset Life file and switch to Standard life to compare.")
    st.markdown(f'<div class="panel-note">{txt}</div>', unsafe_allow_html=True)



def metric_cols(n: int):
    """Metric columns, at most three across so values are never cut off."""
    cols = []
    for i in range(0, n, 3):
        cols += list(st.columns(3))
    return cols[:n]


def download(df: pd.DataFrame, label: str, filename: str, key: str):
    st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=filename, mime="text/csv", key=key)


def page_setup(title: str, subtitle: str, key_prefix: str, needs_ref: bool = False):
    """Shared start of every Lifecycle Planning page. Returns (core_all, filtered, settings, ref)."""
    from common import inject_css, plotly_template, load_data, render_header, sidebar_filters
    st.set_page_config(page_title=title, layout="wide")
    inject_css()
    plotly_template()
    df_all = load_data()
    ref = asset_life_sidebar()
    settings = settings_sidebar(ref is not None)
    render_header(subtitle)
    if needs_ref and ref is None:
        st.info("This page compares the system against the **Asset Life** reference. Upload the Asset Life "
                "file in the sidebar (columns: Asset Name, Group, Average Life (Years)) to use it.")
        st.stop()
    core = get_core(df_all, ref, settings)
    d = sidebar_filters(core, key_prefix=key_prefix)
    if len(d) == 0:
        st.warning("No components match the current filters.")
        st.stop()
    return core, d, settings, ref
