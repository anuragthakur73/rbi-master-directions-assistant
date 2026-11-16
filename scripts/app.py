"""
Credit Assist - chat UI (Week 2, Step 6; Week 5: fallbacks, trust features, usage caps, deploy).

A browser chat page on top of scripts/answer.py. Retrieval and the prompt live in answer.py;
this file only decides what the user sees, what is checked before and after each answer,
and what is logged.

Run locally from the repo root (with the rbi-rag environment active):
  streamlit run scripts/app.py
Deployed: Streamlit Community Cloud runs the same file (see docs/week5_plan.md).

Settings, read from .env locally or from the app's Secrets on Streamlit Community Cloud
(root-level secrets become environment variables there):
  ANTHROPIC_API_KEY        required
  ANTHROPIC_WORKSPACE_ID   only if your key is not tied to one workspace
  DAILY_QUESTION_LIMIT     questions per day across all users (default 200)
  SESSION_QUESTION_LIMIT   questions per browser session (default 20)
  APP_PASSCODE             optional: if set, visitors must enter it before asking anything
  ADMIN_KEY                optional: if set, entering it in the sidebar unlocks log downloads
"""
import hmac
import os

import anthropic
import streamlit as st
from dotenv import load_dotenv

import answer as engine          # scripts/answer.py: answer(), make_client(), MODEL, EFFORT, K_PARAS
import guards                    # scripts/guards.py: personal-data check, answer review, usage counter
import qa_log                    # scripts/qa_log.py: one CSV row per question, plus feedback


# Re-read .env on every page load, so a changed limit applies without restarting the app.
# On Streamlit Cloud there is no .env file; settings come from Secrets and this does nothing.
load_dotenv(engine.ROOT / ".env", override=True)


def setting(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


DAILY_LIMIT = int(setting("DAILY_QUESTION_LIMIT", "200"))
SESSION_LIMIT = int(setting("SESSION_QUESTION_LIMIT", "20"))
PASSCODE = setting("APP_PASSCODE")
ADMIN_KEY = setting("ADMIN_KEY")

SETTINGS = {                     # recorded on every log row, so runs with different settings can be compared
    "effort": engine.EFFORT,
    "k_paras": engine.K_PARAS,
    "system_prompt": engine.SYSTEM_PROMPT_FILE.name,
}

NOT_FOUND = guards.NOT_FOUND
EXAMPLES = [                     # three of the Step 5 test questions: direct, calculation, not found
    "What is the maximum LTV for a gold loan of ₹4 lakh?",
    "A house costs ₹9 lakh and stamp duty is ₹50,000. What is the maximum home loan?",
    "What is the minimum CIBIL score for a home loan?",
]
DISCLAIMER = ("For reference only, not legal or regulatory advice. Always check the official RBI "
              "document before acting. Public RBI documents only: don't enter customer data.")

st.set_page_config(page_title="Credit Assist", page_icon="📘", layout="centered")


# ---------- Shared resources (one per running app, not per visitor) ----------
@st.cache_resource(show_spinner="Preparing the document index. The first start takes about a minute…")
def prepare_index() -> bool:
    """Build the Chroma store from data/processed/chunks.jsonl if this machine doesn't have it yet
    (always the case on a fresh cloud deploy), and load the embedding model once."""
    import embed_store
    built = embed_store.ensure_store()
    embed_store.get_model()
    return built


@st.cache_resource
def get_client() -> anthropic.Anthropic:
    """One API client for the app. A 60 s timeout so a stuck call ends in a message, not a spinner."""
    return engine.make_client().with_options(timeout=60.0, max_retries=2)


@st.cache_resource
def usage() -> guards.UsageCounter:
    return guards.UsageCounter(DAILY_LIMIT)


# ---------- Logging (a logging problem must never block the answer) ----------
def safe_log(fn, *args) -> str:
    try:
        return fn(*args)
    except PermissionError:
        st.warning("Couldn't write to the log file. Is it open in Excel? Close it so later questions are logged.")
    except Exception as e:
        st.warning(f"Couldn't write to the log: {type(e).__name__}: {e}")
    return ""


def save_feedback(run_id: str, question: str, comment: str = "") -> None:
    """Called when a thumbs button changes, and when a comment is sent."""
    rating = st.session_state.get(f"fb_{run_id}")
    safe_log(qa_log.log_feedback, run_id, question, rating, comment)
    if comment:
        st.toast("Thanks, comment saved.")
    elif rating is not None:
        st.toast("Thanks, feedback saved.")


# ---------- Rendering ----------
def render_result(r: dict) -> None:
    """One assistant turn: the answer, any warning about it, the paragraphs it cites, and the evidence."""
    review = r.get("review") or guards.review_answer(r["answer"], r.get("excerpts", []))
    if review["kind"] == "refusal":
        # Designed fallback: a refusal should look like a deliberate outcome, not an error
        extra = r["answer"].strip().strip('"')[len(NOT_FOUND):].strip()
        st.info(f"**I couldn't find this in the loaded RBI directions.**\n\n{extra}\n\n"
                "Try rephrasing, or check the list of loaded directions in the sidebar. "
                "Questions about other directions, live rates or individual cases are outside this tool's scope.")
    else:
        st.markdown(r["answer"])
        if review["kind"] in ("unretrieved", "no_citation"):
            st.warning(review["message"], icon="⚠️")
        elif review["kind"] == "clarify":
            st.caption(review["message"])
    if r.get("stop_reason") == "max_tokens":
        st.warning("This answer was cut off before it finished. Ask again or narrow the question.")

    if review["cited"]:
        st.markdown("**Cited paragraphs** (open to read the RBI text)")
        for ex in review["cited"]:
            with st.expander(f"📄 {ex['doc']}, {ex['label']} · pages {ex['pages']}"):
                st.caption(f"{ex['title']} · updated as on {ex['updated']}")
                st.text(ex["text"])

    with st.expander(f"All paragraphs searched ({len(r['retrieved'])})"):
        st.caption("Paragraphs given to Claude, best match first. The number is retrieval similarity (0–1).")
        for line in r["retrieved"]:
            st.markdown(f"- {line}")

    thinking = f" · {r['thinking_tokens']} thinking" if r.get("thinking_tokens") else ""
    st.caption(f"{r['model']} · {r['total_seconds']}s · "
               f"{r['input_tokens']:,} in / {r['output_tokens']:,} out tokens{thinking}")

    if r.get("run_id"):
        st.feedback("thumbs", key=f"fb_{r['run_id']}", on_change=save_feedback,
                    args=(r["run_id"], r["question"]))
        if st.session_state.get(f"fb_{r['run_id']}") == 0:
            saved_key = f"fbc_saved_{r['run_id']}"
            if st.session_state.get(saved_key):
                st.caption("✅ Comment saved. Thank you.")
            else:
                # A form with an explicit button: a plain text box only saves on Enter, which testers miss
                with st.form(key=f"fbf_{r['run_id']}", border=False):
                    comment = st.text_input("What was wrong? (optional, no customer data)")
                    if st.form_submit_button("Send comment") and comment.strip():
                        if guards.find_personal_data(comment):
                            st.error("Not saved: the comment seems to contain personal data. Remove it and send again.")
                        else:
                            save_feedback(r["run_id"], r["question"], comment)
                            st.session_state[saved_key] = True
                            st.rerun()


# ---------- One question ----------
def ask(question: str) -> dict | None:
    """Check the question, run the pipeline, review and log the answer.
    Every failure ends in a plain-language message, never a traceback or a blank screen."""
    question = question.strip()
    if len(question) > guards.MAX_QUESTION_CHARS:
        st.warning(f"Please keep questions under {guards.MAX_QUESTION_CHARS} characters "
                   f"(this one is {len(question)}). Ask about one rule at a time.")
        return None

    pii = guards.find_personal_data(question)
    if pii:
        st.error(f"**Not sent.** Your question seems to contain personal data ({', '.join(pii)}). This tool answers from "
                 "public RBI rules only and never needs customer details. Remove them and ask again.\n\n"
                 "If it's an amount, write it with commas or in lakh/crore (e.g. ₹25,00,000 or ₹25 lakh).")
        safe_log(qa_log.log_blocked, guards.redact(question), "possible personal data: " + ", ".join(pii),
                 "ui", SETTINGS)
        return None

    if st.session_state.asked >= SESSION_LIMIT:
        st.warning(f"You've reached this session's limit of {SESSION_LIMIT} questions. "
                   "It keeps the public demo affordable. Come back later.")
        return None
    if not usage().take():
        st.warning("The demo has reached today's question limit. Please try again tomorrow.")
        safe_log(qa_log.log_blocked, question, "daily limit reached", "ui", SETTINGS)
        return None
    st.session_state.asked += 1

    try:
        with st.spinner("Searching the directions and drafting a cited answer…"):
            result = engine.answer(question, get_client())
        result["review"] = guards.review_answer(result["answer"], result.get("excerpts", []))
        result["run_id"] = safe_log(qa_log.log_result, result, "ui", SETTINGS)
        st.session_state.retry = None
        return result
    except anthropic.AuthenticationError:
        msg, detail = "The service isn't set up correctly right now (API key rejected).", "auth"
    except anthropic.RateLimitError:
        msg, detail = "Too many requests at the moment. Wait a minute and try again.", "rate_limit"
    except anthropic.APITimeoutError:
        msg, detail = "Claude took too long to respond. Please try again.", "timeout"
    except anthropic.APIConnectionError:
        msg, detail = "Couldn't reach the Claude API. Check your connection and try again.", "connection"
    except anthropic.APIStatusError as e:
        busy = e.status_code == 529 or e.status_code >= 500
        msg = ("Claude is busy right now. Please try again in a moment." if busy
               else "The request was rejected by the Claude API.")
        detail = f"status {e.status_code}: {e.message}"
    except Exception as e:  # e.g. the document index failed to load
        msg, detail = "Something went wrong before the answer was generated.", f"{type(e).__name__}: {e}"
    st.session_state.retry = question      # shown with a Try again button after the rerun
    st.session_state.error = msg
    safe_log(qa_log.log_error, question, detail, "ui", SETTINGS)
    return None


# ---------- Passcode gate (only if APP_PASSCODE is set) ----------
if "asked" not in st.session_state:
    st.session_state.update(asked=0, history=[], retry=None, error="", authed=not PASSCODE)

if not st.session_state.authed:
    st.title("📘 Credit Assist")
    code = st.text_input("This demo is for invited testers. Enter the passcode:", type="password")
    if code and hmac.compare_digest(code.encode(), PASSCODE.encode()):
        st.session_state.authed = True
        st.rerun()
    elif code:
        st.error("That passcode isn't right.")
    st.stop()

try:
    prepare_index()
except Exception as e:
    st.error("The document index couldn't be loaded, so questions can't be answered right now. "
             f"({type(e).__name__}: {e})")
    st.stop()

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Credit Assist")
    st.markdown("**Loaded RBI directions** (public documents, rbi.org.in):")
    sources = {}
    for c in engine.load_chunks():
        sources.setdefault(c["source"], c)
    for src, c in sources.items():
        st.markdown(f"- **{engine.SHORT_NAMES.get(src, src)}**: {c['title']}  \n"
                    f"  <small>{c['reference']} · updated as on {c['updated_as_on']}</small>",
                    unsafe_allow_html=True)
    st.caption("Anything outside these three directions gets a \"not found\" reply. "
               "RBI amends directions from time to time; the dates above show what the answers reflect.")
    st.caption(f"Model: {engine.MODEL} · top {engine.K_PARAS} paragraphs · "
               f"{SESSION_LIMIT - st.session_state.asked} of {SESSION_LIMIT} questions left this session")
    if st.button("Clear chat", width="stretch"):
        st.session_state.history = []
        st.session_state.retry = None
        st.rerun()
    st.divider()
    st.caption("Questions and 👍/👎 ratings are logged (without personal data) to improve the tool.")
    if ADMIN_KEY:
        with st.expander("Owner"):
            key = st.text_input("Admin key", type="password", key="admin_key")
            if key and hmac.compare_digest(key.encode(), ADMIN_KEY.encode()):
                st.caption(f"Today: {DAILY_LIMIT - usage().remaining()} of {DAILY_LIMIT} questions used.")
                for path in (qa_log.LOG_FILE, qa_log.FEEDBACK_FILE):
                    if path.exists():
                        st.download_button(f"Download {path.name}", path.read_bytes(), file_name=path.name,
                                           mime="text/csv", width="stretch")
                st.caption("Cloud logs are lost when the app restarts or sleeps. Download them after each test session.")

# ---------- Main page ----------
st.title("📘 Credit Assist")
st.caption("Ask about RBI rules on credit facilities, credit information reporting and credit risk management. "
           "Every answer cites the paragraph it comes from.")
st.info(DISCLAIMER, icon="ℹ️")

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
if st.session_state.retry:                 # the last question failed: keep it on screen with a retry button
    with st.chat_message("user"):
        st.markdown(st.session_state.retry)
    with st.chat_message("assistant"):
        st.error(f"{st.session_state.error}\n\nYour question wasn't lost.", icon="⚠️")
        if st.button("🔁 Try again", key="retry_btn"):
            picked = st.session_state.retry
            st.session_state.retry = None

question = st.chat_input("Ask a question about the RBI credit directions…") or picked
if question:
    with st.chat_message("user"):
        st.markdown(question if not guards.find_personal_data(question) else guards.redact(question))
    with st.chat_message("assistant"):
        result = ask(question)
    if result:
        st.session_state.history.append({"question": question, "result": result})
    if result or st.session_state.retry:
        st.rerun()                         # redraw through the history loop so feedback and retry buttons work
