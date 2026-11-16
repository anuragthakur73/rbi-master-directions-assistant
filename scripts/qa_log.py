"""
Week 2, Step 7 - Log every question.

Appends one row per question to logs/qa_log.csv: what was asked, which paragraphs were retrieved,
what Claude answered, how long it took and how many tokens it used. Failed questions are logged too.
Weeks 3 (evaluation) and 4 (cost and latency) are built on this file.

Used by scripts/app.py. Open the CSV in Excel to review; close Excel before asking more questions,
because Windows won't let the app write to a file Excel has open.
"""
import csv
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "logs" / "qa_log.csv"
NOT_FOUND = "Not found in the provided documents."

FIELDS = [
    "run_id", "timestamp", "interface", "question", "outcome", "answer",
    "retrieved", "top_similarity", "num_paragraphs",
    "model", "effort", "k_paras", "system_prompt",
    "retrieval_seconds", "total_seconds",
    "input_tokens", "output_tokens", "thinking_tokens", "stop_reason", "error",
]


def outcome_of(result: dict) -> str:
    """answered / not_found / cut_off: a first label for each row, checked by hand in Week 3."""
    if result.get("stop_reason") == "max_tokens":
        return "cut_off"
    if result["answer"].strip().strip('"') == NOT_FOUND:
        return "not_found"
    return "answered"


def _write(row: dict) -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    new_file = not LOG_FILE.exists()
    # utf-8-sig so Excel shows ₹ correctly; newline="" stops blank lines between rows on Windows
    with LOG_FILE.open("a", newline="", encoding="utf-8-sig" if new_file else "utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in FIELDS})


def _base(question: str, interface: str, settings: dict) -> dict:
    return {"run_id": uuid.uuid4().hex[:8],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "interface": interface, "question": question, **settings}


def log_result(result: dict, interface: str, settings: dict) -> str:
    """One successful question. Returns the run_id so a turn on screen can be matched to its row."""
    row = _base(result["question"], interface, settings)
    retrieved = result["retrieved"]          # e.g. "Credit Facilities, Para 44 (0.81)"
    top = retrieved[0].rsplit("(", 1)[-1].rstrip(")") if retrieved else ""
    row.update({
        "outcome": outcome_of(result),
        "answer": result["answer"],
        "retrieved": " | ".join(retrieved),
        "top_similarity": top,
        "num_paragraphs": len(retrieved),
        "model": result["model"],
        **{k: result.get(k) for k in ("retrieval_seconds", "total_seconds", "input_tokens",
                                      "output_tokens", "thinking_tokens", "stop_reason")},
    })
    _write(row)
    return row["run_id"]


def log_error(question: str, error: str, interface: str, settings: dict) -> str:
    """One failed question (API error, missing store...). Failures count in Week 4's reliability numbers."""
    row = _base(question, interface, settings)
    row.update({"outcome": "error", "error": error})
    _write(row)
    return row["run_id"]


# ---------- Week 5: blocked questions and user feedback ----------
FEEDBACK_FILE = ROOT / "logs" / "feedback.csv"
FEEDBACK_FIELDS = ["run_id", "timestamp", "rating", "comment", "question"]


def log_blocked(question: str, reason: str, interface: str, settings: dict) -> str:
    """A question stopped before reaching Claude (possible personal data, daily limit).
    Pass the question already redacted (guards.redact) so personal data never reaches the log."""
    row = _base(question, interface, settings)
    row.update({"outcome": "blocked", "error": reason})
    _write(row)
    return row["run_id"]


def log_feedback(run_id: str, question: str, rating: int | None, comment: str = "") -> None:
    """One row per thumbs click or comment. rating: 1 = thumbs up, 0 = thumbs down, None = cleared.
    Join to qa_log.csv on run_id; the latest row for a run_id is the user's final rating."""
    FEEDBACK_FILE.parent.mkdir(exist_ok=True)
    new_file = not FEEDBACK_FILE.exists()
    with FEEDBACK_FILE.open("a", newline="", encoding="utf-8-sig" if new_file else "utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FEEDBACK_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({"run_id": run_id, "timestamp": datetime.now().isoformat(timespec="seconds"),
                         "rating": {1: "up", 0: "down"}.get(rating, "cleared"),
                         "comment": comment.strip(), "question": question})
