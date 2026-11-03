# Design decisions: why Credit Assist is built this way

One page per decision: what was chosen, why, what the evidence was, and what was given up.
This is for explaining the project in an interview without notes. Where a reason is yours alone
(not visible in the code or logs), there is a **Your reason:** line to fill in in your own words.

Numbers come from `docs/eval_log.md` and `results/`. Code references are to files in `scripts/`.

---

## 1. Problem and user

- **User:** bank branch credit and operations staff, who need a specific RBI rule (LTV ceiling, reporting timeline, valuation requirement) while a customer or file is in front of them.
- **Problem:** the rules are spread across long Master Directions (the Credit Facilities PDF alone runs to over 150 pages), amended over time, with paragraph numbers like 219ZE. Searching the PDF is slow, and a wrong reading has compliance consequences.
- **What the tool is not:** it does not make sanction decisions or give legal advice (system prompt rule 3), and it uses public RBI text only, never internal circulars or customer data.
- **Your reason:** why this user and problem, from your own branch experience: ____

## 2. Corpus: 3 credit directions, not KYC and not all 16

- 16 public Master Directions are listed in `data/manifest.csv`; only 3 are indexed: Credit Facilities, Credit Information Reporting, Credit Risk Management (618 paragraphs, 648 chunks).
- The PRD started as "KYC Assist"; the build moved to credit directions in Week 2.
- **Trade-off:** a smaller corpus made hand-checking every table and gold answer possible. The cost is narrow coverage: questions on KYC, IRAC or wilful defaulters are refused. The test set uses exactly those as "not found" cases.
- **Your reason for switching from KYC to credit:** ____

## 3. Ingestion and cleaning: verify against the PDF, fix by hand where needed

- `ingest.py` extracts text per page with pypdf. Its layout mode was tested on 5 broken-table cases (`compare_layout.py`) and made no difference, so plain extraction was kept.
- `clean.py` drops contents pages, strips page numbers, moves amendment footnotes to metadata, removes deleted-paragraph placeholders, and applies 15 text fixes (`data/overrides/text_fixes.csv`) and 3 hand-entered tables (`data/overrides/*.md`), each checked against the source PDF page.
- **Why:** fused footnote numbers turned "₹30,000" into "₹30,0007". A RAG system repeats whatever the text says, so bad extraction becomes a confident wrong answer. Problems are documented in `data/overrides/ingestion_notes.md`.
- **Trade-off:** manual overrides don't scale to 16 documents, and must be redone when RBI amends a table.

## 4. Chunking: one chunk per paragraph, never by page

- `chunk.py` splits on paragraph numbers (including alphanumeric ones like 170A, 219ZE). Paragraphs over 3,000 characters (~750 tokens) are split at sub-clause boundaries, never mid-clause. Each chunk carries its citation, chapter, pages and amendment notes.
- **Why:** the answer has to be cited to a paragraph, and the paragraph is the unit RBI uses. Page-based chunks would split tables from the sentence that introduces them.
- **Known flaw:** a section heading that follows a paragraph sticks to that paragraph's chunk (e.g. CF 133O ends with "Chapter IX - Infrastructure Financing"). This is minor, but it adds noise to embeddings.

## 5. Embeddings and store: local and free

- BAAI/bge-small-en-v1.5 via fastembed (384 dimensions, cosine similarity), with the BGE query instruction prefix; stored in a local Chroma database.
- **Why:** no API key or cost, no data leaves the laptop, and good enough: the 6-question smoke test found 6/6 in the top 5.
- **Trade-off:** a small model misses wording gaps ("maximum" vs "shall not exceed", S11). A larger embedding model is a Week 4+ experiment.

## 6. Retrieval: hybrid (semantic + keyword + paragraph lookup)

- Fetch 10 chunks by embedding and 10 by BM25 keyword search (`keyword_search.py`), merge them with reciprocal rank fusion (each chunk scores 1/(60 + rank) per list), and put any paragraph named in the question ("Para 70 of CRM") first. Parts of one paragraph are grouped, and the top 5 distinct paragraphs go to Claude.
- **Why grouping:** in the smoke test, CIR Para 36's five parts filled all five slots.
- **Why hybrid:** embeddings match meaning, not numbers ("Para 52") or exact terms. Result: 82% → 91% correct, expected paragraph retrieved 88% → 97%, input tokens +3%. One variable changed.
- **Trade-off:** the light stemmer misses "renewed" vs "renewal" (M08). Synonym lists tuned to test questions were deliberately not added, to avoid overfitting.

## 7. Neighbour paragraphs: built, measured, not switched on

- `NEIGHBOURS = 1` also sends the paragraph before and after each of the top 3 hits (same chapter only).
- **Why it was tried:** all three holdout misses had the answer next to the retrieved paragraph (219X → 219Y, 430 → 429, 219L → 219K).
- **Evidence (retrieval only, no API cost):** "all expected paragraphs sent" 27/32 → 29/32 on the 40-question set and 10/13 → 13/13 on the holdout, but **12/14 → 12/14 on the fresh random set**. Excerpt text +46%.
- **Decision:** keep it off. The holdout gain mostly reflects the cases it was designed for. Revisit only if a full answer-quality run on the fresh set shows a gain worth the extra tokens.
- **This is the story to tell:** a fix that looked good on the data that inspired it, and didn't generalise.

## 8. Model and settings: Sonnet 5.5, effort medium, max_tokens 2000

- **Why:** the first run at the default effort with max_tokens 600 cut answers off. Thinking tokens count against max_tokens. Medium effort used 0 thinking tokens on simple lookups and some on calculations, and fixed the cut-offs (gold loan answer: 7.2s cut off → 4.5s complete).
- **Cost:** about $8.65 per 1,000 queries at the prices in `cost_report.py` (checked 29 Oct 2026), well under the PRD's ₹1 per query.
- **Next:** the Week 4 comparison with Haiku and Opus on the same questions (`run_eval.py --model`).

## 9. Prompt: every rule traces to a failure

| Rule | What it does | Failure that caused it |
|---|---|---|
| 1 | Cite every claim as [Doc, Para X] | Core requirement: users must verify |
| 2 | Exact refusal sentence + at most one related line | Long refusals in v1 |
| 3 | No outside knowledge, no sanction decision | Test 6 (instruction override), test 5 (decision request) |
| 4 | Compare figures with "shall / not exceed" limits and say plainly if exceeded | A02: "exceeds that band" instead of "breaches the 90% ceiling"; your own catch on "85% is not covered" |
| 5 | Answer with a stated assumption when one reading is clear | Unneeded clarifying questions (M06) |
| 6 | Show calculation steps with citations | Multi-paragraph LTV + stamp duty questions |
| 7 | Check scope before flagging a conflict | S12: a false 360 vs 365-day conflict |
| 8 (v3, candidate) | No consequences the excerpts don't state | M03: "stamp duty would have to be funded by the borrower" |

## 10. Evaluation: how the numbers were produced

- 40 questions in 4 categories (single, multi, not-found, adversarial), each with gold answers and source paragraphs; graded by hand for correctness, citation and hallucination; auto-checks are only a first pass.
- One change per iteration, logged in `docs/eval_log.md`.
- Holdout of 15 unseen questions run once after tuning: **83%** vs 94% on the tuned set. Report 83% as the headline.
- **Limits, and say them before you're asked:** small samples (one holdout question = 6.7 points; the 95% interval on 83% is roughly 60–95%), one grader (fix: `second_grader.py`), and questions written from the documents rather than by real users (fix: `docs/user_evidence_plan.md`).

## 11. Interview questions to practise

1. Why RAG instead of fine-tuning a model on the directions?
2. How do you know it doesn't hallucinate? What exactly counts as a hallucination in your grading?
3. Why is the holdout score lower than the tuned score, and which one do you report?
4. Walk me through one failure end to end: question, what was retrieved, what Claude said, the fix.
5. What happens when RBI amends a direction tomorrow?
6. What would you need before putting this in front of 100 branch staff? (Access control, logging policy, user testing, legal review, an update process, a feedback button.)
7. Why not switch on neighbour paragraphs, given it fixed the holdout misses?
8. What does a query cost, and what would you change to halve it?
