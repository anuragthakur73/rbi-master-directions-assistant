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


---

## Week 4 results and decision (5 Nov 2026)

> **Draft by Claude from the results in `docs/eval_log.md`. Review it and rewrite it in your own words before it goes into the README or an interview.**

### Decision rule check

| Threshold (set before the results) | Sonnet 5.5 | Haiku 5.5 | Opus 5.5 |
|---|---|---|---|
| Correct ≥ 85% | ✓ 94% | ✓ 94% | ✓ 94% |
| Hallucinations ≤ 2 of 40 | ✓ 1 | ✓ 0 | ✓ 0 |
| All 8 refusals correct | ✓ 8/8 | ✓ 8/8 | ✓ 8/8 |
| p95 latency < 8 s | ✓ 7.2 s | ✓ 6.7 s | ✗ 10.6 s |
| Cost < ₹1 a query | ✓ ₹0.82 | ✓ ₹0.05 | ✗ ₹1.97 |

Passes all thresholds: Sonnet and Haiku. The cheaper one is Haiku. On multi-paragraph questions both score 7.5/9, so the tie-break doesn't apply. **Result under the rule: Haiku 5.5.**

### 1. Choice

Claude Haiku 5.5 at medium effort.

**Confirmed on the holdout set (6 Nov 2026):** Haiku scored 12.5/15 (83%), the same as Sonnet, with 0 hallucinations and both refusals correct. Same three misses as Sonnet (H05, H06, H08), all retrieval failures. Default switched to Haiku in `scripts/answer.py`.

Original reasoning: It is the cheapest model that met every PRD threshold: $0.57 vs $8.65 per 1,000 queries for Sonnet, with the same 94% correct and no hallucinations. Because the 40-question set was used for tuning, the switch should wait for one more check: run Haiku on the holdout set (15 questions; Sonnet scored 83% there) and switch only if it scores within a question of Sonnet.

```
python scripts/run_eval.py --label holdout_haiku --test-set holdout --model claude-haiku-5-5 --effort medium
```

### 2. Routing

Not worth it now. All three models score the same on every question type, so there is no type that needs a bigger model. Routing would add a classifier, a second model and another failure point for no measured gain. Revisit it only if a larger test set shows a gap on multi-paragraph questions.

### 3. Cost levers

- **Input** is about 2,880 tokens a query, mostly the 5 retrieved paragraphs. On Haiku, input and output each make up about half the cost, and thinking is about two-thirds of the output. So the two levers are:
  - **Thinking:** try `--effort low` on Haiku and check whether accuracy holds.
  - **Excerpt length:** cap the text per paragraph, or send fewer paragraphs.
- **Prompt caching:** little benefit expected (my inference). Only the ~420-word system prompt repeats between questions; the excerpts change every time. Check the caching docs before claiming this.
- **Batch API (50% off):** not usable, because users need live answers. It would suit offline evaluation runs.
- The biggest quality lever is not the model: the remaining misses are all retrieval.

### 4. At 10,000 users a day (estimate, not a measurement)

At an assumed 3 queries per user per working day, Haiku's API cost is about $378 a month, vs about $5,709 for Sonnet and $13,728 for Opus. At that scale the model bill stops being the main concern. These would matter more (my judgement):
- latency and rate limits under load
- monitoring answer quality on a weekly graded sample, so a model update or a new RBI amendment doesn't quietly reduce accuracy
- keeping the corpus current as RBI amends the Directions

### Write-up paragraph (draft)

> I ran the same 40-question test set through Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5 at medium effort, with retrieval and prompt fixed. All three scored 94% correct; Haiku had no hallucinations at $0.57 per 1,000 queries (about 5 paise a query) and a p95 latency of 6.7 s, against $8.65 and 7.2 s for Sonnet, while Opus missed the latency and cost targets. I chose Haiku because it was the cheapest model to meet every PRD threshold, and no larger model did better on multi-paragraph questions. The trade-off I accepted is a decision based on only 40 questions that were used for tuning, so I confirmed it on a 15-question holdout set, where Haiku again matched Sonnet (83%, no hallucinations). The surprise was that the three remaining misses were identical for every model and all were retrieval failures: a bigger model would not have fixed them.
