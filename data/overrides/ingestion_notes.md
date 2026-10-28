# Ingestion notes: Week 2, Step 2

**Date:** 24 Oct 2026
**Script:** `scripts/ingest.py` (pypdf, default extraction mode)
**Scope:** The three credit directions that v0 is built on. The other 13 PDFs in the corpus have not been reviewed yet.
**Method:** I read the extracted `.txt` output for each document and checked the high-value sections (the ones used in `prompts/test_context.md`) line by line. Items marked **[verified in PDF]** were then checked against the source PDFs on 24 Oct 2026.

Each issue gets one of three decisions:
- **Fix now:** resolve before Step 3.
- **Chunking:** handle with cleaning or chunking rules in Step 3.
- **Accept:** a known limitation for v0, to be documented in the README.

---

## Summary

| Document | Pages | Updated as on | Prose quality | Table quality | Main risk |
|---|---|---|---|---|---|
| Credit Facilities Directions, 2025 (RBI/DOR/2025-26/154) | 153 | 1 Oct 2026 | Good | Mixed | Tables and paragraphs split across page breaks; one annex appears empty |
| Credit Information Reporting Directions, 2025 (RBI/DOR/2025-26/156) | 74 | 1 Jul 2026 | Good | Poor in annexes | Footnote numbers fused into amounts and paragraph labels |
| Credit Risk Management Directions, 2025 (RBI/DOR/2025-26/157) | 53 | 1 Oct 2026 | Good | Mixed | Two-column table merged row by row |

**Overall:** The body text of all three documents is usable. Paragraph numbers, ₹ amounts, ≤/≥ signs and curly quotes survived extraction. The main problems are structural (page breaks, footnotes, contents pages, deleted paragraphs) and a few tables. None of them blocks Step 3. Every one of them would produce wrong or uncited answers if the text were chunked page by page without cleaning.

---

## Issues common to all three documents

| # | Issue | Example | Decision |
|---|---|---|---|
| C1 | **Contents pages** repeat every heading with dotted leaders, so a search for a heading matches the contents line before the real section. | CF pp. 1–5, CIR pp. 1–2, CRM p. 1 | Chunking: drop contents pages from the index. |
| C2 | **Page furniture.** A standalone page number ends every page, and the Hindi masthead on page 1 is garbled (`भारतीय �रज़वर् बैंक`). | Every page | Chunking: strip lines that are only a number; strip the masthead. |
| C3 | **Paragraphs and tables cross page breaks.** If each page becomes a chunk, a table is separated from the paragraph number that introduces it. | CF Para 44: the intro is on p. 34 and the LTV table on p. 35. CF Para 111: the post-2017 table is on p. 55; the proviso and pre-June-2017 table are on p. 56. | **Chunking: split by paragraph number, not by page.** This is the most important rule for citations. |
| C4 | **Amendment footnotes** sit mid-page and interrupt paragraphs that run onto the next page. The bracket markers `N[ ... ]` stay in the text. | CF Para 4(iva) "Bridge Finance" is split across pp. 7–8, with three footnotes in between. | Chunking: move footnotes ("Inserted / Substituted / Deleted with effect from …") into chunk metadata as `amended_on`, and strip `N[` and `]` markers. Footnote dates are useful later for "is this rule current?" questions. |
| C5 | **Deleted paragraphs** survive as `*****` placeholders. | CF Ch. V (Paras 51–60), Ch. XI (158–170), Ch. XIII (176–214). CRM Ch. V-A (24–42), Ch. XI (78–91). | Chunking: drop chunks that contain only `*****`. Keep a list of deleted paragraph numbers so the assistant can say "this paragraph has been deleted" rather than "not found". |
| C6 | **Stray spaces inside words and numbers.** | "Comm   ercial", "Reser   ve", "ov erdraft", "non-      fund-based"; reference number "DOR.CRE.REC.73/    07-01-    001/2025-      26"; CRM footnote 19 "October 0 1, 2026" | Chunking: collapse repeated whitespace and rejoin hyphenated words (`word-  word` → `word-word`). Accept that split words like "Comm ercial" will remain; they barely affect embeddings. Fix the reference numbers in metadata by hand. |
| C7 | **Alphanumeric paragraph numbers.** | CF 5A–5C, 60A–60M, 133A–133O, 137A, 170A–170S, 219A–219ZE; CRM 15A, 42A–42T, 91A–91O | Chunking: the paragraph-splitting regex must match `^\d+[A-Z]{0,2}\.`, not just `^\d+\.`. |

---

## 1. Credit Facilities Directions, 2025 (153 pages)

**Parsed well**
- All 18 chapters and the paragraph numbering in the body.
- The gold and silver LTV table (Para 44): the three slabs (≤ ₹2.5 lakh → 85%, > ₹2.5–5 lakh → 80%, > ₹5 lakh → 75%) are readable.
- The housing loan LTV and risk-weight table (Para 111): rows and values are readable.
- The eligible-securities LTV table (Para 219G), the project finance database list (Para 85), and the definitions in Para 4.

**Problems**

| Issue | Where | Decision |
|---|---|---|
| The Para 111 table header is broken across lines ("LTV / Ratio (%)"), and the "> 80 and ≤ 90" row has no row label. Its loan slab (up to ₹30 lakh) is only implied by the row above. | p. 55 | **Fix now:** hand-write a clean text version of this table as an override file (`data/overrides/`). This is a test-pack question. |
| The pre-June-2017 table for Para 111 is on the next page, without the paragraph number. A retrieved chunk could present the old LTV slabs as current. | p. 56 | Chunking (rule C3), and keep it inside the Para 111 chunk with the label "loans sanctioned till 06 Jun 2017". |
| Para 44 is split from its table by a page break. | pp. 34–35 | Chunking (rule C3). |
| In the DLG illustration table (Para 24), the column headers are stacked word by word ("Loan / maturing / without / default"). The figures are intact. | p. 29 | Accept: low question value. |
| The Annex V GML return is badly garbled ("linked GML #" and "GMS-" are separated). | p. 153 | Accept: it is a reporting template, not a rule. |
| Annex I ("Digital Lending – Data to be submitted on the CIMS portal") has a title but no content in the extracted text. **[verified in PDF]:** the page holds a blank reporting template (column headings such as Name of the DLA, Link to DLA, Grievance Redressal Officer details) embedded as an image, which pypdf cannot read. No rules are missing. | p. 149 | Accept: it is an empty template. The reporting duty itself is in Para 18 and is indexed. |
| The definition clauses use mixed numbering ((ia), (iva), (xxiia), (xxxa)), and some brackets are unbalanced (for example, a stray `]` after (vb)). | pp. 7–14 | Chunking: cite definitions as "Para 4(1)(xxiia)". Strip stray brackets. |

---

## 2. Credit Information Reporting Directions, 2025 (74 pages)

**Parsed well**
- The list of the four CICs with registration dates (Para 4(2)).
- The reporting timelines (Para 10), and the compensation framework of ₹100 per calendar day beyond 30 days, with the 21-day CI / 9-day CIC split (Para 36).
- The SARFAESI display rules (Paras 21–22) and the TWG chapter.

**Problems**

| Issue | Where | Decision |
|---|---|---|
| **Superscript footnote numbers are fused into the text with no bracket.** This corrupts amounts and creates fake paragraph labels. "₹30, 0007" is ₹30,000 plus footnote 7. "₹30,00013" is ₹30,000 plus footnote 13. "Table 317" is Table 3 plus footnote 17. "1A CI shall…", "2A CI shall…" and "3A CI shall…" are footnotes 1–3 plus "A CI", and look exactly like paragraph labels such as "5A". | Paras 10(2), 12(10), 15; Annex III | **Fix now:** this is the most serious data-quality finding. Without a fix, the paragraph regex from rule C7 will create fake Paras "1A", "2A" and "3A", and the SHG threshold reads as ₹3,00,007. Hand-correct these occurrences in a cleaning step, and re-check whether layout mode avoids the fusion. |
| The document uses "CI" (credit institution) throughout but never defines it in its own definitions section. Branch staff will ask about "banks". | Throughout | Chunking/prompt: add "CI = credit institution (here, the bank)" to the system prompt, or to the text of each chunk from this document. |
| The illustrations in Para 36 contain margin notes that land mid-line ("– 7 days delay  32 days", "32 + 4 = 36 days"). | pp. 22–25 | Accept: the figures still match the worked text. Keep each "Case n" whole within a chunk. |
| Annex I (the Uniform Credit Reporting Format, about 31 pages of field tables) is heavily garbled: column cells interleave and footnote numbers attach to field names ("Class of Activity 3", "Restructuring4"). | pp. 33–63 | Chunking: **exclude Annex I from the v0 index.** It is a file-format specification, not a question branch staff would ask, and as noise it would crowd out real answers. |
| In the state-code catalogue, several code–state pairs look swapped: MH → Madhya Pradesh, ML → Maharashtra, HP → Haryana, HR → Himachal Pradesh, JH → J&K, JK → Jharkhand, CG/CH and DD/DN. **[verified in PDF]:** the PDF shows the same pairings, so extraction is correct and the misalignment is in the source document itself. | p. 59 | Accept: excluded with Annex I. Note as a source-document error; never answer state-code questions from this table. |
| The Annex III SHG tables are readable, apart from superscript artifacts ("Above 10 … th: 5") and fused footnotes (see the first row). | pp. 65–71 | Chunking: keep, after the footnote fix. |
| The Annex VI timeline table has merged headers. Its dates (9th → 13th → 16th → 20th, and so on) are intact. | p. 74 | Accept: Para 10 states the same rule in prose. |
| The contents page lists Annex VI as page "734". | p. 2 | Accept: contents pages are dropped (rule C1). |

---

## 3. Credit Risk Management Directions, 2025 (53 pages)

**Parsed well**
- The cleanest of the three.
- Valuation and empanelment of valuers (Paras 69–73), including two independent valuation reports for properties of ₹50 crore or above. This is a test-pack question.
- The related-party materiality thresholds table (Para 42I), the LEI rules (Paras 63–68), and the CC/current/OD account framework (Chapter XIA).

**Problems**

| Issue | Where | Decision |
|---|---|---|
| **A two-column list was merged row by row.** Funded and non-funded exposures appear on the same line, so items cross columns: "Loans and advances bonds, warranties." joins a funded item with the tail of the non-funded "Performance bonds, bid bonds, warranties". | Para 47, p. 24 | **Fix now:** hand-write an override with two separate lists. Otherwise the assistant could classify a guarantee as a funded exposure. |
| In the UFCE incremental provisioning table, the "25 percentage point increase in risk weight" cell wraps above and below its row (> 75%, 80 bps). | Para 58, p. 29 | **Fix now:** override, because it sets out capital treatment. |
| There are many deleted sections (Ch. V-A, Paras 15–19, Ch. XI, Annexes II–III). | Various | Chunking (rule C5). |
| A broken date in a footnote: "October 0 1, 2026". | p. 26 | Chunking: the footnote moves to metadata (rule C4). Correct the date by hand. |

---

## Decisions for Step 3, in order

1. **Before chunking ("fix now"):**
   - ✅ Rerun with `extraction_mode="layout"` (`scripts/compare_layout.py`): output was identical to default mode for all five trouble spots, so default mode is kept.
   - ✅ Overrides written in `data/overrides/` for CF Para 111, CRM Para 47 and CRM Para 58, and **checked against the PDFs (CF pp. 55–56, CRM pp. 24 and 29): every value matches.** In CF Para 111 the PDF uses a merged cell for "Up to ₹30 lakh" across both LTV rows, which confirms the override's explicit row labels.
   - ✅ Fused-footnote and broken-date fixes listed in `data/overrides/text_fixes.csv` (15 fixes; each search string occurs exactly once).
   - ✅ The [verify in PDF] items were checked (CF Annex I, CIR state codes; see the tables above).
2. **Cleaning rules:** C1 (drop contents pages), C2 (strip page numbers and masthead), C5 (drop `*****` chunks and log the deleted paragraph numbers), and C6 (whitespace).
3. **Chunking rules:** C3 (split by paragraph, not by page), C4 (footnotes become `amended_on` metadata), and C7 (alphanumeric paragraph regex). Every chunk carries `source`, `para`, `page_start`, `updated_as_on` and `amended_on`.
4. **Exclusions for v0:** CIR Annex I (format specification) and CF Annex V (GML return template).

## Known limitations to state in the README

- Tables other than the three overrides are indexed as extracted. Answers drawn from them may need checking against the PDF.
- Paragraphs marked deleted are recognised as deleted, but the assistant has no content for what they used to say.
- The corpus is current only as of each document's "Updated as on" date. RBI amendments issued after that date are not included.
- The other 13 PDFs in the corpus have not been quality-checked. Repeat this review before adding them to the index.