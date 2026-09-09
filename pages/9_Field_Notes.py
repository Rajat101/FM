import streamlit as st
from common import inject_css, plotly_template, load_data, money, sidebar_filters, render_header, COLORS

st.set_page_config(page_title="Field Notes", layout="wide")
inject_css()
plotly_template()

df_all = load_data()
render_header("Field notes")
st.caption("What's actually written in the comments \u2014 known faults and human overrides on record, not just model output.")

df = sidebar_filters(df_all, key_prefix="notes")

with_comment = df[df["comment"].astype(str).str.len() > 0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Components with any comment", f"{len(with_comment):,}", help=f"{len(with_comment)/max(len(df),1)*100:.0f}% of the filtered portfolio")
c2.metric("Active fault flagged", f"{df['has_fault_note'].sum():,}")
c3.metric("Human override on record", f"{df['has_replace_override'].sum():,}")
c4.metric("Maintenance record referenced", f"{df['has_maintenance_record'].sum():,}")

st.markdown(
    '<div class="panel-note">These flags come from a simple text search on the comment column: fault '
    'keywords (leak, crack, fault, damage, broken, not working), an explicit "replace by [year]" override, '
    'or a reference to a work order / prior replacement. See the How to Use page for the full method.</div>',
    unsafe_allow_html=True,
)

st.markdown("---")
st.subheader("Active fault flags")
faults = df[df["has_fault_note"]].sort_values("urgency_score", ascending=False)[
    ["component", "portfolio", "Condition", "urgency_score", "cost", "comment"]
]
if len(faults):
    st.dataframe(
        faults.head(100), width="stretch", hide_index=True,
        column_config={
            "cost": st.column_config.NumberColumn("cost", format="$%.0f"),
            "urgency_score": st.column_config.ProgressColumn("urgency", format="%.0f", min_value=0, max_value=100),
        },
    )
    if len(faults) > 100:
        st.caption(f"Showing top 100 of {len(faults):,} by urgency.")
else:
    st.info("No active fault flags in the current filter.")

st.markdown("---")
st.subheader("Human overrides vs. the system's own forecast")
overrides = df[df["has_replace_override"] & df["replace_override_year"].notna()][
    ["component", "portfolio", "Condition", "next_renewal_year", "replace_override_year", "comment"]
].rename(columns={"next_renewal_year": "System says", "replace_override_year": "Human override says"})
unparsed = df[df["has_replace_override"] & df["replace_override_year"].isna()]
if len(overrides):
    overrides["Human override says"] = overrides["Human override says"].astype(int)
    st.dataframe(overrides, width="stretch", hide_index=True)
    st.caption(
        "These overrides are already trusted over the system date everywhere else in the app "
        "(via best_estimate_year)."
    )
else:
    st.info("No human overrides found in the current filter's comments.")
if len(unparsed):
    st.caption(
        f"{len(unparsed):,} additional comment(s) mention \u201creplace by\u201d but without a 4-digit year "
        f"the app can parse (e.g. \u201creplace by next year\u201d) \u2014 excluded from the table above."
    )

st.markdown("---")
st.subheader("Components referencing a prior work order or replacement")
maint = df[df["has_maintenance_record"]].sort_values("cost", ascending=False)[
    ["component", "portfolio", "Condition", "cost", "comment"]
]
if len(maint):
    st.dataframe(
        maint.head(100), width="stretch", hide_index=True,
        column_config={"cost": st.column_config.NumberColumn("cost", format="$%.0f")},
    )
    if len(maint) > 100:
        st.caption(f"Showing top 100 of {len(maint):,} by cost.")
else:
    st.info("No maintenance-record references found in the current filter's comments.")
