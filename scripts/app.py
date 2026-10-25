"""
Week 2, Step 6 - Chat UI.

A browser chat page on top of scripts/answer.py. It adds no new retrieval or prompt logic:
every question goes through the same answer() function you tested in Step 5.

Run from the repo root (with the rbi-rag environment active):
  streamlit run scripts/app.py
Your browser opens at http://localhost:8501. Stop it with Ctrl+C in the terminal.

Needs: everything answer.py needs (.env with ANTHROPIC_API_KEY, the Chroma store from Step 4),
plus:  pip install streamlit   (written and tested on Streamlit 1.66)
"""
import anthropic
import streamlit as st

import answer as engine          # scripts/answer.py: answer(), make_client(), MODEL, EFFORT, K_PARAS
import qa_log                    # scripts/qa_log.py: one CSV row per question (Step 7)

SETTINGS = {                     # recorded on every log row, so runs with different settings can be compared
    "effort": engine.EFFORT,
    "k_paras": engine.K_PARAS,
    "system_prompt": engine.SYSTEM_PROMPT_FILE.name,
}

NOT_FOUND = "Not found in the provided documents."
EXAMPLES = [                     # three of the Step 5 test questions: direct, calculation, not found
    "What is the maximum LTV for a gold loan of ₹4 lakh?",
    "A house costs ₹9 lakh and stamp duty is ₹50,000. What is the maximum home loan?",
    "What is the minimum CIBIL score for a home loan?",
]

st.set_page_config(page_title="Credit Assist", page_icon="📘", layout="centered")


@st.cache_resource
def get_client() -> anthropic.Anthropic:
    """One API client for the whole session, instead of a new one per question."""
    return engine.make_client()


def render_result(r: dict) -> None:
    """One assistant turn: the answer, then the evidence behind it."""
    if r["answer"].strip().strip('"') == NOT_FOUND:
        # Designed fallback: a refusal should look like a deliberate outcome, not an error
        st.info(f"**{NOT_FOUND}**\n\nThe retrieved RBI paragraphs don't cover this. "
                "Try rephrasing, or check the full Master Direction on rbi.org.in.")
    else:
        st.markdown(r["answer"])
    if r.get("stop_reason") == "max_tokens":
        st.warning("This answer was cut off before it finished. Ask again or narrow the question.")

    with st.expander(f"Sources searched ({len(r['retrieved'])} paragraphs)"):
        st.caption("Paragraphs given to Claude, best match first. The number is retrieval similarity (0–1).")
        for line in r["retrieved"]:
            st.markdown(f"- {line}")
    with st.expander("Exact text Claude was given"):
        st.code(r["documents"], language="xml", wrap_lines=True)

    thinking = f" · {r['thinking_tokens']} thinking" if r.get("thinking_tokens") else ""
    run = f" · log id {r['run_id']}" if r.get("run_id") else ""
    st.caption(f"{r['model']} · {r['total_seconds']}s ({r['retrieval_seconds']}s retrieval) · "
               f"{r['input_tokens']:,} in / {r['output_tokens']:,} out tokens{thinking}{run}")


def save_to_log(fn, *args) -> str:
    """Write one row to logs/qa_log.csv. A logging problem must never block the answer itself."""
    try:
        return fn(*args, "ui", SETTINGS)
    except PermissionError:
        st.warning("Couldn't write to logs/qa_log.csv. Is it open in Excel? Close it so later questions are logged.")
    except Exception as e:
        st.warning(f"Couldn't write to the log: {type(e).__name__}: {e}")
    return ""


def ask(question: str) -> dict | None:
    """Run the pipeline and log it; turn known failures into plain-language messages instead of a traceback."""
    try:
        with st.spinner("Searching the directions and drafting a cited answer…"):
            result = engine.answer(question, get_client())
        result["run_id"] = save_to_log(qa_log.log_result, result)
        return result
    except anthropic.AuthenticationError:
        msg = "The API key was rejected. Check ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID) in .env."
    except anthropic.RateLimitError:
        msg = "Rate limit reached. Wait a minute and ask again."
    except anthropic.APIConnectionError:
        msg = "Couldn't reach the Claude API. Check your internet connection."
    except anthropic.APIStatusError as e:
        msg = f"The Claude API returned an error ({e.status_code}): {e.message}"
    except Exception as e:  # e.g. Chroma store missing: Step 4 not run on this machine
        msg = f"Something went wrong before the answer was generated: {type(e).__name__}: {e}"
    st.error(msg)
    save_to_log(qa_log.log_error, question, msg)
    return None


# ---------- Sidebar ----------
with st.sidebar:
    st.header("Credit Assist")
    st.markdown("Answers questions from three public RBI directions, citing the paragraph:")
    st.markdown("- Credit Facilities, 2025\n- Credit Information Reporting, 2025\n- Credit Risk Management, 2025")
    st.caption(f"Model: {engine.MODEL} · effort {engine.EFFORT} · top {engine.K_PARAS} paragraphs")
    st.caption("Every question is logged to logs/qa_log.csv.")
    if st.button("Clear chat", width="stretch"):
        st.session_state.history = []
        st.rerun()
    st.divider()
    st.caption("Prototype v0. Not legal or regulatory advice. Always verify against the official "
               "RBI document. Uses public RBI documents only; don't enter customer data.")

# ---------- Main page ----------
st.title("📘 Credit Assist")
st.caption("Ask about RBI rules on credit facilities, credit information reporting and credit risk management.")

if "history" not in st.session_state:
    st.session_state.history = []          # list of {"question": str, "result": dict}

for turn in st.session_state.history:      # Streamlit reruns the script on every click; redraw past turns
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        render_result(turn["result"])

picked = None
if not st.session_state.history:
    st.markdown("**Try one:**")
    for i, q in enumerate(EXAMPLES):
        if st.button(q, key=f"ex{i}", width="stretch"):
            picked = q

question = st.chat_input("Ask a question about the RBI credit directions…") or picked
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        result = ask(question)
        if result:
            render_result(result)
            st.session_state.history.append({"question": question, "result": result})
