import pandas as pd
import streamlit as st

import lifecycle_planning as lp
from common import inject_css, plotly_template, render_header

st.set_page_config(page_title="Asset Life Reference", layout="wide")
inject_css()
plotly_template()
render_header("Asset Life reference — the standard average life for each asset type")
st.caption("A simple view of the Asset Life file: asset name, component group and average life, exactly as "
           "loaded. This is the reference the Standard life view on pages 15–24 uses.")

ref = lp.asset_life_sidebar()
if ref is None:
    st.info("Upload the **Asset Life** file in the sidebar (columns: Asset Name, Group, Average Life (Years)) "
            "to view it here. It is processed in memory only and shared with pages 15–24 for this session.")
    st.stop()

t = ref.rename(columns={"asset_name": "Asset name", "taxonomy_group": "Component group",
                        "avg_life": "Average life (years)"})[["Asset name", "Component group", "Average life (years)"]]

c1, c2, c3 = st.columns(3)
c1.metric("Asset types", f"{len(t):,}")
c2.metric("Component groups", f"{t['Component group'].nunique():,}")
c3.metric("Without an average life", f"{t['Average life (years)'].isna().sum():,}")

f1, f2 = st.columns([2, 1])
search = f1.text_input("Search asset name", key="alr_search")
groups = sorted(t["Component group"].dropna().unique())
sel = f2.multiselect("Component group", groups, default=[], key="alr_group", help="Leave empty to show all groups")
v = t
if search:
    v = v[v["Asset name"].str.contains(search, case=False, regex=False, na=False)]
if sel:
    v = v[v["Component group"].isin(sel)]

st.caption(f"Showing {len(v):,} of {len(t):,} asset types.")
st.dataframe(v, hide_index=True, width="stretch", height=640,
             column_config={"Average life (years)": st.column_config.NumberColumn(format="%d yrs")})
lp.download(v, "Download (CSV)", "asset_life_reference.csv", "alr_dl")
