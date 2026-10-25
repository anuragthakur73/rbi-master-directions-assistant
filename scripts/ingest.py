"""
Week 2, Step 2 - Ingest documents.

Extracts text from every RBI PDF inside the repo's data/ folder, one record per page,
and writes:
  data/processed/pages.jsonl   -> machine-readable (used for chunking in Step 3)
  data/processed/<name>.txt    -> human-readable copy of each PDF, for checking by eye

No API calls, so this costs nothing to run.
Run from the repo root:  python scripts/ingest.py
"""
import json
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent   # repo root (this file lives in scripts/)
PDF_DIR = ROOT / "data"
OUT_DIR = ROOT / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_CHARS = 50   # pages with less text than this are flagged (possibly scanned / image-only)

pdfs = sorted(PDF_DIR.rglob("*.pdf"))
if not pdfs:
    raise SystemExit(f"No PDFs found under {PDF_DIR}")

records, report = [], []

for pdf in pdfs:
    try:
        reader = PdfReader(pdf)
    except Exception as e:  # corrupt or password-protected file
        report.append((pdf.name, 0, 0, f"ERROR: {e}"))
        continue

    readable, near_empty = [], 0
    for page_no, page in enumerate(reader.pages, start=1):
        text = page.extract_text(extraction_mode="layout") or ""
        if len(text.strip()) < MIN_CHARS:
            near_empty += 1
        records.append({"source": pdf.name, "page": page_no, "text": text})
        readable.append(f"\n\n===== PAGE {page_no} =====\n{text}")

    (OUT_DIR / f"{pdf.stem}.txt").write_text("".join(readable), encoding="utf-8")
    report.append((pdf.name, len(reader.pages), near_empty, "ok"))

with open(OUT_DIR / "pages.jsonl", "w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"{'File':55} {'Pages':>6} {'Near-empty':>11}  Status")
print("-" * 82)
for name, n_pages, n_empty, status in report:
    print(f"{name[:55]:55} {n_pages:>6} {n_empty:>11}  {status}")
print(f"\nWrote {len(records)} pages from {len(pdfs)} PDFs to {OUT_DIR / 'pages.jsonl'}")