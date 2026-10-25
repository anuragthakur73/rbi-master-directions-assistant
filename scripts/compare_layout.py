"""
Week 2, Step 3a - Does pypdf's layout mode fix the problem tables?

Re-extracts the three credit directions in layout mode, then prints the five
trouble spots from docs/ingestion_notes.md twice: once from the default
extraction (data/processed/) and once from layout mode, so you can compare.

Full layout-mode text is saved to data/processed/layout/ for checking by eye.
No API calls. Run from the repo root:  python scripts/compare_layout.py
"""
import sys
from pathlib import Path

import pypdf
from pypdf import PdfReader

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # so ₹ and ≤ print on Windows

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "data" / "processed"
LAYOUT_DIR = DEFAULT_DIR / "layout"
LAYOUT_DIR.mkdir(parents=True, exist_ok=True)

CF = "CB_Credit_Facilities_2025"
CIR = "CB_Credit_Information_Reporting_2025"
CRM = "CB_Credit_Risk_Management_2025"

# (document, label, text to find, how many lines to show from the match)
CHECKS = [
    (CF,  "CF Para 111 - housing LTV table", "Category of Loan", 12),
    (CRM, "CRM Para 47 - funded / non-funded exposures", "Funded Exposures", 13),
    (CRM, "CRM Para 58 - UFCE Table 1", "Potential Loss / EBID", 16),
    (CIR, "CIR Para 10(2) - fused footnote '1A CI'", "CI shall keep the credit information", 1),
    (CIR, "CIR Annex III - Rs 30,000 heading", "Information to be collected from individual SHG members where the total", 3),
]


def squash(s: str) -> str:
    """Collapse all runs of whitespace to one space, for matching only."""
    return " ".join(s.split())


def extract_layout(stem: str) -> str:
    matches = list((ROOT / "data").rglob(f"{stem}.pdf"))
    if not matches:
        raise SystemExit(f"Could not find {stem}.pdf anywhere under data/")
    reader = PdfReader(matches[0])
    pages = []
    for n, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            raise SystemExit(
                f"Your pypdf ({pypdf.__version__}) has no layout mode. "
                "Run: pip install -U pypdf   then run this script again."
            )
        pages.append(f"\n\n===== PAGE {n} =====\n{text}")
    full = "".join(pages)
    (LAYOUT_DIR / f"{stem}.txt").write_text(full, encoding="utf-8")
    return full


def show(text: str, needle: str, n_lines: int) -> None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if squash(needle) in squash(line):
            for out in lines[i:i + n_lines]:
                print("   |" + out.rstrip()[:150])
            return
    print("   (text not found - search for it by eye in the .txt file)")


print(f"pypdf version {pypdf.__version__}\n")

layout_text = {}
for stem in (CF, CIR, CRM):
    print(f"Extracting {stem} in layout mode...")
    layout_text[stem] = extract_layout(stem)

for stem, label, needle, n in CHECKS:
    default_file = DEFAULT_DIR / f"{stem}.txt"
    print("\n" + "=" * 100)
    print(label)
    print("=" * 100)
    print("\n-- DEFAULT mode (data/processed) --")
    if default_file.exists():
        show(default_file.read_text(encoding="utf-8"), needle, n)
    else:
        print("   (default .txt not found - run scripts/ingest.py first)")
    print("\n-- LAYOUT mode (data/processed/layout) --")
    show(layout_text[stem], needle, n)

print(f"\nFull layout-mode text saved in {LAYOUT_DIR}")
