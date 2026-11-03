"""
Second grader: check that your hand grades are not just your own opinion.

1. Make a blind sheet: a random sample of answers from a graded results file, WITHOUT your grades.
     python scripts/second_grader.py make results/eval_prompt_v2_20261029_0020.csv --n 15
   -> results/grader2_<results name>.csv. Give it to a second person (a banking colleague or friend
      who can read the RBI paragraphs). They fill the three grader2_ columns, using the same rules as
      tests/README.md, and only look at the paragraphs listed in "retrieved".
      Only questions and answers about public RBI rules go in this sheet: no customer or bank data.

2. Compare their grades with yours:
     python scripts/second_grader.py compare results/eval_prompt_v2_20261029_0020.csv results/grader2_eval_prompt_v2_20261029_0020.csv
   Prints % agreement and Cohen's kappa (agreement beyond chance; above ~0.6 is usually read as
   substantial). Paste the table into docs/eval_log.md and discuss every disagreement.
   Caution: when almost every answer is "yes" (as at 94% accuracy), kappa can be near 0 even with
   high agreement, e.g. 14/15 agree -> 93% but kappa 0.00. So lead with % agreement and the list of
   disagreements; quote kappa only alongside them.
"""
import argparse
import csv
import random
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PAIRS = [("manual_correct", "grader2_correct"),
         ("manual_citation_ok", "grader2_citation_ok"),
         ("manual_hallucination", "grader2_hallucination")]
NORMAL = {"y": "yes", "1": "yes", "true": "yes", "n": "no", "0": "no", "false": "no", "p": "partial", "0.5": "partial"}


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm(v: str | None) -> str:
    v = (v or "").strip().lower()
    return NORMAL.get(v, v)


def make(results: Path, n: int, seed: int) -> None:
    rows = [r for r in load(results) if norm(r.get("manual_correct"))]
    if not rows:
        raise SystemExit("No hand-graded rows in that file. Fill manual_correct first.")
    random.seed(seed)                       # fixed seed: the same sample every time, so it can't be re-drawn to look better
    sample = sorted(random.sample(rows, min(n, len(rows))), key=lambda r: r["id"])
    out = ROOT / "results" / f"grader2_{results.stem}.csv"
    fields = ["id", "question", "answer", "retrieved", "grader2_correct", "grader2_citation_ok",
              "grader2_hallucination", "grader2_notes"]
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sample:
            w.writerow({k: r.get(k, "") for k in ("id", "question", "answer", "retrieved")})
    print(f"Saved {len(sample)} answers (seed {seed}) to {out.relative_to(ROOT)}")
    print("Values: grader2_correct yes/partial/no; grader2_citation_ok yes/no (blank if it refused); "
          "grader2_hallucination yes/no.")


def kappa(a: list[str], b: list[str]) -> float | None:
    """Cohen's kappa for two graders' labels on the same items."""
    n = len(a)
    if n == 0:
        return None
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def compare(results: Path, grader2: Path) -> None:
    mine = {r["id"]: r for r in load(results)}
    theirs = load(grader2)
    lines = ["| Measure | Items both graded | Agreement | Cohen's kappa |", "|---|---|---|---|"]
    disagreements = []
    for m_col, g_col in PAIRS:
        a, b = [], []
        for r in theirs:
            x, y = norm(mine.get(r["id"], {}).get(m_col)), norm(r.get(g_col))
            if x and y:
                a.append(x)
                b.append(y)
                if x != y:
                    disagreements.append(f"{r['id']} {m_col.replace('manual_', '')}: you {x}, grader 2 {y}")
        k = kappa(a, b)
        agree = f"{100 * sum(x == y for x, y in zip(a, b)) / len(a):.0f}%" if a else "n/a"
        k_txt = "n/a (one label only)" if k is None else f"{k:.2f}"
        lines.append(f"| {m_col.replace('manual_', '')} | {len(a)} | {agree} | {k_txt} |")
    print("\n".join(lines))
    print("\nDisagreements to discuss:" if disagreements else "\nNo disagreements.")
    for d in disagreements:
        print("  " + d)


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("results", type=Path)
    m.add_argument("--n", type=int, default=15)
    m.add_argument("--seed", type=int, default=7)
    c = sub.add_parser("compare")
    c.add_argument("results", type=Path)
    c.add_argument("grader2", type=Path)
    args = p.parse_args()
    if args.cmd == "make":
        make(args.results, args.n, args.seed)
    else:
        compare(args.results, args.grader2)


if __name__ == "__main__":
    main()
