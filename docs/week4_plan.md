# Week 4: Model size, cost and latency trade-offs

**Question this week answers:** which Claude model would I ship for Credit Assist, and why?

**Exit criteria (from the build guide):** comparison table complete with the pricing date noted; model choice written up in one paragraph.

## Set-up (fixed for every run)

Only the model changes. Everything else stays as the Week 3 final setup, so any difference is down to the model.

| Setting | Value |
|---|---|
| Test set | `tests/test_set_v1.csv` (40 questions). Its expected answers are checked, and it keeps results comparable with Week 3. The fresh set stays on hold. |
| Retrieval | hybrid, top 5 paragraphs, neighbours off |
| Prompt | `system_prompt_v2.md` |
| Effort | medium (all three models support the effort parameter) |
| Baseline (already done) | Sonnet 5.5: `results/eval_prompt_v2_20261029_0020.csv`: 94% correct, $8.65 per 1,000 queries, p95 7.2s |

**Known bias to state in the write-up:** prompt v2 was tuned on Sonnet's answers in Week 3, so the test slightly favours Sonnet. A model that loses narrowly may do better with its own prompt tuning.

## Prices (checked 3 Nov 2026, Claude API, standard, per million tokens)

| Model | Input | Output |
|---|---|---|
| Haiku 5.5 | $0.10 (prompts up to 100k tokens) | $0.50 |
| Sonnet 5.5 | $2.00 | $10.00 |
| Opus 5.5 | $4.00 | $20.00 |

Sources: Claude Haiku 5.5 model overview (platform.claude.com/docs/en/models/haiku-5-5/overview) and the Claude pricing page. Batch API is 50% off; not used here because the tool answers live questions. Thinking tokens are billed as output.

## Step 1: Run the two new models (about 80 API calls, roughly $1 in total)

```
conda activate rbi-rag
cd "C:\Users\anura\Desktop\docs\ML\pm project\git rep clone\rbi-master-directions-assistant"
python scripts/run_eval.py --label haiku --model claude-haiku-5-5 --effort medium
python scripts/run_eval.py --label opus --model claude-opus-5-5 --effort medium
```

Cost estimate (my arithmetic from the Sonnet run's average of 2,880 input and 289 output tokens; the real token counts per model will differ): Haiku about $0.02 for 40 questions, Opus under $1 (Opus may think more, so allow for it).

Before the full runs, try one question on each model (`--ids S01`) to check the model ID and settings work.

## Step 2: Grade by hand, same rules as Week 3

Open each new `results/eval_<label>_<date>.csv` in Excel and fill `manual_correct`, `manual_citation_ok`, `manual_hallucination` and `manual_notes`, using the rules in `tests/README.md`.

- Grade each answer against the **expected answer and the PDF**, not against Sonnet's answer. Comparing with Sonnet would make Sonnet the gold standard.
- Grade all 40. A row left blank falls back to the auto-check, and the table will show that.

## Step 3: Build the comparison table

```
python scripts/cost_report.py results/eval_prompt_v2_20261029_0020.csv results/eval_haiku_<date>.csv results/eval_opus_<date>.csv
```

It prints and saves `results/model_comparison_<date>.md` with three sections:

1. **Model comparison:** correct %, refusals, hallucinations, median/p95 latency, tokens, cost per 1,000 queries.
2. **Correct by question type:** single / multi / not_found / adversarial for each model. This is the evidence for or against routing.
3. **Scale estimate:** monthly API cost at 10,000 users a day. The usage figures (3 queries per user per working day, 22 days) are assumptions at the top of `cost_report.py`; change them if you have a better basis and label them as estimates either way.

Paste the output into `docs/eval_log.md`. To add a ₹ column, set `USD_TO_INR` in `cost_report.py` to RBI's reference rate on the day and note the date.

## Step 4: Decide, using rules set before seeing the results

Write these down **before** Step 3 so the results can't shape the rule. Suggested rule, based on the PRD targets:

> Ship the cheapest model that meets all of: correct ≥ 85%, hallucinations ≤ 5% (≤ 2 of 40), all 8 refusals correct, p95 latency under 8 s, cost under ₹1 a query. If two models meet them, prefer the cheaper one unless the dearer one is better on multi-paragraph questions, where a wrong answer costs most.

Then answer each of these in one or two sentences:

1. **Choice:** which model, and which threshold decided it?
2. **Routing:** does a cheaper model match on a whole question type? Could the app tell that type apart before answering (for example, a paragraph-number lookup is easy to detect; "single vs multi-paragraph" is not)? If not, say routing isn't worth it yet.
3. **Cost levers:** which matter here? Input is about 90% of tokens, and most of that is the 5 retrieved paragraphs, so fewer or shorter excerpts cut the most. Prompt caching helps little here (my inference): only the ~420-word system prompt repeats between questions, and the excerpts change every time. Check that against the caching docs before you say it in an interview.
4. **At 10,000 users a day:** what you would change (estimate, labelled as one).

## Step 5: Write-up (one paragraph, for the README and retrospective)

Template, to fill only with your own numbers:

> I ran the same 40-question test set through Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5 at medium effort, with retrieval and prompt fixed. [Model] scored [x]% correct with [y] hallucinations at $[z] per 1,000 queries and a p95 of [t]s. I chose [model] because [threshold]. [The trade-off I accepted, in one sentence.] [One thing that surprised me.]

## Optional, if time allows

- **Effort as a lever:** if Haiku misses mainly on multi-paragraph questions, run `--model claude-haiku-5-5 --effort high` once. It is still far cheaper than Sonnet and shows a PM trade-off (thinking vs model size).
- **Re-run variance:** run the chosen model a second time. If the score moves by 2 to 3 questions, say that differences that small between models are not meaningful on 40 questions.
