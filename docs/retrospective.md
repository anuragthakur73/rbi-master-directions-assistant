# Credit Assist: Retrospective

17 Nov 2026 · Anurag Thakur

In six weeks I built and deployed Credit Assist, a tool that answers bank staff's questions on three RBI credit Master Directions with a cited paragraph, or says the answer isn't there. On 15 questions it had never seen, it was 83% correct with no hallucinations, at about ₹0.05 a query. The gap is evidence from users: every test question so far was written by me, and tester feedback is still pending.

Links: [live app](https://credit-assist-rbi.streamlit.app) · [PRD](PRD.md) · [GitHub repo](https://github.com/anuragthakur73/rbi-master-directions-assistant)

## 1. What I set out to do

The goal was a reference tool that gives branch credit staff the current RBI rule, with its paragraph, in seconds instead of a manual PDF search.

**Why this problem.** In my retail credit work I saw two costs of staff applying a rule that had since changed. An auditor flagged a housing loan for breaching margin norms that had changed about a month before sanction. And a gold-loan customer, quoted an outdated LTV, took his business to another bank. The rules sit in long, amended Master Directions; the Credit Facilities direction alone runs to over 150 pages.

**User:** a branch credit or operations officer with a loan file open and a customer waiting.

**What it must never do:** give a sanction decision or legal opinion, accept customer data, or answer from outside the loaded documents.

**Targets set in the PRD before building** (hypotheses, not benchmarks):

- At least 85% of answers fully correct
- At least 90% citation accuracy, and at most 5% of answers with any unsupported claim
- At least 90% of out-of-scope questions refused
- p95 latency under 8 seconds and cost under ₹1 a query
- Testers rate trust 4/5 or higher, and find answers at least 50% faster than manual search

## 2. What I got

Every quality and operational target was met except full correctness on unseen questions (80% vs 85%); the two user metrics are not measured yet. All figures are from the deployed setup (Claude Haiku 5.5, hybrid retrieval, prompt v2), graded by hand.

| Metric | Target | Unseen (15 q) | Tuned (40 q) | Verdict |
|---|---|---|---|---|
| Fully correct | ≥ 85% | 80% | 92% | Missed on unseen |
| Correct, partial = 0.5 | — | 83% | 94% | Headline number: 83% |
| Citation accuracy | ≥ 90% | 100% | 100% | Met |
| Answers with an unsupported claim | ≤ 5% | 0% | 0% | Met |
| Out-of-scope questions refused | ≥ 90% | 2/2 | 8/8 | Met |
| p95 latency | < 8s | 4.2s | 6.7s | Met |
| Cost per query | < ₹1 | about ₹0.05 ($0.57 per 1,000) | | Met |
| Trust rating, time saved | ≥ 4/5, ≥ 50% faster | Not measured | | Open |

**I report 83%, not 94%.** The 40 questions were the ones I used to find and fix problems, so their score is optimistic. The 15 unseen questions were written after tuning and run once. Both samples are small: one unseen question moves the score by 6.7 points.

**How the score moved, one change at a time** (40 questions, Sonnet 5.5):

| Step | Change | Correct | What it fixed |
|---|---|---|---|
| Baseline | Semantic search, prompt v1 | 82% | — |
| Iteration 1 | Add keyword search and paragraph-number lookup (hybrid) | 91% | Expected paragraph retrieved 88% → 97%, for 3% more input tokens |
| Iteration 2 | Prompt v2: state limit breaches plainly, check scope before flagging conflicts | 94% | Two answer-quality failures |
| Holdout | 15 unseen questions, nothing changed | 83% | All three misses were retrieval |
| Model switch | Same setup on Haiku 5.5 | 94% / 83% | Same accuracy at about 1/15 of the cost |

## 3. Key design decisions and trade-offs

Each choice below was made on evidence from the test set, and each gave something up.

| Decision | Chosen | Rejected | Why | Cost of the choice |
|---|---|---|---|---|
| Corpus | 3 credit directions (618 paragraphs) | All 16 directions in the manifest | Small enough to hand-check every table and expected answer | Questions on KYC, IRAC and the rest are refused |
| Text quality | Hand-verified fixes: 15 text fixes, 3 tables re-entered from the PDF | Raw PDF extraction | A footnote number fused into "₹30,000" made "₹30,0007"; a RAG system repeats bad text as a confident answer | Manual fixes must be redone when RBI amends a table |
| Chunking | One chunk per RBI paragraph | Fixed-size or page chunks | The paragraph is what users cite, and page chunks split tables from their text | A heading can stick to the paragraph before it |
| Retrieval | Hybrid: embeddings + keyword (BM25) + paragraph-number lookup | Embeddings only | Embeddings miss numbers ("Para 52") and exact terms; 82% → 91% correct | No synonym lists, to avoid tuning to my own test set; "maximum" vs "shall not exceed" still fails |
| Model | Claude Haiku 5.5 | Sonnet 5.5 (first choice), Opus 5.5 | All three scored 94%; Haiku matched Sonnet on unseen questions at $0.57 vs $8.65 per 1,000 queries | Haiku uses more thinking tokens; run-to-run variation not measured |
| Refusal | Exact "Not found in the provided documents" sentence | Best-effort answers | A wrong rule is worse than no rule for a busy officer | Some answerable questions are refused when retrieval misses (2 of 13 unseen) |
| Trust checks | A code check after the answer: flag answers with no citation, or citing a paragraph that wasn't retrieved | A new prompt rule | Keeps the evaluated prompt and model exactly what is deployed | Catches made-up citations, not wrong readings of real ones |
| Build | Plain Python, no LangChain | A framework | Every step visible and explainable in an interview | More code to maintain by hand |

## 4. What failed and what I learned

The most useful lessons came from changes that looked like wins and weren't.

**1. A fix that didn't generalise: neighbour paragraphs.** All three unseen-question misses had the answer in the paragraph next to the one retrieved (219X → 219Y, 430 → 429, 219L → 219K). So I also sent the paragraphs on either side of the top hits.

| Test set | Expected paragraphs sent, before | After |
|---|---|---|
| 15 holdout questions (the ones that inspired the fix) | 10/13 | 13/13 |
| 16 fresh questions on random paragraphs | 12/14 | 12/14 |

It cost 46% more text per question and changed nothing on fresh questions. I left it off. *Lesson: a fix is only proven on data that didn't inspire it.*

**2. A prompt rule with a side effect.** Prompt v2 made refusals one short sentence, which fixed long-winded refusals. But on M08, which the documents answered in part, v1 had given the part it found; v2 refused the whole question. False refusals rose from 1 to 2 of 32, and v2 produced the first unsupported claim in any run (M03: "stamp duty would have to be funded by the borrower"). I kept v2 because it scored highest, and drafted v3 to allow partial answers. *Lesson: score every category after a prompt change, not just the total.*

**3. A hidden limit cut answers off.** The first runs truncated answers mid-sentence, because the model's thinking counts against the output limit. Raising the limit to 2,000 tokens and setting effort to medium fixed it: the gold-loan answer went from 7.2s and cut off to 4.5s and complete. *Lesson: read the model's settings before blaming the prompt.*

**4. My own tests found usability gaps.** In Week 5 testing, a feedback comment I typed landed in the question box, because pressing Enter gave no confirmation. I added a "Send comment" button with a confirmation message. *Lesson: if the builder gets it wrong, users will too.*

**Limits of this evaluation.** All 71 questions were written by me from the documents, and graded by me alone (the Opus run was graded by Claude, and my spot-check of it is still to do). The 95% confidence interval on 83% from 15 questions is roughly 60–95%. A blind second grader and real staff questions are the next fixes.

## 5. User feedback

Pending: the live link went to 4–5 testers in mid-November, and their feedback hasn't come in yet. This section will be filled from what they actually say, with no invented findings.

| Tester (generic role) | How tested | What they said (their words) | What I changed |
|---|---|---|---|
| | | | |

- 👍 / 👎 counts and comments, from the app's feedback log:
- Trust rating (1–5), "Would you use this at the counter?":
- Time to answer vs manual PDF search, same 5 questions:
- Questions asked that the tool couldn't answer, and which direction they needed:

## 6. V2 roadmap

V2 starts with users, not features: the biggest unknown is whether staff trust and use the tool, not its accuracy.

| # | Item | Why (evidence) |
|---|---|---|
| 1 | 5 conversations with credit staff, and a test set of their real questions | Every test question so far was written by me; the problem rests on my own experience |
| 2 | Amendment alerts: check each direction's "updated as on" date automatically and flag answers from a changed paragraph | Both incidents in section 1 were outdated rules; today the corpus check is manual and monthly |
| 3 | Fix wording gaps in retrieval (query rewriting), tested on a fresh unseen set | All misses on unseen questions were retrieval, not the model |
| 4 | Prompt v3: allow partial answers, ban consequences the text doesn't state | M08 and M03 (section 4) |
| 5 | Add the other 13 directions already listed in the manifest | Questions outside the 3 loaded directions are refused today |
| 6 | Login, stored logs and role-based access | Hosted logs reset when the app sleeps; a bank pilot would need an audit trail |
| 7 | Questions in Hindi and Marathi | v1 answers in English only (PRD edge case 10); worth testing with staff before building |
