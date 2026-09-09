import streamlit as st
import numpy as np
import plotly.graph_objects as go
from common import inject_css, plotly_template, show_chart, load_data, money, sidebar_filters, compute_tipping_economics, render_header, generate_component_group_pdf, COLORS

st.set_page_config(page_title="Economic Tipping Points", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Economic tipping points")
st.caption("Where does it stop making economic sense to keep maintaining an asset instead of replacing it?")

df = sidebar_filters(df_all, key_prefix="tipping")

st.markdown(
    '<div class="panel-note">Method: replacement cost is annualised into an <b>Equivalent Annual '
    'Cost (EAC)</b> using a capital recovery factor. Ongoing maintenance is modelled as a percentage '
    'of replacement cost that escalates as the component approaches end of life. The <b>tipping point</b> '
    'is the age at which the rising maintenance curve crosses the flat EAC line &mdash; the point where '
    'replacing becomes cheaper than continuing to patch. All three assumptions below are adjustable: '
    'this is a heuristic model, and its outputs move with the assumptions you set.</div>',
    unsafe_allow_html=True,
)

st.markdown("#### Assumptions (what-if)")
a1, a2, a3 = st.columns(3)
discount_rate = a1.slider("Discount rate (%)", 2.0, 15.0, 7.0, 0.5) / 100
maint_base_pct = a2.slider("Starting maintenance cost (% of replacement cost/yr)", 0.5, 6.0, 2.0, 0.5) / 100
maint_growth_k = a3.slider("Maintenance cost escalation factor", 1.0, 6.0, 3.0, 0.25,
                            help="How sharply maintenance cost accelerates as the asset ages")

d = compute_tipping_economics(df, discount_rate, maint_base_pct, maint_growth_k)

c1, c2, c3 = st.columns(3)
c1.metric("Assets past their tipping point", f"{(d['life_fraction_used'] >= d['tipping_life_fraction_live']).sum():,}")
c2.metric("Avg. tipping point (% of base life)", f"{d['tipping_life_fraction_live'].mean()*100:.0f}%")
c3.metric("Avg. EAC of replacement", money(d["eac_replace_live"].mean()))

st.markdown("---")
st.subheader("Maintain-vs-replace curve, by component group")
group_options = sorted(d["comp. group"].unique())
sel_group = st.selectbox("Component group", group_options, index=0)
sub = d[d["comp. group"] == sel_group]

life_pct = np.linspace(0, 1.5, 60)
avg_cost = sub["cost"].mean()
avg_eac = sub["eac_replace_live"].mean()
maint_curve = maint_base_pct * avg_cost * np.exp(maint_growth_k * life_pct)
tip_x = sub["tipping_life_fraction_live"].mean()

fig = go.Figure()
fig.add_trace(go.Scatter(x=life_pct * 100, y=maint_curve, name="Rising maintenance cost", line=dict(color=COLORS["warn"], width=3)))
fig.add_trace(go.Scatter(x=life_pct * 100, y=[avg_eac] * len(life_pct), name="EAC of replacement", line=dict(color=COLORS["accent"], width=3, dash="dash")))
fig.add_vline(x=tip_x * 100, line_color=COLORS["critical"], line_dash="dot",
              annotation_text=f"Tipping point: {tip_x*100:.0f}% of life", annotation_font_color=COLORS["critical"])
fig.update_layout(height=420, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="% of base life used",
                   yaxis_title="$ / year", legend=dict(orientation="h", yanchor="bottom", y=-0.3))
show_chart(fig)

st.markdown("---")
st.subheader("Where every component sits relative to its tipping point")
scatter_df = d.sample(min(4000, len(d)), random_state=1)
fig2 = go.Figure(go.Scatter(
    x=scatter_df["life_fraction_used"] * 100, y=scatter_df["tipping_life_fraction_live"] * 100,
    mode="markers", marker=dict(size=5, color=scatter_df["risk_score"], colorscale=[[0, COLORS["good"]], [1, COLORS["critical"]]],
                                 showscale=True, colorbar=dict(title="Risk")),
    text=scatter_df["component"], hovertemplate="%{text}<br>Life used: %{x:.0f}%<br>Tipping: %{y:.0f}%<extra></extra>",
))
fig2.add_trace(go.Scatter(x=[0, 150], y=[0, 150], mode="lines", line=dict(color=COLORS["text_muted"], dash="dot"),
                           showlegend=False))
fig2.update_layout(height=460, margin=dict(t=10, l=0, r=0, b=0), xaxis_title="Actual life used (%)",
                    yaxis_title="Modelled tipping point (%)")
st.caption("Points below the diagonal have already passed their economic tipping point under the current assumptions.")
show_chart(fig2)

st.markdown("---")
st.markdown("##### Export as a business case")
st.caption(f"A focused funding case for **{sel_group}** \u2014 units past tipping point, total cost exposure, "
           f"the curve above, and the highest-priority units in this group.")
if st.button("Generate component-group PDF", type="primary"):
    params = {"discount_rate": discount_rate, "maint_base_pct": maint_base_pct, "maint_growth_k": maint_growth_k}
    top_assets = sub.sort_values("urgency_score", ascending=False).head(10)
    portfolios_in_scope = sorted(df["portfolio"].unique())
    scope_label = f"{len(portfolios_in_scope)} portfolio(s), {len(sub):,} units in {sel_group}"
    pdf_bytes = generate_component_group_pdf(scope_label, sel_group, sub, params, top_assets)
    st.download_button(
        "Download PDF", data=pdf_bytes,
        file_name=f"FM_Asset_Excellence_{sel_group.replace(' ', '_')}_Business_Case.pdf",
        mime="application/pdf",
    )
