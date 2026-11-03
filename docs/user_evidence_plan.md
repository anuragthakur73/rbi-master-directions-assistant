# User evidence plan

**Gap:** every test question so far was written from the documents. Real staff ask shorter, messier questions ("LTV for 25L flat?", "can we give gold loan in cash"), and nobody has yet confirmed that finding RBI rules is a real, frequent pain. For a product portfolio, this evidence matters more than the last few accuracy points.

**Goal:** 15–20 real-style questions, plus notes from 5 short conversations, by the end of Week 4.

## Ground rules (non-negotiable)

- Public RBI rules only. Collect **how people ask**, never internal circulars, bank process notes, customer names, account details or loan files.
- Ask people in a personal capacity, as ex-colleagues or peers. Don't use work channels or your employer's name, and check your employer's policy on outside professional activity before posting anything publicly.
- Rewrite any question that could identify a customer or a branch before you save it.
- Record your own recall separately from what others said, and label it in the `how_collected` column. Both are useful; they are not the same evidence.

## Sources, in order of value

1. **5 conversations** of about 15 minutes with people who handle retail or MSME credit (ex-colleagues, batchmates, contacts at other banks).
2. **Your own recall:** the 10 rule questions you were asked, or had to look up, most often.
3. **Public forums** where bankers discuss RBI rules. Use them for phrasing only, and note the source.

## Conversation script (about 15 minutes)

1. "When did you last need to check an RBI rule on a loan? What was the question, in your own words?"
2. "How did you find the answer: circular, colleague, controlling office, Google? How long did it take?"
3. "What happens when the answer is wrong or late?"
4. "Here is how this tool answered a similar question [show one answer with its citation]. Would you trust it? What would you need to see?"
5. "What else would you ask it?"

Write their questions down **verbatim**, before you tidy them.

## Turning it into evidence

- Add each question to `tests/real_questions_template.csv` (save it as `tests/test_set_real.csv`), then fill `expected_answer` and `expected_sources` from the PDF, as with v1. Questions about directions that aren't loaded are valid "not found" cases. Keep them: they show what to load next.
- Run it with `python scripts/run_eval.py --label real --test-set real`, grade by hand, and log it in `docs/eval_log.md`. Report it separately from the other sets.
- For the portfolio, write a short findings note: how many people, the top 3 pain points in their words, what changed in the product because of them, and one quote each for trust and for distrust.

Don't report any finding you didn't actually hear. Five honest conversations beat a large made-up number.
