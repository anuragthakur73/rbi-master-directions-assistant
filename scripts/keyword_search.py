"""
Week 3 - Keyword search and direct paragraph lookup (used by answer.py when RETRIEVAL_MODE = "hybrid").

Why: the baseline used meaning-based (embedding) search only. On the 40-question test set it missed
4 of 32 expected paragraphs, and it cannot find a paragraph by its number ("What does Para 70 say?").
Keyword search (BM25) catches questions that share exact words with the rule, such as
"fixed deposit ... other bank" -> Para 215 "FDRs or other term deposits of other banks".

Both work on data/processed/chunks.jsonl, the same chunks that are in the Chroma store.
No extra packages are needed: BM25 is about 30 lines of Python.
"""
import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"

# Words a document name can be written with -> source id in chunks.jsonl
DOC_NAMES = {
    "CB_Credit_Facilities_2025": ["credit facilities", "cf"],
    "CB_Credit_Information_Reporting_2025": ["credit information reporting", "credit information", "cir"],
    "CB_Credit_Risk_Management_2025": ["credit risk management", "crm"],
}

STOPWORDS = set("""a an the of to in on for by with and or is are was were be been can could shall should may
might must will would do does did what which who whom whose when where why how this that these those it its
as at from any all such than then there their them they we our you your i me my he his she her not no if
into under up out about per each only also so very much many more most own same just""".split())
# Common words like "bank" or "loan" are not removed: BM25 already gives them almost no weight.


def stem(word: str) -> str:
    """Very light suffix stripping so 'financing' matches 'finance' and 'deposits' matches 'deposit'."""
    for suffix in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower().replace("₹", " "))
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


@lru_cache(maxsize=1)
def load_chunks() -> list[dict]:
    with CHUNKS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


@lru_cache(maxsize=1)
def _index():
    """Term counts per chunk (text plus chapter title) and document frequencies, built once."""
    chunks = load_chunks()
    docs = [Counter(tokenize(c["chapter"] + " " + c["text"])) for c in chunks]
    df = Counter(term for d in docs for term in d)
    avg_len = sum(sum(d.values()) for d in docs) / len(docs)
    return chunks, docs, df, avg_len


def keyword_search(question: str, k: int = 20, k1: float = 1.2, b: float = 0.75) -> list[dict]:
    """BM25: score each chunk by how many rare question words it contains, best first."""
    chunks, docs, df, avg_len = _index()
    n = len(chunks)
    terms = set(tokenize(question))
    scored = []
    for chunk, tf in zip(chunks, docs):
        length = sum(tf.values())
        score = 0.0
        for t in terms:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * length / avg_len))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda x: -x[0])
    return [dict(c, keyword_score=round(s, 2)) for s, c in scored[:k]]


NUM = r"\d{1,3}[A-Za-z]{0,2}"
# "Para 70", "para 170i", "paragraphs 44 and 45", "Paras 111, 112 & 113"
PARA_PATTERN = re.compile(rf"\bpara(?:graph)?s?\.?\s*({NUM}(?:\s*(?:,|and|&)\s*{NUM})*)\b", re.IGNORECASE)


def named_paragraphs(question: str) -> list[tuple[str, str]]:
    """Paragraphs the question names, e.g. 'Para 70 of the Credit Risk Management Directions'.
    If no document is named, every document that has that paragraph number is returned."""
    numbers = [n.upper() for m in PARA_PATTERN.findall(question) for n in re.findall(NUM, m)]
    if not numbers:
        return []
    q = " " + re.sub(r"[^a-z]+", " ", question.lower()) + " "
    named_docs = [src for src, names in DOC_NAMES.items() if any(f" {n} " in q for n in names)]
    existing = {(c["source"], c["para"]) for c in load_chunks()}
    out = []
    for num in numbers:
        for src in (named_docs or DOC_NAMES):
            if (src, num) in existing and (src, num) not in out:
                out.append((src, num))
    return out


def lookup(question: str) -> list[dict]:
    """All chunks (every part) of the paragraphs named in the question, in paragraph order."""
    wanted = named_paragraphs(question)
    chunks = load_chunks()
    return [c for key in wanted for c in chunks if (c["source"], c["para"]) == key]
