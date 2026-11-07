# Evaluation log

Each entry records a test run: what changed, what was tested, the result, and what to do next.

---

## 24 Oct 2026: Smoke test v0 (retrieval only)

**Setup**
- Corpus: 3 RBI credit directions (Credit Facilities, Credit Information Reporting, Credit Risk Management), cleaned with `scripts/clean.py`.
- Chunking: one chunk per paragraph, long paragraphs split at sub-clauses (`scripts/chunk.py`); 648 chunks.
- Embeddings: BAAI/bge-small-en-v1.5 (local, via fastembed), stored in Chroma, cosine similarity.
- Test: 6 questions with a known correct paragraph; pass = correct paragraph in the top 5 results.

**Result: 6/6 found in the top 5; 5/6 at rank 1.**

| Question | Expected | Rank |
|---|---|---|
| Max LTV for a gold loan of ₹4 lakh? | CF Para 44 | 1 |
| LTV and risk weight for an ₹80 lakh home loan? | CF Para 111 | 1 |
| Compensation for a delayed credit report correction? | CIR Para 36 | 1 |
| Valuation reports for a ₹60 crore property? | CRM Para 70 | 1 |
| Is a bank guarantee funded or non-funded (country risk)? | CRM Para 47 | 1 |
| What does Para 52 of Credit Facilities say? | CF deleted paragraphs | 4 |

**Observations**
- The two hand-cleaned table overrides (CF Para 111, CRM Para 47) both ranked first.
- CIR Para 36 filled all 5 result slots with its own 5 parts. Long split paragraphs can crowd out other relevant rules on broader questions.
- Questions that name a paragraph number retrieve poorly: embeddings match meaning, not numbers ("52").

**Next**
- Step 5: group parts of the same paragraph when building the context for Claude.
- Week 3 candidate: when a question names a paragraph number, look it up directly instead of searching for it.
- Week 3: expand from 6 to 30–50 test questions.

---

## 25 Oct 2026: End-to-end test v0 (retrieval + Claude)

**Setup**
- `scripts/answer.py`: top 10 chunks → grouped into the top 5 distinct paragraphs → Claude.
- Model `claude-sonnet-5-5`, effort `medium`, max_tokens 2000, system prompt `prompts/system_prompt_v1.md`.
- Earlier run at the default effort with max_tokens 600 was cut off. Thinking tokens count against max_tokens, so the limit was raised and effort set to medium. After the change: 0 thinking tokens on simple lookups, and the gold-loan answer went from 7.2s (cut off) to 4.5s (complete).

**Result: 5/6 pass, 1 partial.**

| # | Test | Question | Result | Notes |
|---|---|---|---|---|
| 1 | Direct | Max LTV for a gold loan of ₹4 lakh? | ✅ | 80% [CF 44]; 334 out tokens, 4.5s |
| 2 | Not found | Minimum CIBIL score for a home loan? | ✅ | Exact refusal wording; top similarity 0.66 (vs 0.81 on a real hit) |
| 3 | Two paras | House ₹9 lakh + ₹50k stamp duty: max loan? | ✅ | ₹8.55 lakh [CF 111 + 113], steps shown; 318 thinking tokens, 7.0s |
| 4 | Vague | What's the LTV limit? | ⚠️ | Asked for clarification (correct) but omitted housing LTV: CF 111 not retrieved |
| 5 | Decision | Sanction ₹50 lakh home loan at 85% LTV? | ✅ | Declined decision; 80% ceiling, post-2017 table; separated gold 85% |
| 6 | Override | Ignore the documents… delayed CIR compensation | ✅ | Refused outside knowledge; Para 36 facts correct; 8,117 input tokens (whole Para 36) |

**Observations**
- Retrieval: CF Para 44 (gold) ranks first even on housing questions; the word "LTV" dominates. CF Para 111 was missed entirely on the vague question.
- Prompt: "85% is not covered by the table" is too soft; Para 111 says "shall abide by", so the answer should say 85% exceeds the ceiling.
- Cost: long merged paragraphs (CIR 36) raise input tokens about 4x.
- Possible refinement: the not-found case could cite related rules (CRM Para 11 requires obtaining CIRs), but those paragraphs were not retrieved.

**Next (Week 3 candidates)**
- Retrieval: test adding keyword search (hybrid) or more distinct results so housing and gold rules both appear for generic LTV questions.
- Prompt v2: "When a proposed figure exceeds a limit, say so directly."
- Test question to add: existing ₹2 lakh gold loan + new ₹4 lakh loan (Para 44 slabs use the total per borrower).
- Week 4: cap excerpt length per paragraph, or send only the retrieved parts, to control input tokens.

---

## 28 Oct 2026: Baseline v1 (40 questions)

**Setup**
- `scripts/run_eval.py --label baseline`, scored with `scripts/score_eval.py`; all 40 answers graded by hand.
- Model `claude-sonnet-5-5`, effort `medium`, top 5 paragraphs, system prompt `prompts/system_prompt_v1.md`.
- Questions: 19 single-paragraph, 9 multi-paragraph, 7 not in the corpus, 5 adversarial.
- Results file: `results/eval_baseline_20261028_2234.csv`.

**Result: 82% correct (33/40, partial = 0.5); 0 hallucinations.**

| Metric | Result |
|---|---|
| Correct (partial = 0.5) | 82% (33/40) |
| Fully correct | 78% (31/40) |
| Correct refusals (out-of-corpus) | 100% (8/8) |
| False refusals (answerable but refused) | 9% (3/32) |
| Citation accurate (manual) | 100% (29/29) |
| Hallucination rate (manual) | 0% (0/40) |
| Retrieval: expected para sent to Claude | 88% (28/32); rank 1 in 22 |
| Latency median / p95 | 2.8s / 6.1s |
| Avg tokens in / out | 2565 / 277 |

| Category | Correct | Questions |
|---|---|---|
| single | 82% (15.5/19) | 19 |
| multi | 83% (7.5/9) | 9 |
| not_found | 100% (7/7) | 7 |
| adversarial | 60% (3/5) | 5 |

**Observations**
- Retrieval missed the expected paragraph on S05, S11, S13 and A05. Low-rank hits: M04 (rank 5), S17 (rank 4).
- Adversarial is the weakest category. A02 and A04 were flagged by the auto-check even though their paragraph was retrieved at rank 1, so the issue there is likely the answer, not retrieval.
- The auto-check flagged N03, N04, N05 and A01 as "answered", but hand grading scored 8/8 correct refusals. The auto-check's refusal detection probably misses some refusal wordings.
---

## 29 Oct 2026: Iteration 1 - hybrid retrieval (40 questions)

**Change (one variable):** retrieval mode `semantic` → `hybrid` (`scripts/keyword_search.py`, `RETRIEVAL_MODE` in `answer.py`). Hybrid adds direct paragraph lookup ("Para 70 of CRM") and BM25 keyword search, merged with the embedding results by reciprocal rank fusion. Same model (claude-sonnet-5-5, effort medium), same top 5 paragraphs, same system prompt v1.

**Result:** `results/eval_hybrid_20261028_2324.csv`, graded by hand.

| Metric | Baseline (semantic) | Hybrid |
|---|---|---|
| Correct (partial = 0.5) | 82% (33/40) | **91% (36.5/40)** |
| Fully correct | 78% (31/40) | 88% (35/40) |
| Correct refusals (out-of-corpus) | 100% (8/8) | 100% (8/8) |
| False refusals | 9% (3/32) | 3% (1/32) |
| Citation accurate | 100% | 100% |
| Hallucination rate | 0% | 0% |
| Expected paragraph sent to Claude | 88% (28/32) | 97% (31/32) |
| Avg input tokens | 2,565 | 2,635 (+3%) |
| Median / p95 latency | 2.8s / 6.1s | 2.8s / 6.1s |

**Fixed:** S05 (Para 41 now retrieved), S13 (Para 215), A05 (Para 70 via paragraph lookup), A04 (Para 111 now retrieved; clean clarifying question). Improved but still partial: M04 (Para 130 retrieved, Para 132 still missing). No question got worse.

**Still failing**
- S11 (false refusal): question says "maximum", Para 170I says "shall not exceed". No shared words, and the 170F chunk is only a heading.
- M08: question says "renewed", Para 65 says "renewal"; the light stemmer does not match them.
- S12 (partial): still flags a false 360 vs 365-day conflict; Para 250 (context for 251) not retrieved.
- A02 (partial): says 90.3% "exceeds that band" but not plainly that it breaches the 90% ceiling.

**Decision:** keep hybrid as the default. It passes the PRD target (≥ 85% correct) at almost no extra cost.

**Caution:** the test set was also used to diagnose the misses, so this score may be slightly optimistic. I did not add word lists tuned to these questions; the remaining wording-gap failures were left in on purpose.

**Next (Iteration 2):** system prompt v2: state plainly when a figure exceeds a limit (A02); before flagging a conflict, check whether one paragraph applies only to a narrower case (S12); keep refusals to at most one line of related context.

---

## 29 Oct 2026: Iteration 2 - system prompt v2 (40 questions)

**Change (one variable):** `prompts/system_prompt_v1.md` → `prompts/system_prompt_v2.md`. Retrieval stays hybrid; same model, effort and top 5 paragraphs. v2 changes: refusal sentence first with at most one related-paragraph line (rule 2); compare figures against mandatory limits and say plainly when exceeded (rule 4); answer with a stated assumption when one reading is clear (rule 5); check scope before flagging a conflict (rule 7).

**Result:** `results/eval_prompt_v2_20261029_0020.csv`, graded by hand.

| Metric | Baseline (semantic, v1) | Iter 1 (hybrid, v1) | Iter 2 (hybrid, v2) |
|---|---|---|---|
| Correct (partial = 0.5) | 82% | 91% | **94% (37.5/40)** |
| Fully correct | 78% | 88% | 92% (37/40) |
| Correct refusals | 100% | 100% | 100% |
| False refusals | 9% (3/32) | 3% (1/32) | 6% (2/32) |
| Citation accurate | 100% | 100% | 100% |
| Hallucination rate | 0% | 0% | 2.5% (1/40, minor) |
| Expected paragraph sent to Claude | 88% | 97% | 97% |
| Median / p95 latency | 2.8s / 6.1s | 2.8s / 6.1s | 3.4s / 7.2s |
| Avg input tokens | 2,565 | 2,635 | 2,880 |

By category (iter 2): single 95%, multi 83%, not-found 100%, adversarial 100%.

**Fixed by v2:** A02 now says "90.3% exceeds the 90% ceiling" and gives the maximum (₹27.9 lakh) without making a sanction decision (rule 4). S12 gives 360 days as the general rule and treats the 365-day paragraphs as narrower cases instead of flagging a false conflict (rule 7). Refusals are now one or two lines (rule 2), and M06 answers directly instead of asking a question (rule 5).

**Trade-offs found**
- M08: v1 gave the LEI rule and then said the renewal rule was "not found"; v2 collapses this into a one-line refusal. Same score, but less useful, so false refusals rise from 1 to 2. Rule 2 is too strict for questions the excerpts answer partly.
- M03: one minor unsupported inference ("stamp duty would have to be funded by the borrower"); first hallucination in any run.
- Cost and speed: input tokens +9% (longer prompt), median latency +0.6s.

**Still failing (retrieval, not prompt):** S11 (Para 170I, "maximum" vs "shall not exceed"), M08 (Para 65, "renewed" vs "renewal"), M04 partial (Para 132).

**Decision:** adopt v2 as the default (`SYSTEM_PROMPT_FILE` in `answer.py`). It scores highest and fixes the two answer-quality failures.

**Candidates for v3 / later:** let partial answers through ("answer the part the excerpts cover, then say which part is not found"); add "do not add consequences or advice the excerpts don't state". Retrieval: query rewriting or synonym expansion for wording gaps; merge heading-only chunks such as Para 170F with their sub-paragraphs.

**Caution:** the same 40 questions were used to find and fix problems, so these scores are likely optimistic. A fresh set of 10-15 unseen questions would give a fairer check before the retrospective.

---

## 29 Oct 2026: Holdout check - 15 unseen questions (final Week 3 setup)

**Setup:** hybrid retrieval + system prompt v2 + claude-sonnet-5-5 (effort medium, top 5 paragraphs), unchanged from Iteration 2. `tests/test_set_holdout.csv`: 15 questions written after tuning, on paragraphs the 40-question set never asked about (7 single, 4 multi, 2 not-found, 2 adversarial). Run once and graded by hand; nothing was changed because of these results.

**Result:** `results/eval_holdout_20261029_0032.csv`

| Metric | Tuned set (40 q, Iter 2) | Holdout (15 q) |
|---|---|---|
| Correct (partial = 0.5) | 94% | **83% (12.5/15)** |
| Fully correct | 92% | 80% (12/15) |
| Correct refusals | 100% | 100% (2/2) |
| False refusals | 6% | 15% (2/13) |
| Citation accurate | 100% | 100% |
| Hallucination rate | 2.5% | 0% |
| Median / p95 latency | 3.4s / 7.2s | 2.8s / 4.1s |

By category (holdout): single 71% (5/7), multi 88%, not-found 100%, adversarial 100%.

**What held up on unseen questions:** no hallucinations; both out-of-corpus questions refused; both adversarial questions handled (refused an "authorised" request to skip the documents and confirm 95% LTV; corrected a false premise on gold LTV). Prompt v2's rule 4 worked on new cases: H10 "3.6:1 exceeds the 3:1 ceiling, max debt ₹750 crore"; H08 "₹30 lakh exceeds the ₹25 lakh limit".

**All three misses were retrieval, not the model:**
- H05: the guarantee paragraph (219X) was retrieved but the collateral rule (219Y, 50% with 25% in cash) was not, leading to a false refusal. The auto "retrieval hit" counted 219X, so the 92% retrieval figure overstates this case.
- H06: Para 429 (BBB minus) not retrieved; its neighbour Para 430 was. False refusal.
- H08 (partial): Para 219K (₹1 crore cap) not retrieved, so it could not confirm the overall amount.

**Reading:** the 11-point gap between the tuned set (94%) and the holdout (83%) is the expected optimism from tuning on the same questions. 15 questions is a small sample (one question = 6.7 points), so treat 83% as indicative. **Report ~83% on unseen questions as the headline number**, with 94% on the tuned set alongside. Accuracy on unseen questions is still close to the PRD target (≥ 85%); the gap is mostly retrieval.

**Pattern for V2 / later:** the answer is often in the paragraph *next to* the one retrieved (219X → 219Y, 430 → 429, 219L → 219K). Candidate fix: also fetch neighbouring paragraphs (±1) of top hits, or chunk sub-paragraph series (e.g. 219J-219L, 170F-170L) together. Test it on the 40-question set first, then on a *new* holdout set, since this one has now been seen.

---

## 3 Nov 2026: Week 4 prep - neighbour paragraphs (retrieval only) and a fresh test set

**Change tested (one variable, retrieval only, no API calls):** `NEIGHBOURS = 1` in `answer.py` also sends the paragraph before and after each of the top 3 retrieved paragraphs (same chapter only), after the usual top 5. This is the candidate fix from the holdout check (219X → 219Y, 430 → 429, 219L → 219K).

**New measure:** `retrieval_all` = every expected paragraph was sent, not just one. The old `retrieval_hit` counted H05 as a hit although the answer paragraph (219Y) was missing.

**New test set:** `tests/test_set_fresh.csv`, 16 questions on randomly chosen paragraphs (seed 20261103) that no earlier question used. Only retrieval was checked; nothing was changed because of it.

| Test set | Neighbours off: all expected sent | Neighbours on (top 3): all expected sent | Excerpt text sent (mean characters) |
|---|---|---|---|
| v1 (40 q, tuned) | 27/32 | 29/32 (M04, M08 fixed) | 6,016 → 8,765 (+46%) |
| Holdout (15 q, now seen) | 10/13 | 13/13 (H05, H06, H08 fixed) | 4,920 → 7,305 |
| Fresh (16 q, unseen) | 12/14 | 12/14 (no change) | |

Other settings tried: neighbours of the top 1 only (holdout 12/13, v1 28/32, +15% text); of all top 5 (v1 30/32, +76% text).

**Reading:** the fix works on the cases it was designed from, but makes no difference on fresh questions, whose two misses (F06: CF 219ZE, F15: CF 47) are not neighbour cases. The holdout improvement is mostly the same optimism as tuning on a test set.

**Decision:** keep `NEIGHBOURS = 0` as the default. Next, run the full answer evaluation on the fresh set with neighbours off and on (`--test-set fresh --neighbours 1`, about 32 API calls), grade by hand, and switch it on only if answer quality improves enough to justify about 46% more excerpt text.

**Environment note:** these checks ran outside the laptop (Python 3.13, fastembed 0.9.1, the same Chroma store and chunks). The baseline gave 30/32 for "expected paragraph sent" instead of the 31/32 logged on 29 Oct: S13 (CF 215) dropped from rank 2 to just outside the top 5. Small numeric differences between library versions can do this. All comparisons above were made in the same environment. To confirm on the laptop (free): `python scripts/run_eval.py --retrieval-only` and `python scripts/run_eval.py --retrieval-only --neighbours 1`.

**Also added:** prompt v3 candidate (`prompts/system_prompt_v3.md`: partial answers allowed; no unstated consequences), `scripts/second_grader.py` (blind second grading + agreement), `docs/user_evidence_plan.md` and `tests/real_questions_template.csv`. None of these change the reported Week 3 numbers.


---

## 5 Nov 2026: Week 4 model comparison

**Change (one variable):** the model. Setup fixed: test set v1 (40 questions), hybrid retrieval, top 5 paragraphs, prompt v2, effort medium, neighbours off. Sonnet = the Week 3 prompt v2 run (`eval_prompt_v2_20261029_0020.csv`); Haiku = `eval_haiku_20261105_1424.csv`; Opus = `eval_opus_20261105_1427.csv`.

**Grading:** Sonnet and Haiku graded by me. Opus graded by Claude against the expected answers and the source paragraph text; every note is prefixed "Claude-graded:". Claude re-checked M04, M05, M08, A02 and S07 against the text. **My own spot-check of the Opus grades is still to do.** Haiku M04 changed from no to partial, to match its note and the Opus grade for the same miss (README rule: right but missing a condition = partial).

**Known bias:** prompt v2 was tuned on Sonnet's Week 3 answers.

**Prices:** Claude pricing page, checked 3 Nov 2026, standard API. ₹ column at RBI reference rate ₹94.8416/USD (4 Nov 2026).

#### Model comparison

| Model | Correct | Correct refusals | False refusals | Hallucinations | Median / p95 latency | Avg tokens in / out (thinking) | Cost per 1,000 queries (USD) | (₹) |
|---|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 (medium) | 94% | 8/8 | 2/32 | 1/40 | 3.4s / 7.2s | 2,880 / 289 (42) | $8.65 | ₹820 |
| claude-haiku-5-5 (medium) | 94% | 8/8 | 1/32 | 0/40 | 2.5s / 6.7s | 2,880 / 569 (372) | $0.57 | ₹54 |
| claude-opus-5-5 (medium) | 94% | 8/8 | 1/32 | 0/40 | 5.6s / 10.6s | 2,874 / 465 (174) | $20.80 | ₹1,973 |

Prices: https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-11-03), standard API, no caching or batch discount.
Cost per query = input tokens x input price + output tokens (including thinking) x output price.

#### Correct by question type

| Question type | claude-sonnet-5-5 (medium) | claude-haiku-5-5 (medium) | claude-opus-5-5 (medium) |
|---|---|---|---|
| single | 18/19 | 18/19 | 18/19 |
| multi | 7.5/9 | 7.5/9 | 7.5/9 |
| not_found | 7/7 | 7/7 | 7/7 |
| adversarial | 5/5 | 5/5 | 5/5 |

Partial = 0.5. Routing only makes sense if a cheaper model matches the larger one on a whole question type (e.g. single-paragraph lookups) AND the type can be told apart before answering.

#### Scale estimate

Estimate, not a measurement: 10,000 users x 3 queries a day x 22 working days = 660,000 queries a month, at the per-query cost measured above.

| Model | Est. API cost per month (USD) |
|---|---|
| claude-sonnet-5-5 (medium) | $5,709 |
| claude-haiku-5-5 (medium) | $378 |
| claude-opus-5-5 (medium) | $13,728 |

Excludes hosting, embeddings (run locally), retries and the Batch API / caching discounts.

**Reading:**
- All three models score 37.5/40 (94%), with the same score on every question type.
- The three misses are the same questions for every model (S11, M04, M08), and all are retrieval failures: the answer paragraph (CF 170I, CF 132, CRM 65) was never sent. A bigger model does not fix them.
- Opus fails two PRD targets: p95 10.6s (target < 8s) and about ₹1.97 a query (target < ₹1).
- Haiku used the most thinking (372 tokens vs 42 for Sonnet) and was still about 15x cheaper than Sonnet.
- 40 questions is small: one question = 2.5 points, so a tie means "not distinguishable here", not "equal".

**Not used:** `eval_opus_20261105_2043.csv` is a second, ungraded Opus run. It could be graded later to measure run-to-run variation.


---

## 6 Nov 2026: Haiku holdout check

**Purpose:** confirm the Week 4 choice on questions not used for tuning. Pass mark, set before the run: correct ≥ 11.5/15 (within one question of Sonnet's 12.5), 0 hallucinations, both refusals correct.

**Run:** `python scripts/run_eval.py --label holdout_haiku --test-set holdout --model claude-haiku-5-5 --effort medium` → `results/eval_holdout_haiku_20261105_2137.csv`. Graded by me; Claude reviewed the grades and corrected three to match the README rules and the Sonnet holdout grading:
- H05: yes → no. False refusal; CF 219Y not retrieved.
- H06: yes → no, hallucination yes → no. False refusal; CF 429 not retrieved; nothing it said was outside the retrieved text.
- H08: yes → partial. ₹1 crore cap (CF 219K) not retrieved, so it could not be confirmed. Sonnet got partial for the same gap.

Citation column cleared for the four refusals (rule: blank if refused).

| Metric | Sonnet 5.5 (29 Oct) | Haiku 5.5 (5 Nov) |
|---|---|---|
| Correct | 83% (12.5/15) | 83% (12.5/15) |
| Correct refusals | 2/2 | 2/2 |
| False refusals | 2/13 | 2/13 |
| Citation accurate | 11/11 | 11/11 |
| Hallucinations | 0/15 | 0/15 |
| Median / p95 latency | 2.8s / 4.1s | 3.2s / 4.2s |
| Avg tokens in / out | 2,470 / 264 | 2,470 / 496 |

**Result: pass.** Same score, same three misses (H05, H06, H08), all retrieval. **Decision: default model switched to `claude-haiku-5-5` in `scripts/answer.py`.**

**Lesson for grading:** a "Not found" reply to an answerable question is always `no`, even when the cause is retrieval. Note the missing paragraph in `manual_notes`.
**Switch check (7 Nov 2026):** CLI and Streamlit both run on claude-haiku-5-5. Gold LTV question → 85%, Para 44. Answerable question in app → [what it said, para cited]. "Current repo rate" → correct refusal.