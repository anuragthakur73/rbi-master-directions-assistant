"""
Week 5 - Guards around the answer pipeline: what the app checks BEFORE and AFTER calling Claude.

Before (nothing is sent to the API if these fail):
  - find_personal_data(): stops questions that look like they contain customer data
    (Aadhaar, PAN, mobile number, email, account / card number). Public RBI rules never need them.
  - question length cap, so a public link can't be used to send very long (expensive) prompts.
After (the answer is still shown, with a warning):
  - review_answer(): flags answers with no citation, answers citing a paragraph that was not
    among the retrieved excerpts, and clarifying questions.
Usage caps (UsageCounter) live here too, so they can be tested without Streamlit.

Pure Python, no extra packages. Patterns are deliberately simple; they will miss some personal
data and occasionally flag a number that isn't personal data (e.g. a 10-digit amount without commas).
"""
import re
import threading
from datetime import date

MAX_QUESTION_CHARS = 500

# (label shown to the user, pattern). Order matters only for the message.
_PII_PATTERNS = [
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.I)),
    ("Aadhaar number", re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")),
    ("email address", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("card number", re.compile(r"\b(?:\d{4}[\s-]){3}\d{4}\b")),
    ("mobile number", re.compile(r"(?<![\d,.])(?:\+?91[\s-]?)?[6-9]\d{9}(?![\d,])")),
    ("account number", re.compile(r"(?<![\d,.₹])\d{11,18}(?![\d,])")),
]


def find_personal_data(text: str) -> list[str]:
    """Kinds of personal data the text appears to contain (empty list = none found)."""
    found = []
    for label, pattern in _PII_PATTERNS:
        if pattern.search(text) and label not in found:
            found.append(label)
    # A 12-digit Aadhaar also matches the account pattern; report it once
    if "Aadhaar number" in found and "account number" in found:
        found.remove("account number")
    # A spaced 16-digit card number also contains an Aadhaar-shaped 12-digit run; report the card
    if "card number" in found and "Aadhaar number" in found:
        found.remove("Aadhaar number")
    return found


def redact(text: str) -> str:
    """Question text safe to write to the log: personal data replaced with [REDACTED]."""
    for _, pattern in _PII_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


# ---------- After the answer ----------
NOT_FOUND = "Not found in the provided documents."
# [Credit Facilities, Para 44] / [Credit Risk Management, Paras 58-59] / [CIR, Annex II]
_CITATION = re.compile(r"\[([A-Za-z ]+?),\s*(?:Paras?\.?\s*)?([^\]]+?)\]")


def citations_in(answer: str) -> list[tuple[str, str]]:
    """(document short name, paragraph label) pairs cited in the answer, in order, without repeats."""
    out = []
    for doc, para in _CITATION.findall(answer):
        for part in re.split(r"\s*(?:,|and|&)\s*", para):
            part = part.strip()
            if part and (doc.strip(), part) not in out:
                out.append((doc.strip(), part))
    return out


def _para_key(label: str) -> str:
    return re.sub(r"^para(graph)?s?\.?\s*", "", label.strip(), flags=re.I).lower()


def review_answer(answer: str, excerpts: list[dict]) -> dict:
    """Checks on a finished answer. Returns {"kind": ..., "message": ..., "cited": [...]}

    kind: "refusal"     - the designed "not found" reply
          "clarify"     - Claude asked a clarifying question
          "no_citation" - an answer with no [Doc, Para X] citation at all
          "unretrieved" - cites a paragraph that wasn't in the excerpts Claude was given
          "ok"
    cited: the cited paragraphs found among the excerpts, for the "cited paragraphs" panel.
    """
    text = answer.strip().strip('"')
    if text.startswith(NOT_FOUND):
        return {"kind": "refusal", "message": "", "cited": []}

    available = {(e["doc"], _para_key(e["label"])): e for e in excerpts}
    cited, missing = [], []
    for doc, para in citations_in(text):
        hit = available.get((doc, _para_key(para)))
        if hit and hit not in cited:
            cited.append(hit)
        elif not hit:
            missing.append(f"{doc}, {para}" if para[:1].isalpha() else f"{doc}, Para {para}")

    if missing:
        return {"kind": "unretrieved", "cited": cited,
                "message": "This answer cites " + "; ".join(missing) + ", which was not among the "
                           "paragraphs retrieved for this question. Treat it as unverified and check the PDF."}
    if not cited:
        last = text.rstrip().splitlines()[-1] if text.strip() else ""
        if last.rstrip().endswith("?"):
            return {"kind": "clarify", "cited": [], "message": "Claude needs one more detail to answer. Reply with it below."}
        return {"kind": "no_citation", "cited": [],
                "message": "This answer has no paragraph citation, so it can't be traced to the RBI text. "
                           "Treat it as unverified and check the sources below."}
    return {"kind": "ok", "message": "", "cited": cited}


# ---------- Usage caps ----------
class UsageCounter:
    """Questions answered today, shared by everyone using one running copy of the app.

    Resets at midnight (server time) and whenever the app restarts, so it is a safety net against a
    runaway bill, not exact accounting. The hard limit is the monthly spend limit in the Claude Console.
    """
    def __init__(self, daily_limit: int):
        self.daily_limit = daily_limit
        self._day = date.today()
        self._count = 0
        self._lock = threading.Lock()

    def _roll(self):
        if date.today() != self._day:
            self._day, self._count = date.today(), 0

    def remaining(self) -> int:
        with self._lock:
            self._roll()
            return max(self.daily_limit - self._count, 0)

    def take(self) -> bool:
        """Count one question. False if today's limit is already used up."""
        with self._lock:
            self._roll()
            if self._count >= self.daily_limit:
                return False
            self._count += 1
            return True
