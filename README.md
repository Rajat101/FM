# Pannawonica Asset Lifecycle & Decision Model

A multi-page Streamlit app built from `Lifecycle_PAN.xlsx` (129,487 tracked
components across 7 Pannawonica portfolios). It cleans the raw lifecycle
export, computes risk scores, economic tipping points, and a maintain /
renew / replace / defer decision for every component, then lets you run
budget what-if scenarios across a 20-year horizon.

## Pages

1. **Home** — portfolio-wide KPIs, CapEx forecast, decision mix, data
   confidence overview.
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

## Setup

```bash
pip install -r requirements.txt
```

The workbook itself is not bundled (it's large) — point `data_prep.py` at
your copy of `Lifecycle_PAN.xlsx` if the path differs, then run:

```bash
python data_prep.py
```

This writes `data/processed.parquet`, which the app reads on every launch.
Re-run it any time the source workbook is updated.

## Run

```bash
streamlit run Home.py
```

Opens at `http://localhost:8501`. Use the sidebar to switch pages and
filter by portfolio / component group.

## Deploying (optional)

Push this folder to a GitHub repo and deploy free on
[Streamlit Community Cloud](https://streamlit.io/cloud) — point it at
`Home.py` as the entry point, and make sure `data/processed.parquet` is
committed (or that `data_prep.py` runs as a build step).

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

See `Pannawonica_Lifecycle_Model_Feature_Plan.md` (shared earlier in this
conversation) for the full feature inventory this app was built from.
