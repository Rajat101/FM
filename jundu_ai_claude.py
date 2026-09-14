# -*- coding: utf-8 -*-
"""
Claude (Anthropic) version of the Jundunmunnah AI assistant.

Reuses everything provider-agnostic from jundu_ai.py -- the tool executor functions
(TOOL_DISPATCH), the data summary builder, and the chart builder are pure Python
operating on the dataframe, with no OpenAI-specific code in them. Only the request/
response shape to the AI provider differs: Claude's Messages API structures tool
definitions, tool calls, and tool results differently from OpenAI's Chat Completions
API, so that plumbing is rewritten here rather than shared.
"""
import json

import jundu_common as jc
from jundu_ai import TOOL_DISPATCH, build_data_summary, build_chart_from_tool_call  # noqa: F401 (re-exported)

DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1500


# ============================================================================ SIMPLE Q&A
SIMPLE_QA_SYSTEM_PROMPT = (
    "You are an assistant answering questions about the Jundunmunnah refurbishment asset register, "
    "using ONLY the data summary provided below. Do not invent numbers that aren't in the summary. "
    "If a question needs a live calculation with parameters not shown in the summary (like 'what if the "
    "budget were $2M'), say so plainly and suggest the user try the Function-Calling Assistant tab instead, "
    "which can run real calculations. All figures here are transparent formula-based calculations "
    "(escalation, capital recovery factor, rule-based staging) -- not machine learning or predictions.\n\n"
    "DATA SUMMARY:\n{summary}"
)


def ask_simple_qa_claude(client, model: str, summary: str, history: list, question: str) -> str:
    """One-shot Q&A grounded in the static data summary. No tool calls, no live computation."""
    messages = list(history) + [{"role": "user", "content": question}]
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SIMPLE_QA_SYSTEM_PROMPT.format(summary=summary),
        messages=messages,
    )
    text_blocks = [b.text for b in resp.content if b.type == "text"]
    return "\n".join(text_blocks) if text_blocks else "(no response)"


# ============================================================================ FUNCTION-CALLING (Claude tool-use)
def _to_claude_tool_schemas():
    """Converts jundu_ai's OpenAI-format TOOL_SCHEMAS into Claude's input_schema format."""
    from jundu_ai import TOOL_SCHEMAS as OPENAI_SCHEMAS
    claude_tools = []
    for t in OPENAI_SCHEMAS:
        fn = t["function"]
        claude_tools.append({
            "name": fn["name"],
            "description": fn["description"],
            "input_schema": fn["parameters"],
        })
    return claude_tools


CLAUDE_TOOL_SCHEMAS = _to_claude_tool_schemas()

FUNCTION_CALLING_SYSTEM_PROMPT = (
    "You are an assistant with the ability to run real calculations on the Jundunmunnah refurbishment "
    "asset register via the tools provided. Always use a tool to get numbers rather than guessing or "
    "recalling from memory -- every answer must be backed by an actual tool call. When a user asks a "
    "'what if' question with parameters (budget, growth, escalation, discount rate), call the relevant "
    "tool with those exact parameters. All calculations are transparent formulas (escalation, capital "
    "recovery factor, rule-based staging) -- there is no machine learning involved. After getting a tool "
    "result, explain it in plain, concise English."
)


def run_function_calling_chat_claude(client, model: str, df, history: list, question: str,
                                      max_rounds: int = 4) -> tuple:
    """
    Runs Claude's tool-use loop for one user question, executing the same real jundu_common.py
    calculations via TOOL_DISPATCH as the OpenAI version. Returns (final_answer_text,
    updated_history, tool_calls_made) -- same return shape as jundu_ai.run_function_calling_chat,
    so the page code can treat both providers identically.
    """
    messages = list(history) + [{"role": "user", "content": question}]
    tool_calls_made = []

    for _ in range(max_rounds):
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=FUNCTION_CALLING_SYSTEM_PROMPT,
            messages=messages,
            tools=CLAUDE_TOOL_SCHEMAS,
        )

        if resp.stop_reason != "tool_use":
            text_blocks = [b.text for b in resp.content if b.type == "text"]
            final_text = "\n".join(text_blocks) if text_blocks else "(no response)"
            new_history = history + [
                {"role": "user", "content": question},
                {"role": "assistant", "content": final_text},
            ]
            return final_text, new_history, tool_calls_made

        # Assistant's turn (may include text + one or more tool_use blocks) goes back into the
        # conversation verbatim so Claude keeps the full reasoning context on the next round.
        assistant_content = [
            {"type": b.type, **({"text": b.text} if b.type == "text" else
                                 {"id": b.id, "name": b.name, "input": b.input})}
            for b in resp.content
        ]
        messages.append({"role": "assistant", "content": assistant_content})

        tool_result_blocks = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            fn_name = b.name
            args = b.input or {}
            fn = TOOL_DISPATCH.get(fn_name)
            if fn is None:
                result = {"error": f"Unknown tool: {fn_name}"}
            else:
                try:
                    result = fn(df, **args)
                except Exception as e:
                    result = {"error": str(e)}
            chart_type = result.pop("_chart_type", None) if isinstance(result, dict) else None
            chart_data = result.pop("_chart_data", None) if isinstance(result, dict) else None
            tool_calls_made.append({
                "name": fn_name, "args": args, "result": result,
                "chart_type": chart_type, "chart_data": chart_data,
            })
            tool_result_blocks.append({
                "type": "tool_result", "tool_use_id": b.id,
                "content": json.dumps(result, default=str),
            })
        messages.append({"role": "user", "content": tool_result_blocks})

    final_text = "I made several calculations but couldn't finish reasoning about them in time. Try a simpler question."
    new_history = history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": final_text},
    ]
    return final_text, new_history, tool_calls_made
