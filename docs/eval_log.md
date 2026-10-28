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