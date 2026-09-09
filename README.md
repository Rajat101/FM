# Pannawonica Asset Lifecycle & Decision Model

A multi-page Streamlit app that cleans a lifecycle asset export, computes
risk scores, economic tipping points, and a maintain / renew / replace /
defer decision for every component, then lets you run budget what-if
scenarios across a 20-year horizon.

**No data is committed to this repo.** The app takes the workbook via an
in-browser file upload and processes it entirely in memory, in your own
session -- nothing is written to disk or shared with anyone else. This is
what lets the repo (and app) be public even though the underlying asset
data is sensitive.

## Pages

1. **Home** — upload the workbook here; portfolio-wide KPIs, CapEx
   forecast, decision mix, data confidence overview.
2. **Asset Explorer** — filterable/searchable table of every component with
   a full drill-down per asset (condition, forecast profile, comments).
3. **Lifecycle Forecast** — CapEx vs OpEx by year, by portfolio, by
   component group, and deferred-renewal exposure.
4. **Risk & Condition** — risk scoring methodology, condition distribution,
   and the life-used-vs-risk decision matrix.
5. **Economic Tipping Points** — adjustable maintain-vs-replace economics
   (discount rate, maintenance escalation) with live-recomputed tipping
   points per component group.
6. **Scenario Modeling** — set an annual budget, growth rate, deferral
   escalation, and prioritisation weighting; compare two scenarios
   side-by-side on backlog value, risk exposure, and spend.

## Run locally

```bash
pip install -r requirements.txt
streamlit run Home.py
```

Opens at `http://localhost:8501`. Upload your copy of `Lifecycle_PAN.xlsx`
in the sidebar when prompted -- the app expects the same column layout as
the original export (portfolio, site, cmp_id, base_life, Condition, cost,
the 2026-2045 annual columns, etc.).

## Deploying on Streamlit Community Cloud

1. Push this folder's contents to a GitHub repo (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, click **New app**.
3. Pick the repo/branch, set **Main file path** to `Home.py`, click Deploy.
4. Open the app and upload the workbook each session -- it's never stored
   on the server between sessions, so nothing sensitive lives in the repo
   or on Streamlit's infrastructure after you close the tab.

### Optional: faster local iteration

`data_prep.py` can pre-process a local copy of the workbook into
`data/processed.parquet` for quick offline testing (`python data_prep.py
/path/to/Lifecycle__PAN.xlsx`), but this is a dev convenience only --
it's not read by the deployed app and doesn't need to be committed.

## Methodology notes & assumptions

- **Data confidence**: flags components with missing survey years, a
  uniform construction year across the whole property (consistent with —
  but not proof of — a system default per the SME notes), and the C-model
  condition-reset pattern for recently-surveyed, short-life equipment.
- **Risk score**: `condition x consequence x safety`, normalised 0-100.
- **Economic tipping point**: replacement cost is annualised via a capital
  recovery factor (discount rate, adjustable); maintenance cost is modelled
  as an escalating percentage of replacement cost. Both curves are shown
  and both assumptions are sliders — treat the output as a directional
  planning tool, not a precise forecast.
- **Scenario engine**: each year, due/overdue assets compete for that
  year's budget by a blended urgency/cost-efficiency score. Unfunded assets
  carry forward with escalated cost and urgency (deferral compounds).
