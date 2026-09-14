# -*- coding: utf-8 -*-
"""
AI assistant layer for the Jundunmunnah refurb model.

Two modes:
  - Simple Q&A: the model answers from a text summary of the current data. No live
    computation -- just reads and explains numbers that already exist.
  - Function-calling: the model can invoke the *real* jundu_common.py functions with
    parameters it extracts from the user's question, so answers are always backed by
    an actual calculation, never invented. This is what makes "set the budget to $2M
    and tell me what happens" possible.

The user's OpenAI API key is never written to disk, never logged, and lives only in
Streamlit's session_state for the current browser session -- gone on reload.
"""
import json
import numpy as np
import pandas as pd

import jundu_common as jc

DEFAULT_MODEL = "gpt-4o-mini"


# ============================================================================ CONTEXT / SUMMARY (Q&A mode)
def build_data_summary(df: pd.DataFrame, ce_totals: dict, rec_summary: pd.DataFrame,
                        conf_summary: pd.DataFrame, vision_status: list) -> str:
    """A compact text summary of the current data -- sent as context for simple Q&A. No row-level data."""
    lines = [
        f"JUNDUNMUNNAH REFURBISHMENT DATA SUMMARY (as of {jc.CONSTRUCTION_YEAR})",
        f"Total assets: {len(df)}",
        f"Assets with base life set: {df['has_base_life'].sum()} of {len(df)}",
        f"Total package cost (today's dollars): {jc.money(df['Package Cost'].sum())}",
        f"Overdue or renewal-due assets: {(df['lcm_stage'].isin(['Overdue', 'Renewal Due'])).sum()}",
        "",
        "Cost engine breakdown:",
    ]
    for k, v in ce_totals.items():
        lines.append(f"  {k}: {jc.money(v)}")
    lines.append("")
    lines.append("Data confidence breakdown:")
    for idx, row in conf_summary.iterrows():
        lines.append(f"  {idx}: {int(row['count'])} assets, {jc.money(row['cost'])}")
    lines.append("")
    lines.append("Recommendation breakdown:")
    for idx, row in rec_summary.iterrows():
        lines.append(f"  {idx}: {int(row['count'])} assets, {jc.money(row['cost'])}")
    lines.append("")
    lines.append("Vision-text item tracker:")
    for v in vision_status:
        lines.append(f"  {v['item']} ({v['vision_text']}): {v['status']} \u2014 {v['detail']}")
    lines.append("")
    lines.append("Asset groups present: " + ", ".join(sorted(df["Asset Group"].dropna().unique())))
    return "\n".join(lines)


SIMPLE_QA_SYSTEM_PROMPT = (
    "You are an assistant answering questions about the Jundunmunnah refurbishment asset register, "
    "using ONLY the data summary provided below. Do not invent numbers that aren't in the summary. "
    "If a question needs a live calculation with parameters not shown in the summary (like 'what if the "
    "budget were $2M'), say so plainly and suggest the user try the Function-Calling Assistant tab instead, "
    "which can run real calculations. All figures here are transparent formula-based calculations "
    "(escalation, capital recovery factor, rule-based staging) -- not machine learning or predictions.\n\n"
    "DATA SUMMARY:\n{summary}"
)


def ask_simple_qa(client, model: str, summary: str, history: list, question: str) -> str:
    """One-shot Q&A grounded in the static data summary. No tool calls, no live computation."""
    messages = [{"role": "system", "content": SIMPLE_QA_SYSTEM_PROMPT.format(summary=summary)}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
    return resp.choices[0].message.content


# ============================================================================ TOOLS (function-calling mode)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_scenario",
            "description": "Run the real budget scenario simulation over the forecast horizon and return "
                            "the resulting spend, backlog, and unfunded-events counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "annual_budget": {"type": "number", "description": "Starting annual budget in dollars."},
                    "budget_growth_pct": {"type": "number", "description": "Annual budget growth, as a percent (e.g. 2 for 2%)."},
                    "deferral_escalation_pct": {"type": "number", "description": "Annual cost escalation for unfunded/deferred items, as a percent."},
                    "cost_escalation_pct": {"type": "number", "description": "Annual replacement-cost escalation used to build the cycle events, as a percent."},
                    "horizon_years": {"type": "integer", "description": "How many years from now to simulate."},
                },
                "required": ["annual_budget", "budget_growth_pct", "deferral_escalation_pct", "cost_escalation_pct", "horizon_years"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_tco_summary",
            "description": "Compute total nominal cost at renewal, present value, and equivalent annual "
                            "cost (EAC) across all assets with a base life set, using the given discount "
                            "and escalation rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "discount_rate_pct": {"type": "number", "description": "Discount rate as a percent (e.g. 7 for 7%)."},
                    "cost_escalation_pct": {"type": "number", "description": "Cost escalation rate as a percent."},
                },
                "required": ["discount_rate_pct", "cost_escalation_pct"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendation_breakdown",
            "description": "Get the current count and total cost of assets in each recommendation "
                            "category (Overdue, Renewal Due, Needs Base Life, Needs Cost Confirmation, "
                            "Mid-Life Monitor, New Monitor).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_confidence_breakdown",
            "description": "Get the current count and total cost of assets in each data-confidence bucket.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vision_tracker",
            "description": "Get the status of each vision-text item (e.g. Chair, Bed and Mattress, "
                            "Exhaust Fan, Painting, Split System AC, Hot Water Unit) against the live data.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "filter_assets",
            "description": "Get a count, total cost, and a short sample list of assets matching filters. "
                            "Use this to answer questions like 'how many overdue assets are in HVAC' or "
                            "'what are the assets needing cost confirmation'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_group": {"type": "string", "description": "Filter to this Asset Group (e.g. 'HVAC', 'Electrical'). Omit for all."},
                    "recommendation": {"type": "string", "description": "Filter to this recommendation category. Omit for all."},
                    "confidence": {"type": "string", "description": "Filter to assets whose confidence bucket contains this text (e.g. 'Ready', 'Not Ready'). Omit for all."},
                },
                "required": [],
            },
        },
    },
]


def _tool_run_scenario(df, annual_budget, budget_growth_pct, deferral_escalation_pct,
                        cost_escalation_pct, horizon_years):
    horizon_end_year = jc.CONSTRUCTION_YEAR + int(horizon_years)
    df2 = jc.compute_escalated_cost(df, cost_escalation_pct / 100, view_year=jc.CONSTRUCTION_YEAR)
    events = jc.build_cycle_events(df2, horizon_end_year, cost_escalation_pct / 100, view_year=jc.CONSTRUCTION_YEAR)
    if len(events) == 0:
        return {"error": "No assets have a base life set yet, so no scenario can be simulated."}
    results = jc.run_jundu_scenario(events, jc.CONSTRUCTION_YEAR, horizon_end_year, annual_budget,
                                     budget_growth_pct / 100, deferral_escalation_pct / 100)
    return {
        "total_spend": round(float(results["spend"].sum()), 2),
        "backlog_value_at_end": round(float(results.iloc[-1]["backlog_value"]), 2),
        "events_never_funded_at_end": int(results.iloc[-1]["assets_backlog"]),
        "horizon_end_year": horizon_end_year,
        "first_5_years": results.head(5)[["year", "budget", "spend", "backlog_value"]].round(2).to_dict("records"),
        "last_5_years": results.tail(5)[["year", "budget", "spend", "backlog_value"]].round(2).to_dict("records"),
    }


def _tool_compute_tco_summary(df, discount_rate_pct, cost_escalation_pct):
    df2 = jc.compute_escalated_cost(df, cost_escalation_pct / 100, view_year=jc.CONSTRUCTION_YEAR)
    df2 = jc.compute_tco(df2, discount_rate_pct / 100, cost_escalation_pct / 100, view_year=jc.CONSTRUCTION_YEAR)
    valid = df2[df2["has_base_life"]]
    if len(valid) == 0:
        return {"error": "No assets have a base life set yet."}
    return {
        "nominal_cost_at_renewal_total": round(float(valid["cost_at_renewal"].sum()), 2),
        "present_value_total": round(float(valid["pv_at_renewal"].sum()), 2),
        "eac_of_todays_cost_total": round(float(valid["eac_today"].sum()), 2),
        "assets_included": int(len(valid)),
    }


def _tool_get_recommendation_breakdown(df):
    rec_summary = df.groupby("recommendation").agg(count=("Package Cost", "count"), cost=("Package Cost", "sum"))
    rec_summary = rec_summary.reindex(jc.RECOMMENDATION_ORDER).dropna(how="all")
    return {idx: {"count": int(r["count"]), "cost": round(float(r["cost"]), 2)} for idx, r in rec_summary.iterrows()}


def _tool_get_confidence_breakdown(df):
    conf_summary = df.groupby("confidence").agg(count=("Package Cost", "count"), cost=("Package Cost", "sum"))
    return {idx: {"count": int(r["count"]), "cost": round(float(r["cost"]), 2)} for idx, r in conf_summary.iterrows()}


def _tool_get_vision_tracker(df):
    return jc.vision_point_status(df)


def _tool_filter_assets(df, asset_group=None, recommendation=None, confidence=None):
    subset = df
    if asset_group:
        subset = subset[subset["Asset Group"].str.contains(asset_group, case=False, na=False)]
    if recommendation:
        subset = subset[subset["recommendation"].str.contains(recommendation, case=False, na=False)]
    if confidence:
        subset = subset[subset["confidence"].str.contains(confidence, case=False, na=False)]
    sample = subset[["Asset Group", "Asset / Component", "Package Cost", "recommendation", "confidence"]].head(15)
    return {
        "matching_count": int(len(subset)),
        "matching_total_cost": round(float(subset["Package Cost"].sum()), 2),
        "sample_rows": sample.round(2).to_dict("records"),
    }


TOOL_DISPATCH = {
    "run_scenario": _tool_run_scenario,
    "compute_tco_summary": _tool_compute_tco_summary,
    "get_recommendation_breakdown": _tool_get_recommendation_breakdown,
    "get_confidence_breakdown": _tool_get_confidence_breakdown,
    "get_vision_tracker": _tool_get_vision_tracker,
    "filter_assets": _tool_filter_assets,
}

FUNCTION_CALLING_SYSTEM_PROMPT = (
    "You are an assistant with the ability to run real calculations on the Jundunmunnah refurbishment "
    "asset register via the tools provided. Always use a tool to get numbers rather than guessing or "
    "recalling from memory -- every answer must be backed by an actual tool call. When a user asks a "
    "'what if' question with parameters (budget, growth, escalation, discount rate), call the relevant "
    "tool with those exact parameters. All calculations are transparent formulas (escalation, capital "
    "recovery factor, rule-based staging) -- there is no machine learning involved. After getting a tool "
    "result, explain it in plain, concise English."
)


def run_function_calling_chat(client, model: str, df: pd.DataFrame, history: list, question: str,
                               max_rounds: int = 4) -> tuple:
    """
    Runs the OpenAI tool-calling loop for one user question, executing real jundu_common.py
    calculations via TOOL_DISPATCH. Returns (final_answer_text, updated_history, tool_calls_made).
    """
    messages = [{"role": "system", "content": FUNCTION_CALLING_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    tool_calls_made = []
    for _ in range(max_rounds):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto", temperature=0.1,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            final_text = msg.content or "(no response)"
            new_history = history + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": final_text},
            ]
            return final_text, new_history, tool_calls_made

        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]})

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            fn = TOOL_DISPATCH.get(fn_name)
            if fn is None:
                result = {"error": f"Unknown tool: {fn_name}"}
            else:
                try:
                    result = fn(df, **args)
                except Exception as e:
                    result = {"error": str(e)}
            tool_calls_made.append({"name": fn_name, "args": args, "result": result})
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

    # Ran out of rounds -- return whatever we have.
    final_text = "I made several calculations but couldn't finish reasoning about them in time. Try a simpler question."
    new_history = history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": final_text},
    ]
    return final_text, new_history, tool_calls_made
