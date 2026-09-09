"""
Data prep for the Pannawonica Asset Lifecycle Decision Model.
Reads the raw workbook once, cleans it, computes every derived measure the
app needs, and writes a single parquet file the Streamlit app loads instantly.

Run once: python data_prep.py
"""
import numpy as np
import pandas as pd

SRC = "/mnt/project/Lifecycle__PAN.xlsx"
OUT = "data/processed.parquet"
CURRENT_YEAR = 2026  # forecast start / "today" reference used throughout

YEAR_COLS = list(range(2026, 2046))

CONDITION_NUM = {"C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}
# fraction of base_life "used up" implied by a condition rating (engineering heuristic)
CONDITION_LIFE_USED = {"C1": 0.10, "C2": 0.40, "C3": 0.65, "C4": 0.85, "C5": 0.97}


def load_raw() -> pd.DataFrame:
    df = pd.read_excel(SRC, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    df["comment"] = df["comment"].apply(lambda v: v if isinstance(v, str) else ("" if pd.isna(v) else str(v)))
    return df


def add_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    df["survey_missing"] = df["cmp_survey_year"] == 0

    # Soft transparency flag, NOT a confident "this is wrong" claim: every
    # component in the property shares one construction year, which is
    # consistent with the SME's note that missing years default to the
    # property's date -- but is equally consistent with a property that was
    # genuinely built in one campaign. We surface it as reduced confidence,
    # not as a corrected number, because we cannot tell the two apart from
    # this file alone.
    nunique_years = df.groupby("property code")["cmp_construction_year"].transform("nunique")
    n_components = df.groupby("property code")["cmp_construction_year"].transform("count")
    df["construction_year_uniform_property"] = (nunique_years == 1) & (n_components >= 5)

    df["already_overdue"] = df["next_renewal_year"] < CURRENT_YEAR
    df["renewal_beyond_window"] = df["next_renewal_year"] > 2045

    # The SME's specific critique of the C-model: a recent survey rating an
    # asset as good resets its forecast to a full remaining life for that
    # condition, regardless of how old the asset actually is. This risk is
    # inherent to short-lived, condition-scored equipment surveyed recently
    # -- it doesn't require the construction year to look defaulted.
    df["condition_reset_risk"] = (
        (df["calc_method"] == "C")
        & (df["cmp_survey_year"] >= 2023)
        & df["Condition"].isin(["C1", "C2"])
        & (df["base_life"] <= 20)
    )

    # Overall confidence in this row's forecast date, 0-100 -> High/Medium/Low
    conf = pd.Series(100.0, index=df.index)
    conf -= df["survey_missing"] * 30
    conf -= df["construction_year_uniform_property"] * 15
    conf -= df["condition_reset_risk"] * 25
    conf = conf.clip(0, 100)
    df["data_confidence_score"] = conf
    df["data_confidence"] = pd.cut(conf, bins=[-1, 59, 89, 101], labels=["Low", "Medium", "High"])
    return df


def mine_comments(df: pd.DataFrame) -> pd.DataFrame:
    c = df["comment"].fillna("")
    df["has_replace_override"] = c.str.contains(r"replace by", case=False, regex=True)
    df["replace_override_year"] = (
        c.str.extract(r"[Rr]eplace by\s*(\d{4})", expand=False).astype("float")
    )
    df["has_fault_note"] = c.str.contains(
        r"leak|crack|fault|damage|broken|not working", case=False, regex=True
    )
    df["has_maintenance_record"] = c.str.contains(r"order:|replaced", case=False, regex=True)
    return df


def add_lifecycle_estimates(df: pd.DataFrame) -> pd.DataFrame:
    df["condition_numeric"] = df["Condition"].map(CONDITION_NUM)
    life_used_frac = df["Condition"].map(CONDITION_LIFE_USED)

    # Age-based cross-check, shown alongside the system's own next_renewal_year
    # so a large gap between the two is itself a useful diagnostic -- it flags
    # exactly the C-model reset scenario the SME described, without us
    # silently picking a "winning" number.
    age = CURRENT_YEAR - df["cmp_construction_year"]
    remaining_life_age = df["base_life"] - age
    df["est_replacement_year_age_based"] = CURRENT_YEAR + remaining_life_age
    df["forecast_year_gap"] = (df["next_renewal_year"] - df["est_replacement_year_age_based"]).round(0)

    # An explicit human override in the comments (e.g. "Replace by 2032")
    # is the one case where we do prefer a number over the system's -- someone
    # already made the engineering judgment call.
    df["best_estimate_year"] = np.where(
        df["has_replace_override"] & df["replace_override_year"].notna(),
        df["replace_override_year"],
        df["next_renewal_year"],
    )
    df["life_fraction_used"] = np.clip(life_used_frac, 0, 1.5)
    return df


def add_risk_and_economics(df: pd.DataFrame, discount_rate=0.07, maint_base_pct=0.02, maint_growth_k=3.0):
    # risk score 0-100: condition severity x consequence x safety, normalised
    raw_risk = df["condition_numeric"] * df["consequence"] * df["safety"]
    df["risk_score"] = (raw_risk / raw_risk.max() * 100).round(1)

    # urgency nudges risk by known data problems / already-overdue status
    urgency = df["risk_score"].copy()
    urgency += df["already_overdue"] * 15
    urgency += df["condition_reset_risk"] * 10
    df["urgency_score"] = np.clip(urgency, 0, 100).round(1)

    # equivalent annual cost of replacement (capital recovery factor)
    n = df["base_life"].clip(lower=1)
    r = discount_rate
    crf = (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    df["eac_replace"] = (df["cost"] * crf).round(2)

    # heuristic maintenance-cost curve: escalates exponentially as life_fraction_used -> 1
    x = df["life_fraction_used"].clip(0, 1.5)
    df["annual_maintenance_cost_now"] = (maint_base_pct * df["cost"] * np.exp(maint_growth_k * x)).round(2)

    # tipping point: life-fraction x* where maintenance curve crosses EAC of replacement
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
    return df


def main():
    df = load_raw()
    df = add_quality_flags(df)
    df = mine_comments(df)
    df = add_lifecycle_estimates(df)
    df = add_risk_and_economics(df)

    import os
    os.makedirs("data", exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Wrote {len(df):,} rows x {len(df.columns)} cols -> {OUT}")


if __name__ == "__main__":
    main()
