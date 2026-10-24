"""
Week 2, Step 3b - Clean the extracted text (rules from docs/ingestion_notes.md).

Reads  data/processed/pages.jsonl   (written by scripts/ingest.py)
       data/overrides/*.md          (hand-cleaned tables, verified against the PDFs)
       data/overrides/text_fixes.csv
Writes data/processed/clean/<document>.txt  -> cleaned text, one file per document
       data/processed/clean/report.json     -> what was removed, fixed and logged

For v0 only the three credit directions are cleaned (see DOCS below).
No API calls. Run from the repo root:  python scripts/clean.py
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "processed" / "pages.jsonl"
OVERRIDES = ROOT / "data" / "overrides"
OUT = ROOT / "data" / "processed" / "clean"
OUT.mkdir(parents=True, exist_ok=True)

# Per-document settings. Page numbers are PDF page numbers.
DOCS = {
    "CB_Credit_Facilities_2025": {
        "contents_pages": range(1, 6),       # rule C1
        "excluded_pages": [149, 153],        # Annex I image template, Annex V GML return
    },
    "CB_Credit_Information_Reporting_2025": {
        "contents_pages": range(1, 3),
        "excluded_pages": list(range(33, 64)) + [72],   # Annex I reporting format, Annex IV template
    },
    "CB_Credit_Risk_Management_2025": {
        "contents_pages": range(1, 2),
        "excluded_pages": [],
    },
}

PAGE_MARK = "<<<PAGE {}>>>"            # kept in the clean text so Step 3c knows page numbers
PAGE_MARK_RE = re.compile(r"<<<PAGE \d+>>>")

# Rule C4: amendment footnotes ("1 Inserted with effect from ...") start the footnote block at a page bottom
FOOTNOTE_START = re.compile(r"^\s*(\d{1,2})\s*(Inserted|Substituted|Deleted|Renumbered)\b")
AMEND_MARKER = re.compile(r"\b\d{1,2}\[")                                  # "16[" before amended text
# Rule C5: deleted-paragraph placeholders
DELETED_PARA = re.compile(r"^\s*\[?(\d{1,3}[A-Z]{0,2})\.\s*\[?\*{5}\s*\]?\s*$")
STARS_ONLY = re.compile(r"^\s*(?:[A-Z]{1,2}(?:\.\d+)*\.?\s*)?\[?\*{5}\s*\]?\s*$")


def loose(text: str) -> re.Pattern:
    """Regex that matches `text` with any amount of whitespace between its words."""
    return re.compile(r"\s+".join(re.escape(w) for w in text.split()))


def clean_page(text: str, report: dict, stem: str, page: int, fixes: list) -> str:
    for fix in fixes:                                   # text fixes first, on the raw page
        text, n = loose(fix["find"]).subn(fix["replace"], text)
        fix["replaced"] += n
    text = AMEND_MARKER.sub("", text)                   # "16[" -> "" so deleted paras are recognised
    lines = text.splitlines()

    # Rule C2: drop the page number (last non-empty line, digits only) and the Hindi masthead
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip().isdigit():
        lines.pop()
    lines = [l for l in lines if "भारतीय" not in l and "�" not in l]

    # Rule C4: move amendment footnotes out of the text and into the report
    kept, footnotes, current = [], [], None
    for line in lines:
        m = FOOTNOTE_START.match(line)
        if m:
            current = {"page": page, "number": int(m.group(1)), "text": line.strip()}
            footnotes.append(current)
        elif current is not None and line.strip():
            current["text"] += " " + line.strip()       # continuation of a footnote
        elif current is None:
            kept.append(line)
    for fn in footnotes:
        fn["text"] = " ".join(fn["text"].split())
    report["footnotes"].extend(footnotes)

    # Rule C5: drop deleted placeholders, but log the paragraph numbers
    out = []
    for line in kept:
        d = DELETED_PARA.match(line)
        if d:
            report["deleted_paras"].append(d.group(1))
            continue
        if STARS_ONLY.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def normalise(text: str) -> str:
    """Rule C6: collapse runs of spaces, rejoin 'non-  banking' style hyphenation, trim blank lines."""
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"(\w)- (\w)", r"\1-\2", text)
    text = "\n".join(l.strip() for l in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def load_text_fixes(stem: str) -> list:
    with open(OVERRIDES / "text_fixes.csv", encoding="utf-8") as f:
        return [{"find": r["find"], "replace": r["replace"], "replaced": 0}
                for r in csv.DictReader(f) if r["source"] == stem]


def read_override(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    _, front, body = raw.split("---", 2)
    meta = {}
    for line in front.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta, body.strip()


def apply_overrides(text: str, stem: str, report: dict) -> str:
    for path in sorted(OVERRIDES.glob("*.md")):
        meta, body = read_override(path)
        if meta["source"] != stem:
            continue
        start = loose(meta["replace_from"]).search(text)
        end = loose(meta["replace_until"]).search(text, start.end()) if start else None
        if not (start and end):
            print(f"  WARNING: override {path.name} - markers not found, NOT applied")
            report["overrides"].append({"file": path.name, "applied": False})
            continue
        replaced = text[start.start():end.start()]
        page_marks = "\n".join(PAGE_MARK_RE.findall(replaced))   # keep page tracking intact
        text = text[:start.start()] + body + "\n\n" + (page_marks + "\n" if page_marks else "") + text[end.start():]
        report["overrides"].append({"file": path.name, "applied": True})
    return text


def main() -> None:
    pages_by_doc = {stem: [] for stem in DOCS}
    with open(PAGES, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            stem = Path(rec["source"]).stem
            if stem in pages_by_doc:
                pages_by_doc[stem].append(rec)

    summary = []
    for stem, cfg in DOCS.items():
        pages = sorted(pages_by_doc[stem], key=lambda r: r["page"])
        if not pages:
            print(f"{stem}: not found in pages.jsonl - skipped")
            continue
        report = {"source": stem, "dropped_pages": [], "footnotes": [], "deleted_paras": [],
                  "text_fixes": [], "overrides": []}
        fixes = load_text_fixes(stem)
        parts = []
        for rec in pages:
            p = rec["page"]
            if p in cfg["contents_pages"] or p in cfg["excluded_pages"]:
                report["dropped_pages"].append(p)
                continue
            parts.append(PAGE_MARK.format(p) + "\n" + clean_page(rec["text"], report, stem, p, fixes))

        text = normalise("\n".join(parts))
        for fix in fixes:
            if fix["replaced"] != 1:
                print(f"  WARNING: {stem}: text fix {fix['find']!r} matched {fix['replaced']} times (expected 1)")
        report["text_fixes"] = fixes
        text = apply_overrides(text, stem, report)

        (OUT / f"{stem}.txt").write_text(text, encoding="utf-8")
        (OUT / f"{stem}.report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                 encoding="utf-8")
        summary.append((stem, len(pages), len(report["dropped_pages"]), len(report["footnotes"]),
                        len(report["deleted_paras"]),
                        sum(1 for x in report["text_fixes"] if x["replaced"] == 1), len(report["text_fixes"]),
                        sum(1 for x in report["overrides"] if x["applied"]), len(report["overrides"])))

    print(f"\n{'Document':40} {'Pages':>5} {'Dropped':>8} {'Footnotes':>10} {'Deleted':>8} {'Fixes':>7} {'Overrides':>10}")
    print("-" * 94)
    for s, n, d, fn, dl, fx, fxt, ov, ovt in summary:
        print(f"{s:40} {n:>5} {d:>8} {fn:>10} {dl:>8} {fx:>3}/{fxt:<3} {ov:>5}/{ovt:<4}")
    print(f"\nClean text and reports written to {OUT}")


if __name__ == "__main__":
    main()