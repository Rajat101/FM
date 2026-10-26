import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle_planning as lp
from common import show_chart, money, COLORS, YEARS_INT

core, df, settings, ref = lp.page_setup("Predictive Analytics", "Predictive analytics — modelled estimates", "pda")
b = settings["basis"]
life_label = "standard average life" if b == "std" else "system base life"

st.markdown(
    f'<div class="panel-note"><b>Modelled, not learned.</b> Your exports hold one snapshot per asset — no failure '
    f'records, repeat condition surveys or maintenance spend. So the probabilities here come from a standard '
    f'reliability (Weibull) curve centred on each component\'s {life_label}, and the clustering and outlier checks '
    f'use the data as it stands. With work-order history or yearly snapshots, these can be replaced by models '
    f'trained on what actually happened.</div>', unsafe_allow_html=True)

with st.expander("What would unlock true prediction"):
    st.markdown("""
| Capability | Needs |
|---|---|
| Remaining useful life learned from history | Replacement / failure dates per asset (work orders) |
| Condition deterioration prediction | The same asset surveyed at least 2–3 times (yearly export snapshots) |
| Maintenance cost prediction | Maintenance spend per asset or per work order |
| Failure trend prediction (observed) | Failure events with dates |
| Predictive maintenance recommendations | All of the above, ideally with sensor or inspection readings |
""")

c1, c2, c3 = st.columns(3)
k = c1.slider("Curve shape (Weibull k)", 1.2, 6.0, 3.0, 0.1, key="pda_k",
              help="Higher = failures cluster tightly around the average life. ~1.5 random/early failures, "
                   "3 typical wear-out, 5+ very predictable.")
cond_adj = c2.toggle("Adjust age by condition", value=True, key="pda_cond",
                     help="C1 assets age as if 40% younger, C5 as if 60% older.")
horizon = c3.selectbox("Probability horizon", [1, 3, 5, 10], index=2, key="pda_h",
                       format_func=lambda h: f"Next {h} year{'s' if h > 1 else ''}")
ok = df["life"].notna() & df["asset_age"].notna()
d = df[ok].copy()
d["p_h"] = lp.failure_probability(d, horizon, k, cond_adj)
d["p_1"] = lp.failure_probability(d, 1, k, cond_adj)

# ------------------------------------------------------------------ failure probability
st.markdown("---")
st.subheader("Probability of reaching end of life")
past = d["asset_age"] > d["life"]
di = d[~past]
m0, m1, m2, m3, m4 = st.columns(5)
m0.metric("Already past life (age-based)", f"{past.sum():,}", money(d.loc[past, "cost"].sum()), delta_color="off")
m1.metric("Of the rest: expected to reach EOL next year", f"{di['p_1'].sum():,.0f}",
          money((di["p_1"] * di["cost"]).sum()), delta_color="off")
m2.metric(f"Expected within {horizon} yrs", f"{di['p_h'].sum():,.0f}", money((di["p_h"] * di["cost"]).sum()),
          delta_color="off")
m3.metric(f"> 50% likely within {horizon} yrs", f"{(di['p_h'] > 0.5).sum():,}")
m4.metric("Critical with > 50% chance", f"{((di['p_h'] > 0.5) & (di['criticality_tier'] == 'Critical')).sum():,}")
st.caption("Components already past their life are counted separately — the model gives them a near-certain "
           "probability, which would otherwise swamp the forecast for everything still in service.")
col1, col2 = st.columns(2)
with col1:
    fig = go.Figure(go.Histogram(x=di["p_h"] * 100, nbinsx=40, marker_color=COLORS["accent"]))
    fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0),
                      xaxis_title=f"% chance within {horizon} yrs (components still within life)",
                      yaxis_title="Components")
    show_chart(fig)
with col2:
    g = di.groupby("comp. group").apply(lambda x: (x["p_h"] * x["cost"]).sum(), include_groups=False).sort_values()
    fig = go.Figure(go.Bar(y=g.index, x=g.values / 1e6, orientation="h", marker_color=COLORS["warn"]))
    fig.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0),
                      xaxis_title=f"Expected replacement $M within {horizon} yrs")
    show_chart(fig)
cols = ["cmp_id", "source_site", "property", "component", "Condition", "asset_age", "life", "p_h", "criticality_tier",
        "cost"]
t = d.sort_values(["p_h", "criticality_score"], ascending=False)
st.dataframe(t[cols].head(1000), hide_index=True, width="stretch", column_config={
    "p_h": st.column_config.ProgressColumn(f"P(EOL ≤ {horizon} yrs)", min_value=0, max_value=1, format="percent"),
    "cost": st.column_config.NumberColumn(format="$%.0f")})
lp.download(t[cols], "Download probabilities (CSV)", "eol_probability.csv", "pda_dl1")

# ------------------------------------------------------------------ survival curves
st.markdown("---")
st.subheader("Survival analysis — probability of remaining in service")
life_by_group = d.groupby("comp. group")["life"].median().sort_values()
pick = st.multiselect("Component groups", life_by_group.index.tolist(),
                      default=life_by_group.index.tolist()[:: max(1, len(life_by_group) // 4)][:5], key="pda_groups")
tt = np.linspace(0, 100, 201)
fig = go.Figure()
for gname in pick:
    L = float(life_by_group[gname])
    fig.add_trace(go.Scatter(x=tt, y=lp.survival(tt, L, k) * 100, name=f"{gname} ({L:.0f} yrs)", mode="lines"))
fig.update_layout(height=360, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Age (years)",
                  yaxis_title="% still in service", legend=dict(orientation="h", yanchor="bottom", y=-0.4))
show_chart(fig)

st.markdown("**Asset lifetime by category (modelled)**")
q = lambda L, p: lp.weibull_scale(L, k) * (-math.log(1 - p)) ** (1 / k)
lt = d.groupby("comp. group").agg(components=("cmp_id", "size"), median_life=("life", "median"),
                                  avg_age=("asset_age", "mean"))
lt["10% replaced by (yrs)"] = lt["median_life"].map(lambda L: q(L, 0.10))
lt["50% replaced by (yrs)"] = lt["median_life"].map(lambda L: q(L, 0.50))
lt["90% replaced by (yrs)"] = lt["median_life"].map(lambda L: q(L, 0.90))
lt["% of fleet past 90% point"] = d.assign(_p=d["asset_age"] > d["life"].map(lambda L: q(L, 0.9))).groupby(
    "comp. group")["_p"].mean() * 100
st.dataframe(lt.round(1), width="stretch")

# ------------------------------------------------------------------ expected EOL trend
st.markdown("---")
st.subheader("End-of-life trend — expected events per year")
age = d["asset_age"].to_numpy(dtype=float)
if cond_adj:
    age = age * d["Condition"].map(lp.CONDITION_AGE_FACTOR).fillna(1.0).to_numpy()
lam = d["life"].to_numpy(dtype=float) / math.gamma(1 + 1 / k)
s0 = np.exp(-np.power(age / lam, k))
s0 = np.where(s0 < 1e-9, 1e-9, s0)
probs = []
prev = np.ones_like(age)
for i, y in enumerate(YEARS_INT, start=1):
    s = np.exp(-np.power((age + i) / lam, k)) / s0
    probs.append(prev - s)
    prev = s
P = np.vstack(probs).T
trend_by = st.radio("Split by", ["comp. group", "criticality_tier"], horizontal=True, key="pda_trend",
                    format_func={"comp. group": "Component group", "criticality_tier": "Criticality"}.get)
grp = lp.top_n_other(d, trend_by, "cost", 7).to_numpy()
fig = go.Figure()
for gname in pd.unique(grp):
    m = grp == gname
    fig.add_trace(go.Bar(x=YEARS_INT, y=P[m].sum(axis=0), name=str(gname)))
fig.update_layout(barmode="stack", height=360, margin=dict(t=10, l=0, r=0, b=0),
                  yaxis_title="Expected first end-of-life events", legend=dict(orientation="h", yanchor="bottom", y=-0.35))
show_chart(fig)
st.caption("Each component contributes its probability of first reaching end of life in each year (given it is in "
           "service today). Components already well past their life show up mostly in the first years.")

# ------------------------------------------------------------------ clustering
st.markdown("---")
st.subheader("Asset portfolio clustering")
n_clusters = st.slider("Number of clusters", 3, 8, 5, key="pda_k_clusters")
feat = pd.DataFrame({
    "Age": d["asset_age"],
    "Life used": d["consumed"].clip(upper=3).fillna(1),
    "Cost (log)": np.log10(d["cost"].clip(lower=1)),
    "Criticality": d["criticality"],
    "Condition": d["condition_numeric"].astype(float).fillna(3),
    "Survey age": d["survey_age"].fillna(15).clip(upper=15),
})
mu, sd = feat.mean(), feat.std().replace(0, 1)
X = ((feat - mu) / sd).to_numpy()
rng = np.random.default_rng(1)
fit_idx = rng.choice(len(X), size=min(20000, len(X)), replace=False)
C = lp.memo(("pda_km", lp.data_key(d), n_clusters), lp.kmeans, X[fit_idx], n_clusters)
labels = np.argmin(((X[:, None, :] - C[None]) ** 2).sum(-1), axis=1)
names = []
for c in C:
    parts = [("High " if v > 0 else "Low ") + f.lower() for f, v in sorted(zip(feat.columns, c), key=lambda t: -abs(t[1]))[:2]
             if abs(v) > 0.4]
    names.append(", ".join(parts) or "Typical")
d["cluster"] = [f"{i+1}: {names[i]}" for i in labels]
prof = d.groupby("cluster").agg(components=("cmp_id", "size"), avg_age=("asset_age", "mean"),
                                life_used_pct=("consumed", lambda s: s.clip(upper=3).mean() * 100),
                                avg_cost=("cost", "mean"), total_cost=("cost", "sum"),
                                avg_criticality=("criticality", "mean"),
                                overdue_pct=("status", lambda s: (s == "Overdue").mean() * 100),
                                top_group=("comp. group", lambda s: s.mode().iloc[0] if len(s) else ""))
st.dataframe(prof.round(1), width="stretch", column_config={
    "avg_cost": st.column_config.NumberColumn(format="$%.0f"),
    "total_cost": st.column_config.NumberColumn(format="$%.0f"),
    "life_used_pct": st.column_config.NumberColumn("Life used", format="%.0f%%"),
    "overdue_pct": st.column_config.NumberColumn("% overdue", format="%.0f%%")})
samp = d.sample(min(6000, len(d)), random_state=2)
fig = go.Figure()
for cl in sorted(samp["cluster"].unique()):
    s = samp[samp["cluster"] == cl]
    fig.add_trace(go.Scatter(x=s["asset_age"], y=s["consumed"].clip(upper=3) * 100, mode="markers", name=cl,
                             marker=dict(size=5, opacity=0.6), text=s["component"],
                             hovertemplate="%{text}<br>Age %{x} · %{y:.0f}% life used<extra></extra>"))
fig.update_layout(height=400, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Age (yrs)",
                  yaxis_title="% of life used (capped 300%)", legend=dict(orientation="h", yanchor="bottom", y=-0.4))
show_chart(fig)
st.caption("Clusters group components with similar age, life used, cost, criticality, condition and survey age, "
           "so each group can get its own strategy. Sample of 6,000 shown.")

# ------------------------------------------------------------------ outliers
st.markdown("---")
st.subheader("Outlier detection")
o1, o2, o3 = st.tabs(["Unusual cost (rate or total)", "Unusually short or long life", "Unusual age"])
with o1:
    rate = pd.to_numeric(df.get("rate"), errors="coerce") if "rate" in df.columns else df["cost"]
    key = df["component"].astype(str) + " | " + df.get("unit", pd.Series("", index=df.index)).astype(str)
    zr = lp.robust_z(rate, key)
    zc = lp.robust_z(np.log10(df["cost"].clip(lower=1)), df["component"])
    out = df.assign(rate_z=zr.round(1), cost_z=zc.round(1))
    out = out[(out["rate_z"].abs() > 3.5) | (out["cost_z"] > 3.5)].sort_values("cost", ascending=False)
    st.caption(f"{len(out):,} components whose rate (per unit) or total cost is far from others of the same type "
               f"(robust z-score > 3.5). Large qty × rate values are often data-entry errors.")
    st.dataframe(out[["cmp_id", "source_site", "property", "component", "qty", "unit", "rate", "cost", "rate_z",
                      "cost_z"]].head(1000), hide_index=True, width="stretch",
                 column_config={"cost": st.column_config.NumberColumn(format="$%.0f")})
    lp.download(out, "Download cost outliers (CSV)", "cost_outliers.csv", "pda_dl2")
with o2:
    if ref is None:
        st.info("Upload the Asset Life file to compare system lives with the standard.")
    else:
        r = df["sys_life"] / df["std_life"]
        lo = df[r < 0.5].assign(ratio=r)
        hi = df[r > 2].assign(ratio=r)
        a, bcol = st.columns(2)
        a.metric("Unusually short-lived (system < 50% of standard)", f"{len(lo):,}", money(lo["cost"].sum()),
                 delta_color="off")
        bcol.metric("Unusually long-lived (system > 200% of standard)", f"{len(hi):,}", money(hi["cost"].sum()),
                    delta_color="off")
        sl = pd.concat([lo, hi]).groupby("component").agg(components=("cmp_id", "size"),
                                                           system_life=("sys_life", "median"),
                                                           standard_life=("std_life", "first"),
                                                           cost=("cost", "sum")).sort_values("cost", ascending=False)
        st.dataframe(sl, width="stretch", column_config={"cost": st.column_config.NumberColumn(format="$%.0f")})
with o3:
    za = lp.robust_z(df["asset_age"].astype(float), df["property code"].astype(str))
    out = df.assign(age_z=za.round(1))
    out = out[out["age_z"].abs() > 3.5].sort_values("age_z", key=lambda s: s.abs(), ascending=False)
    st.caption(f"{len(out):,} components whose age is far from the rest of their property — a hint of a wrong or "
               f"defaulted construction year.")
    st.dataframe(out[["cmp_id", "property", "component", "cmp_construction_year", "asset_age", "age_z"]].head(1000),
                 hide_index=True, width="stretch")
