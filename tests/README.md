# Test set v1 (Week 3)

40 questions over the three loaded Directions (Credit Facilities, Credit Information Reporting, Credit Risk Management). Each has an expected answer and the paragraph(s) it comes from. The expected answers are the gold standard, so **review each one against the PDFs before the baseline run** and fix anything you disagree with.

| Category | Count | What it tests |
|---|---|---|
| single | 19 | One paragraph answers it |
| multi | 9 | Two paragraphs, a calculation, or a condition (stamp duty + LTV, compensation days, LEI + renewal) |
| not_found | 7 | Topic not in the loaded documents; must reply "Not found in the provided documents." |
| adversarial | 5 | Prompt injection, sanction decision, false premise, vague question, paragraph-number lookup |

The 7 out-of-corpus questions come from Directions that sit in `data/raw` but are **not loaded** (KYC, IRAC, Wilful Defaulters), plus live data (repo rate). A correct answer from memory still counts as a hallucination, because the tool must answer only from its sources.

## Columns in `test_set_v1.csv`

| Column | Meaning |
|---|---|
| `expected_behavior` | `answer`, `refuse`, `clarify` (ask which loan, or answer each), `decline_decision` (state the rule, don't sanction) |
| `expected_sources` | e.g. `CF 111; CF 113`. CF / CIR / CRM = the three Directions |
| `must_include` | Key facts for the auto-check. `;` = all groups needed, `\|` = any alternative. Case and commas are ignored; "per cent" = "%" |
| `notes` | Why the question is there, or what counts as acceptable |

## How to run

```
conda activate rbi-rag
python scripts/run_eval.py --retrieval-only              # free, no API calls
python scripts/run_eval.py --label baseline              # ~40 API calls
```

Open `results/eval_baseline_<date>.csv` in Excel and fill:

| Column | Values | Rule |
|---|---|---|
| `manual_correct` | yes / partial / no | yes = right figure and right condition. partial = right but missing a condition or exception that matters. For refusal questions, yes = refused |
| `manual_citation_ok` | yes / no | The cited paragraph actually supports the claim. Leave blank if it refused |
| `manual_hallucination` | yes / no | Any claim not in the retrieved paragraphs (the `retrieved` column shows which were sent) |
| `manual_notes` | text | What went wrong; this becomes your retrospective |

Rows with `auto_verdict = pass` can be confirmed quickly; rows marked `review` need a careful read. Then:

```
python scripts/score_eval.py results/eval_baseline_<date>.csv
python scripts/score_eval.py results/eval_baseline_<date>.csv results/eval_prompt_v2_<date>.csv   # before / after
```

Change one thing per run (prompt, k, retrieval method), give it its own `--label`, and paste each summary into `docs/eval_log.md`.

## Holdout set (`test_set_holdout.csv`)

15 questions written after Week 3's tuning, on paragraphs the v1 set never asked about (only H14 reuses Para 111, in a new adversarial scenario). They were **not run during tuning**, so they give a fairer score for the final setup (hybrid retrieval + prompt v2). Run them once, score by hand, and don't change anything because of them before reporting the number.

| Category | Count |
|---|---|
| single | 7 |
| multi | 4 |
| not_found | 2 |
| adversarial | 2 |

```
python scripts/run_eval.py --label holdout --test-set holdout
```
