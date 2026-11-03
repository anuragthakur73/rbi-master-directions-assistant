"""
Week 4 - Model, cost and latency comparison.

  python scripts/cost_report.py results/eval_prompt_v2_20261029_0020.csv results/eval_haiku_<date>.csv results/eval_opus_<date>.csv

For each results file (one model run): quality from your manual scores (same rules as score_eval.py),
plus latency and cost from the token counts the run recorded. Prints one markdown table for
docs/eval_log.md and saves it as results/model_comparison_<date>.md.

Cost = input tokens x input price + output tokens x output price. Output tokens already include
Claude's thinking tokens, which are billed as output.

PRICES must match Anthropic's official pricing page on the day you report them. Prices change,
so check the page and update PRICES_CHECKED before you publish any number.
"""
import statistics
import sys
from datetime import date
from pathlib import Path

from score_eval import load, summarise

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PRICES_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
PRICES_CHECKED = "2026-10-29"
# USD per million tokens, standard API (no batch, no caching, global data residency).
# Haiku 5.5 is tiered by prompt length: prompts over 100,000 tokens pay the higher rate.
PRICES = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50,
                         "over_100k": {"input": 0.50, "output": 2.50}},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00},
}
USD_TO_INR = None   # optional: set a rate (e.g. from RBI's reference rate on the day) to add a ₹ column


def query_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICES[model]
    if "over_100k" in p and input_tokens > 100_000:
        p = p["over_100k"]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def p95(values: list[float]) -> float:
    s = sorted(values)
    return s[max(0, int(round(0.95 * len(s))) - 1)]


def analyse(path: Path) -> dict:
    rows = load(path)
    s = summarise(rows)
    model = s["config"].get("model", "")
    if model not in PRICES:
        raise SystemExit(f"{path.name}: no price for model '{model}'. Add it to PRICES.")
    done = [r for r in rows if r.get("input_tokens") and r.get("output_tokens")]
    costs = [query_cost(model, int(r["input_tokens"]), int(r["output_tokens"])) for r in done]
    lat = [float(r["total_seconds"]) for r in done if r.get("total_seconds")]
    thinking = [int(r["thinking_tokens"]) for r in done if (r.get("thinking_tokens") or "").isdigit()]
    errors = sum(1 for r in rows if r.get("error"))
    return {
        "file": path.name, "model": model, "n": len(rows), "errors": errors,
        "correct": 100 * s["correct"] / s["graded"] if s["graded"] else None,
        "graded": s["graded"], "manual": s["manual"], "unreviewed": s["unreviewed"],
        "refusal_ok": f"{s['refusal_ok']}/{s['refuse_n']}",
        "false_ref": f"{s['false_refusals']}/{s['answerable_n']}",
        "halluc": f"{s['halluc']}/{s['halluc_n']}" if s["halluc_n"] else "not scored",
        "lat_median": statistics.median(lat) if lat else None,
        "lat_p95": p95(lat) if lat else None,
        "in_avg": statistics.mean(int(r["input_tokens"]) for r in done) if done else 0,
        "out_avg": statistics.mean(int(r["output_tokens"]) for r in done) if done else 0,
        "think_avg": statistics.mean(thinking) if thinking else 0,
        "cost_per_1000": 1000 * statistics.mean(costs) if costs else None,
        "effort": s["config"].get("effort", ""),
    }


def table(results: list[dict]) -> str:
    inr = USD_TO_INR is not None
    head = ["Model", "Correct", "Correct refusals", "False refusals", "Hallucinations", "Median / p95 latency",
            "Avg tokens in / out (thinking)", "Cost per 1,000 queries (USD)"] + (["(₹)"] if inr else [])
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in results:
        correct = f"{r['correct']:.0f}%" if r["correct"] is not None else "n/a"
        if r["graded"] > r["manual"]:
            correct += f" (auto-check for {r['graded'] - r['manual']})"
        if r["unreviewed"]:
            correct += f", {len(r['unreviewed'])} not yet scored"
        cells = [f"{r['model']} ({r['effort']})", correct, r["refusal_ok"], r["false_ref"], r["halluc"],
                 f"{r['lat_median']:.1f}s / {r['lat_p95']:.1f}s" if r["lat_median"] is not None else "n/a",
                 f"{r['in_avg']:,.0f} / {r['out_avg']:,.0f} ({r['think_avg']:,.0f})",
                 f"${r['cost_per_1000']:.2f}" if r["cost_per_1000"] is not None else "n/a"]
        if inr:
            cells.append(f"₹{r['cost_per_1000'] * USD_TO_INR:,.0f}" if r["cost_per_1000"] is not None else "n/a")
        lines.append("| " + " | ".join(cells) + " |")
    notes = [f"\nPrices: {PRICES_SOURCE} (checked {PRICES_CHECKED}), standard API, no caching or batch discount.",
             "Cost per query = input tokens x input price + output tokens (including thinking) x output price."]
    errs = [f"{r['model']}: {r['errors']} API errors" for r in results if r["errors"]]
    if errs:
        notes.append("Errors: " + "; ".join(errs) + " (counted as wrong in Correct).")
    return "\n".join(lines + notes)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    results = [analyse(Path(p)) for p in sys.argv[1:]]
    text = "### Model comparison\n\n" + table(results)
    print(text)
    out = ROOT / "results" / f"model_comparison_{date.today():%Y%m%d}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
