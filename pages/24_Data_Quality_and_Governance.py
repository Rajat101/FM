from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS

core, df, settings, ref = lp.page_setup("Data Quality & Governance",
                                        "Data quality & governance — can the lifecycle numbers be trusted?", "dqg")
st.caption("Checks the inputs every lifecycle calculation depends on — construction year, life, cost, category, "
           "survey and maintenance history — and keeps a log of lifecycle decisions.")
n = len(df)

# ------------------------------------------------------------------ checks
cy = pd.to_numeric(df["cmp_construction_year"], errors="coerce")
top_year = cy.mode().iloc[0] if cy.notna().any() else np.nan
top_year_share = (cy == top_year).mean()
r = df["sys_life"] / df["std_life"]
dup_key = [c for c in ["cmp_id", "mnt_id"] if c in df.columns]
exact_dupes = df.duplicated(subset=dup_key + (["source_site"] if "source_site" in df.columns else []), keep=False)
pot_key = [c for c in ["property code", "component", "location", "qty", "cmp_construction_year"] if c in df.columns]
pot_dupes = df.duplicated(subset=pot_key, keep=False) & ~exact_dupes
grp_per_comp = df.groupby("component")["comp. group"].transform("nunique")
life_per_comp = df.groupby("component")["sys_life"].transform("nunique")

checks = [
    ("Construction year missing or invalid", ~df["construction_year_valid"]),
    ("Construction year same for every component in the property (likely default)",
     df["construction_year_uniform_property"].fillna(False)),
    (f"Construction year = {int(top_year) if pd.notna(top_year) else '–'} (most common year, "
     f"{top_year_share*100:.0f}% of records — check if it is a system default)", cy == top_year),
    ("System base life missing or outside 1–150 years", ~df["base_life_valid"]),
    ("System base life ≥ 100 years", df["sys_life"] >= 100),
    ("No standard average life (not in Asset Life file)", ~df["has_avg_life"] if ref is not None
     else pd.Series(False, index=df.index)),
    ("System life < 50% or > 200% of standard", (r < 0.5) | (r > 2)),
    ("Never surveyed", df["survey_age"].isna()),
    ("Survey older than 5 years", df["survey_age"] >= 5),
    ("Replacement cost missing or zero", ~df["has_cost"]),
    ("Exact duplicate asset ID", exact_dupes),
    ("Possible duplicate (same property, component, location, qty, year)", pot_dupes),
    ("Component name used in more than one component group", grp_per_comp > 1),
    ("Same component given different base lives", life_per_comp > 1),
]
sc = pd.DataFrame([{"Check": name, "Records flagged": int(m.sum()), "% of records": m.mean() * 100,
                    "Value affected": df.loc[m, "cost"].sum()} for name, m in checks])
sc["Status"] = np.select([sc["% of records"] == 0, sc["% of records"] < 5], ["✅ Pass", "⚠️ Review"], "❌ Fix")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg. record completeness", f"{df['completeness_score'].mean():.0f}%")
c2.metric("Fully complete records", f"{(df['completeness_score'] == 100).mean()*100:.0f}%")
c3.metric("High data confidence", f"{(df['data_confidence'].astype(str) == 'High').mean()*100:.0f}%")
c4.metric("Checks needing a fix", f"{(sc['Status'] == '❌ Fix').sum()} of {len(sc)}")

st.subheader("Lifecycle assumption validation scorecard")
st.dataframe(sc, hide_index=True, width="stretch", column_config={
    "% of records": st.column_config.NumberColumn(format="%.1f%%"),
    "Value affected": st.column_config.NumberColumn(format="$%.0f")})
pick = st.selectbox("Show records for check", [c[0] for c in checks], key="dqg_pick")
mask = dict(checks)[pick]
cols = ["cmp_id", "source_site", "property code", "property", "comp. group", "component", "location", "qty",
        "cmp_construction_year", "cmp_survey_year", "base_life", "avg_life", "cost"]
cols = [c for c in cols if c in df.columns]
st.dataframe(df.loc[mask, cols].head(2000), hide_index=True, width="stretch",
             column_config={"cost": st.column_config.NumberColumn(format="$%.0f")})
lp.download(df.loc[mask, cols], "Download flagged records (CSV)", "dq_flagged.csv", "dqg_dl1")

# ------------------------------------------------------------------ completeness
st.markdown("---")
st.subheader("Asset record completeness score")
st.caption("Six checks per record: valid, non-default construction year · valid base life · standard life found · "
           "survey year present · cost > 0 · condition rating present.")
col1, col2 = st.columns(2)
with col1:
    dist = df["completeness_score"].value_counts().sort_index()
    fig = go.Figure(go.Bar(x=dist.index.astype(int).astype(str) + "%", y=dist.values, marker_color=COLORS["accent"]))
    fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0), yaxis_title="Records",
                      xaxis_title="Completeness score")
    show_chart(fig)
with col2:
    site_col = "source_site" if df["source_site"].nunique() > 1 else "site"
    by = df.groupby(site_col)["completeness_score"].mean().sort_values().tail(15)
    fig = go.Figure(go.Bar(y=by.index.astype(str), x=by.values, orientation="h", marker_color=COLORS["steel"]))
    fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Avg. completeness %", xaxis_range=[0, 100])
    show_chart(fig)
miss = pd.DataFrame({c.replace("has_", "").replace("_", " "): 1 - df[c].mean() for c in
                     ["has_construction_year", "has_base_life", "has_avg_life", "has_survey", "has_cost",
                      "has_condition"]}, index=["% missing / failing"]).T * 100
by_group = df.groupby("comp. group")[["has_construction_year", "has_base_life", "has_avg_life", "has_survey",
                                      "has_cost", "has_condition"]].mean().mul(100).round(0)
by_group.columns = [c.replace("has_", "").replace("_", " ") for c in by_group.columns]
st.markdown("**% of records passing each check, by component group**")
st.dataframe(by_group, width="stretch",
             column_config={c: st.column_config.ProgressColumn(c, min_value=0, max_value=100, format="%.0f%%")
                            for c in by_group.columns})

# ------------------------------------------------------------------ construction year
st.markdown("---")
st.subheader("Construction year patterns")
yc = cy.value_counts().sort_index()
fig = go.Figure(go.Bar(x=yc.index.astype(int), y=yc.values,
                       marker_color=[COLORS["critical"] if y == top_year else COLORS["steel"] for y in yc.index]))
fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Construction year", yaxis_title="Records")
show_chart(fig)
st.caption("A single tall bar usually means a default date (property added to the system), not a real build year. "
           "The SME notes that missing construction years default to the property's date.")

# ------------------------------------------------------------------ categories
st.markdown("---")
st.subheader("Inconsistent asset categories")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Same component name in several component groups**")
    x = df[grp_per_comp > 1].groupby("component").agg(groups=("comp. group", lambda s: ", ".join(sorted(s.unique()))),
                                                      records=("cmp_id", "size")).sort_values("records", ascending=False)
    st.dataframe(x, width="stretch")
with col2:
    st.markdown("**Same component, different base lives**")
    y = df[life_per_comp > 1].groupby("component").agg(
        lives=("sys_life", lambda s: ", ".join(str(int(v)) for v in sorted(s.dropna().unique()))),
        records=("cmp_id", "size"), standard=("std_life", "first")).sort_values("records", ascending=False)
    st.dataframe(y, width="stretch")
if ref is not None:
    st.markdown("**System group vs Asset Life taxonomy group**")
    tax_of = dict(zip(ref["asset_name"].map(lp._key), ref["taxonomy_group"]))
    tg = set(ref["taxonomy_group"].dropna())
    name_grp = df["component"].map(lambda s: tax_of.get(lp._key(s)))
    sys_grp = df["comp. group"].map({g: lp._map_group(g, tg) for g in df["comp. group"].unique()})
    mis = df[name_grp.notna() & sys_grp.ne("") & (name_grp != sys_grp)].assign(taxonomy_group=name_grp)
    z = mis.groupby(["component", "comp. group", "taxonomy_group"]).size().rename("records").reset_index()
    st.caption(f"{len(mis):,} records sit in a system group that doesn't match the taxonomy group for that asset "
               f"name ({z['component'].nunique()} asset names).")
    st.dataframe(z.sort_values("records", ascending=False), hide_index=True, width="stretch")

# ------------------------------------------------------------------ duplicates
st.markdown("---")
st.subheader("Duplicate asset identification")
d1, d2 = st.columns(2)
d1.metric("Exact duplicate IDs", f"{exact_dupes.sum():,}")
d2.metric("Possible duplicates", f"{pot_dupes.sum():,}", money(df.loc[pot_dupes, "cost"].sum()), delta_color="off")
if pot_dupes.any():
    pd_ = df[pot_dupes].sort_values(pot_key)
    st.dataframe(pd_[cols].head(2000), hide_index=True, width="stretch",
                 column_config={"cost": st.column_config.NumberColumn(format="$%.0f")})
    st.caption("Same property, component, location, quantity and construction year. Some are legitimate "
               "(e.g. two identical units in one room) — check before removing.")

# ------------------------------------------------------------------ inspection & maintenance tracking
st.markdown("---")
st.subheader("Last inspection and last maintenance")
lm = lp.last_maintenance_year(df["comment"])
t1, t2, t3, t4 = st.columns(4)
t1.metric("Records with a survey year", f"{df['has_survey'].mean()*100:.0f}%")
t2.metric("Median years since survey", f"{df['survey_age'].median():.0f}" if df["survey_age"].notna().any() else "–")
t3.metric("Maintenance date found in comments", f"{lm.notna().sum():,}")
t4.metric("Fault noted in comments", f"{df['has_fault_note'].fillna(False).sum():,}")
mt = df.assign(last_inspection=df["cmp_survey_year"].replace(0, np.nan), last_maintenance=lm)
show = mt[mt["last_maintenance"].notna() | mt["has_fault_note"].fillna(False)][
    ["cmp_id", "property", "component", "last_inspection", "last_maintenance", "has_fault_note", "comment"]]
st.dataframe(show.sort_values("last_maintenance", ascending=False).head(1000), hide_index=True, width="stretch",
             column_config={"last_inspection": st.column_config.NumberColumn(format="%d"),
                            "last_maintenance": st.column_config.NumberColumn(format="%d")})
st.caption("Maintenance dates are read from free-text comments ('Order: …, Date: dd.mm.yyyy', 'replaced … yyyy'), "
           "so coverage is partial. A work-order export would make this complete.")

# ------------------------------------------------------------------ decision log
st.markdown("---")
st.subheader("Audit trail — lifecycle and replacement decisions")
st.markdown('<div class="panel-note">Decisions are kept for this session only — the app stores nothing on the '
            'server. <b>Download the log</b> before closing, and upload it next time to carry on.</div>',
            unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("lp_decision_log", [])
up = st.file_uploader("Continue an existing log (CSV)", type=["csv"], key="dqg_log_up")
if up is not None and not ss.get("lp_log_loaded") == up.name:
    prev = pd.read_csv(up)
    ss["lp_decision_log"] = prev.to_dict("records") + ss["lp_decision_log"]
    ss["lp_log_loaded"] = up.name
    st.success(f"Loaded {len(prev):,} earlier decisions.")
with st.form("dqg_log_form", clear_on_submit=True):
    f1, f2 = st.columns([2, 1])
    ids = f1.text_input("Component ID(s) — cmp_id, comma-separated")
    decision = f2.selectbox("Decision", ["Approve replacement", "Defer replacement", "Re-survey", "Override life",
                                         "Override cost", "Mark as data error", "No action"])
    f3, f4, f5 = st.columns([1, 1, 2])
    new_year = f3.number_input("New replacement year (optional)", 0, 2100, 0)
    new_life = f4.number_input("New life in years (optional)", 0, 200, 0)
    by = f5.text_input("Decided by")
    reason = st.text_area("Reason / evidence")
    if st.form_submit_button("Add to log"):
        id_list = [s.strip() for s in ids.split(",") if s.strip()]
        known = set(df["cmp_id"].astype(str))
        bad = [i for i in id_list if i not in known]
        if not id_list:
            st.error("Enter at least one component ID.")
        elif not by or not reason:
            st.error("'Decided by' and 'Reason' are required for an audit trail.")
        else:
            info = df.assign(_id=df["cmp_id"].astype(str)).drop_duplicates("_id").set_index("_id")
            good = [i for i in id_list if i in info.index]
            for i in good:
                row = info.loc[i]
                ss["lp_decision_log"].append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "cmp_id": i,
                    "source_site": row.get("source_site"), "component": row["component"],
                    "property": row["property"], "decision": decision,
                    "new_replacement_year": new_year or None, "new_life": new_life or None,
                    "system_due": row["sys_due"], "standard_due": row["std_due"],
                    "decided_by": by, "reason": reason, "basis_viewed": settings["basis_label"]})
            if good:
                st.success(f"Logged {len(good)} decision(s).")
            if bad:
                st.error(f"Not logged — not found in the loaded data: {', '.join(bad)}")
log = pd.DataFrame(ss["lp_decision_log"])
if len(log):
    st.dataframe(log, hide_index=True, width="stretch")
    lp.download(log, "Download decision log (CSV)", f"lifecycle_decision_log_{datetime.now():%Y%m%d}.csv", "dqg_dl_log")
else:
    st.caption("No decisions logged yet.")
