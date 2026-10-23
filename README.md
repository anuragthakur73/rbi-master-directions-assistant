# rbi-master-directions-assistant
RBI Master Directions Assistant
A question-answering assistant over public RBI Master Directions, with answers cited to the source paragraph.

Status
Work in progress — Week 1: setup.

Problem
Bank staff spend time searching long regulatory PDFs for specific rules.

Scope
Corpus: public RBI Master Directions only (rbi.org.in)
No internal bank documents or customer data
Tech
Python, <LLM provider> API

Disclaimer
Not legal or regulatory advice. Always verify against the official RBI document.
Scope and data policy
Corpus: public RBI Master Directions downloaded from rbi.org.in, listed in data/manifest.csv.
Not used, ever: internal bank documents, intranet content, internal circulars, process notes, or any customer data — including anonymised data.
Source PDFs are not committed. To rebuild the corpus, download each source_url in the manifest into data/raw/.
