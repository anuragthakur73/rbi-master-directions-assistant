"""
Week 3 - Summarise a scored results file.

  python scripts/score_eval.py results/eval_baseline_20261026_2100.csv
  python scripts/score_eval.py results/eval_baseline_20261026_2100.csv results/eval_prompt_v2_20261027_2030.csv

Uses your manual_ columns where filled; otherwise falls back to the auto-checks and says so.
Prints a markdown summary to paste into docs/eval_log.md, and saves it next to the results file.
With two files it also prints a before/after comparison table.

Manual columns (fill in Excel):
  manual_correct        yes / partial / no    (for refusal questions: yes = refused correctly)
  manual_citation_ok    yes / no              (does the cited paragraph support the answer? blank if refused)
  manual_hallucination  yes / no              (any claim not in the retrieved paragraphs?)
  manual_notes          free text
"""
import csv
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

YES = {"yes", "y", "1", "true"}
PARTIAL = {"partial", "p", "0.5"}
CATEGORIES = ["single", "multi", "not_found", "adversarial"]
NOT_FOUND = "Not found in the provided documents."


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def val(s: str | None) -> str:
    return (s or "").strip().lower()


def refused(r: dict) -> bool:
    """A reply that starts with the refusal sentence counts as a refusal, even if context follows."""
    if r.get("answer"):
        return r["answer"].strip().strip('"').startswith(NOT_FOUND)
    return val(r.get("refused")) == "yes"


def correctness(r: dict) -> tuple[float | None, str]:
    """Score 1 / 0.5 / 0 and where it came from; None if nothing to score."""
    m = val(r.get("manual_correct"))
    if m:
        return (1.0 if m in YES else 0.5 if m in PARTIAL else 0.0), "manual"
    auto = val(r.get("auto_verdict"))
    if not auto:
        return None, "none"
    if auto == "pass":
        return 1.0, "auto"
    if auto.startswith("fail") or auto == "error":
        return 0.0, "auto"
    return None, "unreviewed"           # auto said "review" and you haven't scored it yet


def pct(num: float, den: int) -> str:
    return f"{100 * num / den:.0f}% ({num:g}/{den})" if den else "n/a"


def summarise(rows: list[dict]) -> dict:
    scored = [(r, *correctness(r)) for r in rows]
    graded = [(r, s) for r, s, _ in scored if s is not None]
    unreviewed = [r["id"] for r, s, src in scored if src == "unreviewed"]
    manual = sum(src == "manual" for _, _, src in scored)

    refuse = [r for r in rows if r["expected_behavior"] == "refuse"]
    answerable = [r for r in rows if r["expected_behavior"] != "refuse"]
    answered = [r for r in rows if r.get("answer") and not refused(r) and not r.get("error")]
    cites = [val(r.get("manual_citation_ok")) for r in answered if val(r.get("manual_citation_ok"))]
    if not cites:                                    # fall back to the auto citation check
        cites = [val(r.get("cited_expected")) for r in answered if val(r.get("cited_expected")) in ("yes", "no")]
    halluc = [val(r.get("manual_hallucination")) for r in rows if val(r.get("manual_hallucination"))]
    latencies = [float(r["total_seconds"]) for r in rows if r.get("total_seconds")]
    tokens_in = [int(r["input_tokens"]) for r in rows if r.get("input_tokens")]
    tokens_out = [int(r["output_tokens"]) for r in rows if r.get("output_tokens")]
    retr = [r for r in rows if r.get("retrieval_hit") in ("yes", "no")]

    by_cat = {}
    for c in CATEGORIES:
        g = [s for r, s in graded if r["category"] == c]
        by_cat[c] = (sum(g), len(g), sum(r["category"] == c for r in rows))

    return {
        "n": len(rows), "graded": len(graded), "manual": manual, "unreviewed": unreviewed,
        "correct": sum(s for _, s in graded), "correct_strict": sum(s == 1.0 for _, s in graded),
        "refusal_ok": sum(refused(r) for r in refuse), "refuse_n": len(refuse),
        "false_refusals": sum(refused(r) for r in answerable), "answerable_n": len(answerable),
        "cite_ok": sum(c in YES for c in cites), "cite_n": len(cites),
        "cite_source": "manual" if any(val(r.get("manual_citation_ok")) for r in answered) else "auto",
        "halluc": sum(h in YES for h in halluc), "halluc_n": len(halluc),
        "retr_hit": sum(r["retrieval_hit"] == "yes" for r in retr), "retr_n": len(retr),
        "retr_top1": sum(r.get("retrieval_rank") == "1" for r in retr),
        "lat_median": statistics.median(latencies) if latencies else None,
        "lat_p95": sorted(latencies)[max(0, int(round(0.95 * len(latencies))) - 1)] if latencies else None,
        "in_avg": statistics.mean(tokens_in) if tokens_in else None,
        "out_avg": statistics.mean(tokens_out) if tokens_out else None,
        "by_cat": by_cat,
        "config": {k: rows[0].get(k, "") for k in ("model", "effort", "k_paras", "system_prompt", "retrieval_mode")} if rows else {},
    }


def report(name: str, s: dict) -> str:
    lines = [f"### {name}", ""]
    cfg = s["config"]
    lines.append(f"Config: {cfg.get('model')}, effort {cfg.get('effort')}, top {cfg.get('k_paras')} paragraphs, "
                 f"{cfg.get('system_prompt')}, {cfg.get('retrieval_mode') or 'semantic'} retrieval. Graded {s['graded']}/{s['n']} ({s['manual']} by hand).")
    if s["unreviewed"]:
        lines.append(f"**Not yet scored (auto-check said review):** {', '.join(s['unreviewed'])}")
    lines += ["", "| Metric | Result |", "|---|---|",
              f"| Correct (partial = 0.5) | {pct(s['correct'], s['graded'])} |",
              f"| Fully correct | {pct(s['correct_strict'], s['graded'])} |",
              f"| Correct refusals (out-of-corpus) | {pct(s['refusal_ok'], s['refuse_n'])} |",
              f"| False refusals (answerable but refused) | {pct(s['false_refusals'], s['answerable_n'])} |",
              f"| Citation accurate ({s['cite_source']}) | {pct(s['cite_ok'], s['cite_n'])} |",
              f"| Hallucination rate (manual) | {pct(s['halluc'], s['halluc_n'])} |",
              f"| Retrieval: expected para sent to Claude | {pct(s['retr_hit'], s['retr_n'])}; rank 1 in {s['retr_top1']} |"]
    if s["lat_median"] is not None:
        lines.append(f"| Latency median / p95 | {s['lat_median']:.1f}s / {s['lat_p95']:.1f}s |")
        lines.append(f"| Avg tokens in / out | {s['in_avg']:.0f} / {s['out_avg']:.0f} |")
    lines += ["", "| Category | Correct | Questions |", "|---|---|---|"]
    for c, (score, graded, total) in s["by_cat"].items():
        lines.append(f"| {c} | {pct(score, graded)} | {total} |")
    return "\n".join(lines)


def compare(names: list[str], sums: list[dict]) -> str:
    def f(s, key, den):
        return f"{100 * s[key] / s[den]:.0f}%" if s[den] else "n/a"
    rows = [("Correct", "correct", "graded"), ("Correct refusals", "refusal_ok", "refuse_n"),
            ("False refusals", "false_refusals", "answerable_n"), ("Citation accurate", "cite_ok", "cite_n"),
            ("Hallucination", "halluc", "halluc_n"), ("Retrieval hit", "retr_hit", "retr_n")]
    out = ["### Comparison", "", "| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for label, k, d in rows:
        out.append(f"| {label} | " + " | ".join(f(s, k, d) for s in sums) + " |")
    return "\n".join(out)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    paths = [Path(p) for p in sys.argv[1:]]
    sums, names = [], []
    for p in paths:
        s = summarise(load(p))
        text = report(p.stem, s)
        print(text + "\n")
        p.with_name(p.stem + "_summary.md").write_text(text + "\n", encoding="utf-8")
        sums.append(s)
        names.append(p.stem.replace("eval_", ""))
    if len(paths) > 1:
        print(compare(names, sums))


if __name__ == "__main__":
    main()
