"""
Week 3 - Run the test set and score it.

Reads  tests/test_set_v1.csv          (40 questions with expected answers and source paragraphs)
Writes results/eval_<label>_<date-time>.csv   (one row per question: answer, auto-checks, blank columns for your scoring)
Also logs every question to logs/qa_log.csv with interface "eval", like the app does.

Run from the repo root:
  python scripts/run_eval.py --retrieval-only          free: checks retrieval only, no API calls
  python scripts/run_eval.py --label baseline          full run: about 40 API calls
  python scripts/run_eval.py --label baseline --ids S01,M02,A04    only some questions
  python scripts/run_eval.py --label semantic --retrieval semantic   re-run with Week 2 retrieval
  python scripts/run_eval.py --label prompt_v2 --prompt v2           use prompts/system_prompt_v2.md

Then open the results CSV in Excel, fill the four "manual_" columns, save, and run
  python scripts/score_eval.py results/<that file>.csv

Auto-checks are a first pass, not the verdict. They only look for key figures and citations;
you decide whether an answer is actually correct.
"""
import argparse
import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import answer as engine          # scripts/answer.py
import qa_log
from embed_store import search

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TEST_SET = ROOT / "tests" / "test_set_v1.csv"
RESULTS_DIR = ROOT / "results"
NOT_FOUND = qa_log.NOT_FOUND

DOC_ABBR = {"CF": "Credit Facilities", "CIR": "Credit Information Reporting", "CRM": "Credit Risk Management"}
SOURCE_ABBR = {"CB_Credit_Facilities_2025": "CF", "CB_Credit_Information_Reporting_2025": "CIR",
               "CB_Credit_Risk_Management_2025": "CRM"}

MANUAL_COLS = ["manual_correct", "manual_citation_ok", "manual_hallucination", "manual_notes"]
FIELDS = ["id", "category", "expected_behavior", "question", "expected_answer", "expected_sources",
          "answer", "retrieved", "retrieval_hit", "retrieval_rank", "refused", "facts_found", "cited_expected",
          "auto_verdict", *MANUAL_COLS,
          "model", "effort", "k_paras", "system_prompt", "retrieval_mode", "total_seconds", "input_tokens", "output_tokens",
          "thinking_tokens", "stop_reason", "error"]


def norm(text: str) -> str:
    """Lower case, drop thousands separators, and write 'per cent' as '%' so '85 per cent' matches '85%'."""
    t = text.lower().replace(",", "").replace("₹", "")
    t = re.sub(r"\s*per\s*cent", "%", t)
    t = re.sub(r"\s*percent", "%", t)
    return re.sub(r"\s+", " ", t)


def facts_found(answer_text: str, must_include: str) -> str:
    """must_include: groups separated by ';', alternatives by '|'. Every group needs one alternative."""
    if not must_include.strip():
        return "n/a"
    a = norm(answer_text)
    missing = [g for g in must_include.split(";")
               if not any(norm(alt.strip()) in a for alt in g.split("|") if alt.strip())]
    return "yes" if not missing else "no (missing: " + "; ".join(m.strip() for m in missing) + ")"


def expected_list(sources: str) -> list[tuple[str, str]]:
    """'CF 111; CF 113' -> [('CF', '111'), ('CF', '113')]"""
    out = []
    for s in sources.split(";"):
        parts = s.strip().split(None, 1)
        if len(parts) == 2:
            out.append((parts[0], parts[1]))
    return out


def retrieval_rank(question: str, expected: list[tuple[str, str]]) -> int | None:
    """Rank (1 = best) of the first expected paragraph among the distinct paragraphs sent to Claude."""
    excerpts = engine.retrieve(question)
    for rank, ex in enumerate(excerpts, start=1):
        if (SOURCE_ABBR.get(ex["source"]), ex["para"]) in expected:
            return rank
    return None


def cited_expected(answer_text: str, expected: list[tuple[str, str]]) -> str:
    """Does the answer cite at least one expected paragraph, e.g. [Credit Facilities, Para 111(a)]?"""
    if not expected:
        return "n/a"
    for abbr, para in expected:
        doc = re.escape(DOC_ABBR[abbr])
        if re.search(rf"{doc}[^\]]*?Para(?:s|graphs?)?\s*[^\]]*?\b{re.escape(para)}(?![0-9A-Z])", answer_text):
            return "yes"
    return "no"


def auto_verdict(case: dict, row: dict) -> str:
    behavior = case["expected_behavior"]
    if row.get("error"):
        return "error"
    if row["stop_reason"] == "max_tokens":
        return "fail (cut off)"
    if behavior == "refuse":
        return "pass" if row["refused"] == "yes" else "review (answered; check for hallucination)"
    if row["refused"] == "yes":
        return "fail (refused an answerable question)"
    if behavior == "clarify":
        return "review"
    ok = row["facts_found"] in ("yes", "n/a") and row["cited_expected"] in ("yes", "n/a")
    return "pass" if ok else "review"


def load_cases(ids: str | None) -> list[dict]:
    with TEST_SET.open(encoding="utf-8-sig", newline="") as f:
        cases = list(csv.DictReader(f))
    if ids:
        wanted = {i.strip().upper() for i in ids.split(",")}
        cases = [c for c in cases if c["id"].upper() in wanted]
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run", help="short name for this run, e.g. baseline, prompt_v2, k8")
    parser.add_argument("--ids", help="comma-separated test ids to run, e.g. S01,M02")
    parser.add_argument("--retrieval-only", action="store_true", help="check retrieval only; no API calls, no cost")
    parser.add_argument("--retrieval", choices=["semantic", "hybrid"],
                        help="override RETRIEVAL_MODE in answer.py for this run")
    parser.add_argument("--prompt", help="system prompt version for this run, e.g. v2 -> prompts/system_prompt_v2.md")
    args = parser.parse_args()
    if args.retrieval:
        engine.RETRIEVAL_MODE = args.retrieval
    if args.prompt:
        engine.SYSTEM_PROMPT_FILE = engine.ROOT / "prompts" / f"system_prompt_{args.prompt}.md"
        engine.load_system_prompt()          # fail now, not after the first API call, if the file is missing

    cases = load_cases(args.ids)
    if not cases:
        raise SystemExit("No test cases selected.")
    settings = {"effort": engine.EFFORT, "k_paras": engine.K_PARAS, "system_prompt": engine.SYSTEM_PROMPT_FILE.name}
    client = None if args.retrieval_only else engine.make_client()

    RESULTS_DIR.mkdir(exist_ok=True)
    label = re.sub(r"[^A-Za-z0-9_-]", "_", args.label) + ("_retrieval" if args.retrieval_only else "")
    out_file = RESULTS_DIR / f"eval_{label}_{datetime.now():%Y%m%d_%H%M}.csv"

    rows = []
    for n, case in enumerate(cases, start=1):
        expected = expected_list(case["expected_sources"])
        rank = retrieval_rank(case["question"], expected) if expected else None
        row = {k: case[k] for k in ("id", "category", "expected_behavior", "question", "expected_answer", "expected_sources")}
        row.update({"retrieval_rank": rank or "", "model": engine.MODEL, **settings,
                    "retrieval_mode": engine.RETRIEVAL_MODE,
                    "retrieval_hit": "n/a" if not expected else ("yes" if rank else "no")})

        if not args.retrieval_only:
            try:
                result = engine.answer(case["question"], client)
                qa_log.log_result(result, "eval", settings)
                text = result["answer"]
                row.update({
                    "answer": text,
                    "retrieved": " | ".join(result["retrieved"]),
                    "refused": "yes" if text.strip().strip('"').startswith(NOT_FOUND) else "no",   # refusal may be followed by context
                    "facts_found": facts_found(text, case["must_include"]),
                    "cited_expected": cited_expected(text, expected),
                    **{k: result.get(k) for k in ("total_seconds", "input_tokens", "output_tokens",
                                                  "thinking_tokens", "stop_reason")},
                })
            except Exception as e:                          # keep going; one failure shouldn't stop the run
                msg = f"{type(e).__name__}: {e}"
                qa_log.log_error(case["question"], msg, "eval", settings)
                row.update({"error": msg, "stop_reason": ""})
            row["auto_verdict"] = auto_verdict(case, row)
            time.sleep(0.5)                                 # gentle on rate limits

        rows.append(row)
        status = row.get("auto_verdict", f"retrieval {'hit @' + str(rank) if rank else ('miss' if expected else 'n/a')}")
        print(f"[{n:>2}/{len(cases)}] {case['id']:<4} {status}")
    print(f"\nRetrieval mode: {engine.RETRIEVAL_MODE}")

    with out_file.open("w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig so Excel shows ₹
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({k: r.get(k, "") for k in FIELDS} for r in rows)

    answerable = [r for r in rows if r["retrieval_hit"] != "n/a"]
    hits = sum(r["retrieval_hit"] == "yes" for r in answerable)
    top1 = sum(str(r["retrieval_rank"]) == "1" for r in answerable)
    print(f"\nRetrieval: expected paragraph sent to Claude in {hits}/{len(answerable)} answerable questions "
          f"(rank 1 in {top1}).")
    if not args.retrieval_only:
        passes = sum(r["auto_verdict"] == "pass" for r in rows)
        print(f"Auto-check: {passes}/{len(rows)} pass; the rest need your review.")
    print(f"Saved: {out_file.relative_to(ROOT)}")
    if not args.retrieval_only:
        print("Next: fill the manual_ columns in Excel (close it afterwards), then run "
              f"python scripts/score_eval.py {out_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
