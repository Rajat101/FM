# FM Asset Excellence

A Sodexo-branded, multi-page Streamlit app that cleans a lifecycle asset
export, surfaces plain-language insights, computes risk scores and economic
tipping points, and lets stakeholders set their own budget/escalation
parameters and watch the 20-year forecast respond live.

**No data is committed to this repo.** The app takes the workbook via an
in-browser file upload and processes it entirely in memory, in your own
session -- nothing is written to disk or shared with anyone else. This is
what lets the repo (and app) be public even though the underlying asset
data is sensitive.

## Pages

1. **Home** — upload the workbook here; insight banner (auto-surfaced
   findings), portfolio KPIs, a live scenario/forecast hero you can tune
   right on the page, and the three "how it works" visuals (lifecycle flow,
   condition decay curve, cost crossover).
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
7. **Recommendations** (new in v1) — set your own life-used and risk
   thresholds (plus an optional budget cap) and every asset is reclassified
   live into Maintain / Plan Renewal / Replace Now / Overdue / Defer,
   each shown with count, total cost, and a browsable table. Includes a
   PDF export: KPIs, insights, and per-category counts/costs plus a
   top-10-by-urgency sample -- never a full data dump.

## v1 changelog

- Fixed axis labels clipped across nearly every chart (condition
  distribution, risk score distribution, top component groups, portfolio
  stacked, deferred exposure) -- root cause was a forced zero left margin;
  fixed centrally with `automargin=True` in the shared chart helper.
- Removed Plotly's toolbar (the black bar) from every chart.
- Added a caption clarifying OpEx's real scale (only 281 of 129,487 rows
  are tagged Opex) instead of leaving it looking broken.
- Added the Recommendations page and PDF export (see above).
- Fixed a pandas `iterrows()` dtype bug that showed asset counts as
  "3,422.0" instead of "3,422" in KPI cards and the PDF table.
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
