"""
Week 2, Step 3c - Chunk the clean text by paragraph number.

Reads  data/processed/clean/<document>.txt          (written by scripts/clean.py)
       data/processed/clean/<document>.report.json  (footnotes, deleted paragraphs)
Writes data/processed/chunks.jsonl                  -> one chunk per line, with citation metadata

Rules (from docs/ingestion_notes.md):
  C3  split by paragraph number, never by page
  C7  paragraph numbers can be alphanumeric (5A, 170A, 219ZE)
  Long paragraphs (e.g. Para 4 definitions) are split at sub-clause boundaries, never mid-clause.
  Each annex is chunked as its own section.
  One extra chunk per document lists the deleted paragraphs, so the assistant can say
  "this paragraph has been deleted" instead of "not found".

No API calls. Run from the repo root:  python scripts/chunk.py
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "processed" / "clean"
OUT_FILE = ROOT / "data" / "processed" / "chunks.jsonl"

# Hand-entered document metadata (from page 1 of each PDF)
DOCS = {
    "CB_Credit_Facilities_2025": {
        "short": "CF",
        "title": "RBI (Commercial Banks – Credit Facilities) Directions, 2025",
        "reference": "RBI/DOR/2025-26/154, DOR.CRE.REC.73/07-01-001/2025-26",
        "issued": "2025-11-28",
        "updated_as_on": "2026-10-01",
    },
    "CB_Credit_Information_Reporting_2025": {
        "short": "CIR",
        "title": "RBI (Commercial Banks – Credit Information Reporting) Directions, 2025",
        "reference": "RBI/DOR/2025-26/156, DOR.FIN.REC.No.75/20.16.056/2025-26",
        "issued": "2025-11-28",
        "updated_as_on": "2026-07-01",
    },
    "CB_Credit_Risk_Management_2025": {
        "short": "CRM",
        "title": "RBI (Commercial Banks – Credit Risk Management) Directions, 2025",
        "reference": "RBI/DOR/2025-26/157, DOR.CRE.REC.76/07-02-001/2025-26",
        "issued": "2025-11-28",
        "updated_as_on": "2026-10-01",
    },
}

MAX_CHARS = 3000          # about 750 tokens (rule of thumb: 1 token ~ 4 characters of English)

PAGE_RE = re.compile(r"^<<<PAGE (\d+)>>>$")
PARA_RE = re.compile(r"^(\d{1,3})([A-Z]{0,2})\.(?:\s+\S|\s*$)")   # "111. The bank...", "219ZE. A bank...", "4."
CHAPTER_RE = re.compile(r"^Chapter\s*-?\s*([IVXL]+(?:\s?A)?)(?:\s*[-–:]\s*|\s+)(.+?)\s*$")
ANNEX_RE = re.compile(r"^Annex\s*[-–]?\s*([IVX]+)\s*$")
SUBCLAUSE_RE = re.compile(r"^\((?:\d{1,2}|[ivxl]{1,6}[a-e]?|[a-z])\)\s")   # (1), (xiv), (iva), (a)


def para_key(num: int, suffix: str) -> tuple:
    return (num, len(suffix), suffix)                # 170 < 170A < 170Z < 170ZA < 171


def is_next_para(num: int, suffix: str, current: tuple | None, deleted: set) -> bool:
    """Accept a paragraph number only if it plausibly follows the current one.
    Guards against numbered lists inside paragraphs being read as new paragraphs."""
    if current is None:
        return num <= 3
    cur_num = current[0]
    if para_key(num, suffix) <= current:
        return False
    if num == cur_num:
        return True                                   # 5 -> 5A, 170A -> 170B
    skipped = range(cur_num + 1, num)
    return len(skipped) <= 2 or all(str(n) in deleted for n in skipped)


def is_chapter_heading(line: str) -> re.Match | None:
    m = CHAPTER_RE.match(line)
    if not m or line.endswith(".") or "of these Directions" in line:
        return None
    return m


def split_long(lines: list[str]) -> list[list[str]]:
    """Pack lines into parts of at most MAX_CHARS, breaking only before a sub-clause or blank line."""
    units, cur = [], []
    for line in lines:
        if cur and (SUBCLAUSE_RE.match(line) or not line.strip()):
            units.append(cur)
            cur = []
        cur.append(line)
    if cur:
        units.append(cur)

    parts, part, size = [], [], 0
    for unit in units:
        unit_size = sum(len(l) + 1 for l in unit)
        if part and size + unit_size > MAX_CHARS:
            parts.append(part)
            part, size = [], 0
        part.extend(unit)
        size += unit_size
    if part:
        parts.append(part)
    return parts


def chunk_document(stem: str, meta: dict) -> list[dict]:
    text = (CLEAN / f"{stem}.txt").read_text(encoding="utf-8")
    text = re.sub(r"[\ue000-\uf8ff]", "•", text)      # PDF symbol-font bullets (e.g. U+F0D8) -> plain bullet
    report = json.loads((CLEAN / f"{stem}.report.json").read_text(encoding="utf-8"))
    deleted = set(report["deleted_paras"])
    footnotes_by_page: dict[int, list[str]] = {}
    for fn in report["footnotes"]:
        footnotes_by_page.setdefault(fn["page"], []).append(fn["text"])

    sections = []        # each: {"label", "chapter", "pages", "lines"}
    page, chapter, current_para = None, "Preamble", None
    section = {"label": "Introduction", "chapter": chapter, "pages": [], "lines": []}

    def start(label: str) -> None:
        nonlocal section
        sections.append(section)
        section = {"label": label, "chapter": chapter, "pages": [page], "lines": []}

    for line in text.splitlines():
        pm = PAGE_RE.match(line)
        if pm:
            page = int(pm.group(1))
            if page not in section["pages"]:
                section["pages"].append(page)
            continue

        am = ANNEX_RE.match(line)
        if am:
            chapter = f"Annex {am.group(1)}"
            start(chapter)
            section["lines"].append(line)
            continue

        cm = is_chapter_heading(line)
        if cm and not chapter.startswith("Annex"):
            chapter = f"Chapter {cm.group(1).replace(' ', '')} - {cm.group(2)}"
            section["lines"].append(line)       # heading stays with the text until the next paragraph
            continue

        pa = PARA_RE.match(line)
        if pa and not chapter.startswith("Annex"):
            num, suffix = int(pa.group(1)), pa.group(2)
            if is_next_para(num, suffix, current_para, deleted):
                current_para = para_key(num, suffix)
                start(f"{num}{suffix}")
                section["chapter"] = chapter
        section["lines"].append(line)
    sections.append(section)

    chunks = []
    for sec in sections:
        body = sec["lines"]
        if len([l for l in body if l.strip()]) <= 1 and sec["label"].startswith("Annex"):
            continue                                   # deleted annex: heading only
        parts = split_long(body) if sum(len(l) + 1 for l in body) > MAX_CHARS else [body]
        pages = [p for p in sec["pages"] if p is not None]
        for i, part in enumerate(parts, start=1):
            label = sec["label"]
            cite_para = label if label.startswith(("Annex", "Intro")) else f"Para {label}"
            part_note = f" (part {i} of {len(parts)})" if len(parts) > 1 else ""
            content = "\n".join(part).strip()
            header = f"{meta['title']} | {cite_para}{part_note} | {sec['chapter']}"
            amendments = sorted({t for p in pages for t in footnotes_by_page.get(p, [])})
            chunks.append({
                "id": f"{meta['short']}-{label.replace(' ', '')}-{i}",
                "source": stem,
                "title": meta["title"],
                "reference": meta["reference"],
                "updated_as_on": meta["updated_as_on"],
                "chapter": sec["chapter"],
                "para": label,
                "part": i,
                "parts": len(parts),
                "page_start": pages[0] if pages else None,
                "page_end": pages[-1] if pages else None,
                "citation": f"[{meta['short']} {cite_para}]",
                "amendments_on_these_pages": amendments,
                "text": content,
                "embed_text": header + "\n\n" + content,
                "chars": len(content),
            })

    if deleted:
        listed = ", ".join(sorted(deleted, key=lambda s: (int(re.match(r"\d+", s).group()), s)))
        content = (f"The following paragraphs of the {meta['title']} have been deleted and contain "
                   f"no instructions: {listed}.")
        chunks.append({
            "id": f"{meta['short']}-deleted-1", "source": stem, "title": meta["title"],
            "reference": meta["reference"], "updated_as_on": meta["updated_as_on"],
            "chapter": "Deleted paragraphs", "para": "deleted", "part": 1, "parts": 1,
            "page_start": None, "page_end": None, "citation": f"[{meta['short']} deleted paragraphs]",
            "amendments_on_these_pages": [], "text": content,
            "embed_text": f"{meta['title']} | Deleted paragraphs\n\n{content}", "chars": len(content),
        })
    return chunks


def main() -> None:
    all_chunks = []
    print(f"{'Document':40} {'Chunks':>7} {'Paras':>6} {'Split paras':>12} {'Avg chars':>10} {'Max chars':>10}")
    print("-" * 90)
    for stem, meta in DOCS.items():
        if not (CLEAN / f"{stem}.txt").exists():
            print(f"{stem}: clean text not found - run scripts/clean.py first")
            continue
        chunks = chunk_document(stem, meta)
        all_chunks.extend(chunks)
        paras = {c["para"] for c in chunks}
        split = {c["para"] for c in chunks if c["parts"] > 1}
        sizes = [c["chars"] for c in chunks]
        print(f"{stem:40} {len(chunks):>7} {len(paras):>6} {len(split):>12} "
              f"{sum(sizes) // len(sizes):>10} {max(sizes):>10}")

    ids = [c["id"] for c in all_chunks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        print(f"\nWARNING: duplicate chunk ids (a paragraph number was detected twice): {sorted(dupes)}")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(all_chunks)} chunks to {OUT_FILE}")


if __name__ == "__main__":
    main()