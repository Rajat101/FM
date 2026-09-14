import streamlit as st
import pandas as pd

from common import inject_css, plotly_template, render_header, money, COLORS
import jundu_common as jc
import jundu_ai as ja

st.set_page_config(page_title="Jundunmunnah AI Assistant", layout="wide")
inject_css()
plotly_template()

render_header("Jundunmunnah AI Assistant")
st.caption("Ask questions about the refurb model in plain English \u2014 with your own OpenAI API key")

st.markdown(
    '<div class="panel-note"><b>Your API key is never stored.</b> It lives only in this browser session\'s '
    'memory and is gone the moment you reload the page or close the tab \u2014 it is never written to disk, '
    'never logged, and never saved anywhere in this app. Questions and a summary of your data are sent to '
    'OpenAI to generate answers; do not use this with data you are not comfortable sharing with a third '
    'party. This uses the OpenAI API, which is billed separately from a ChatGPT subscription \u2014 you\'ll '
    'need an API key from platform.openai.com with some credit on it.</div>',
    unsafe_allow_html=True,
)

# ============================================================================ DATA SOURCE
st.markdown("##### 1. Load the Jundunmunnah data")
shared_bytes = st.session_state.get("jundu_uploaded_bytes")
use_shared = False
if shared_bytes is not None:
    use_shared = st.checkbox("Use the file already uploaded on the Jundunmunnah Refurb Model page", value=True)

if use_shared:
    file_bytes = shared_bytes
else:
    uploaded = st.file_uploader("Upload a Jundunmunnah-format LCCM workbook (.xlsx)", type=["xlsx"], key="ai_page_upload")
    file_bytes = uploaded.getvalue() if uploaded else None

if file_bytes is None:
    st.info("Upload a workbook (or upload one on the Jundunmunnah Refurb Model page first) to begin.")
    st.stop()


@st.cache_data(show_spinner="Processing workbook\u2026")
def process_for_ai(file_bytes):
    import io
    buf = io.BytesIO(file_bytes)
    df = jc.load_jundu_workbook(buf)
    buf.seek(0)
    missing_df = jc.load_missing_cost_inputs(buf)
    df, _ = jc.flag_partial_cost_items(df, missing_df)
    df = jc.compute_confidence(df)
    df = jc.compute_lifecycle_stage(df, view_year=jc.CONSTRUCTION_YEAR)
    df = jc.compute_recommendation(df)
    return df


try:
    df = process_for_ai(file_bytes)
except Exception as e:
    st.error(f"Couldn't process this file: {e}")
    st.stop()

st.success(f"Loaded {len(df):,} assets. Ready to ask questions.")

# ============================================================================ API KEY
st.markdown("##### 2. Paste your OpenAI API key")
api_key = st.text_input(
    "OpenAI API key", type="password", key="openai_api_key_input",
    help="Starts with 'sk-'. Get one at platform.openai.com/api-keys. Never stored beyond this session.",
)
model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"], index=0,
                      help="gpt-4o-mini is the cheapest option and works well for this.")

if not api_key:
    st.info("Paste your API key above to enable the assistant tabs below.")
    st.stop()

try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
except ImportError:
    st.error("The `openai` package isn't installed in this environment.")
    st.stop()

st.markdown("---")

# ============================================================================ TWO MODES
tab1, tab2 = st.tabs(["\U0001F4AC Simple Q&A", "\u2699\ufe0f Function-Calling Assistant"])

# ---------------------------------------------------------------- TAB 1: SIMPLE Q&A
with tab1:
    st.caption(
        "Answers questions using a summary of the current data only \u2014 no live recalculation. "
        "Good for \u201chow many\u201d and \u201cwhat's the status of\u201d questions. For \u201cwhat if\u201d "
        "questions with new parameters, use the Function-Calling tab instead."
    )

    ce_totals = jc.cost_engine_breakdown(df)
    rec_summary = df.groupby("recommendation").agg(count=("Package Cost", "count"), cost=("Package Cost", "sum"))
    rec_summary = rec_summary.reindex(jc.RECOMMENDATION_ORDER).dropna(how="all")
    conf_summary = df.groupby("confidence").agg(count=("Package Cost", "count"), cost=("Package Cost", "sum"))
    vision_status = jc.vision_point_status(df)
    data_summary = ja.build_data_summary(df, ce_totals, rec_summary, conf_summary, vision_status)

    with st.expander("See exactly what data the AI can see for this mode"):
        st.code(data_summary, language=None)

    if "qa_history" not in st.session_state:
        st.session_state.qa_history = []

    for msg in st.session_state.qa_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    qa_question = st.chat_input("Ask a question about the data\u2026", key="qa_chat_input")
    if qa_question:
        st.session_state.qa_history.append({"role": "user", "content": qa_question})
        with st.chat_message("user"):
            st.markdown(qa_question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking\u2026"):
                try:
                    answer = ja.ask_simple_qa(client, model, data_summary, st.session_state.qa_history[:-1], qa_question)
                except Exception as e:
                    answer = f"Error calling OpenAI: {e}"
            st.markdown(answer)
        st.session_state.qa_history.append({"role": "assistant", "content": answer})

    if st.session_state.qa_history and st.button("Clear Q&A conversation", key="clear_qa"):
        st.session_state.qa_history = []
        st.rerun()

# ---------------------------------------------------------------- TAB 2: FUNCTION-CALLING
with tab2:
    st.caption(
        "The assistant can run the real budget scenario, TCO, and recommendation calculations with "
        "parameters it pulls from your question \u2014 every answer is backed by an actual calculation, "
        "not a guess. Try: \u201cWhat happens if the budget is $2M growing 3% a year over 25 years?\u201d"
    )

    if "fc_history" not in st.session_state:
        st.session_state.fc_history = []
    if "fc_tool_log" not in st.session_state:
        st.session_state.fc_tool_log = []

    for msg in st.session_state.fc_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    fc_question = st.chat_input("Ask a question, or set parameters in plain English\u2026", key="fc_chat_input")
    if fc_question:
        with st.chat_message("user"):
            st.markdown(fc_question)
        with st.chat_message("assistant"):
            with st.spinner("Calculating\u2026"):
                try:
                    answer, new_history, tool_calls_made = ja.run_function_calling_chat(
                        client, model, df, st.session_state.fc_history, fc_question,
                    )
                    st.session_state.fc_history = new_history
                    st.session_state.fc_tool_log.extend(tool_calls_made)
                except Exception as e:
                    answer = f"Error calling OpenAI: {e}"
                    st.session_state.fc_history.append({"role": "user", "content": fc_question})
                    st.session_state.fc_history.append({"role": "assistant", "content": answer})
            st.markdown(answer)

    if st.session_state.fc_tool_log:
        with st.expander(f"See the {len(st.session_state.fc_tool_log)} real calculation(s) run so far"):
            for i, call in enumerate(st.session_state.fc_tool_log, 1):
                st.markdown(f"**{i}. `{call['name']}`** called with `{call['args']}`")
                st.json(call["result"])

    if st.session_state.fc_history and st.button("Clear Function-Calling conversation", key="clear_fc"):
        st.session_state.fc_history = []
        st.session_state.fc_tool_log = []
        st.rerun()
