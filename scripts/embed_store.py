"""
Week 2, Step 4 - Embed the chunks and store them in a local Chroma vector database.

Reads  data/processed/chunks.jsonl   (written by scripts/chunk.py)
Writes data/vectorstore/             (Chroma database files - git-ignored, rebuildable)

Embedding model: BAAI/bge-small-en-v1.5, run locally through fastembed.
  - Free, no API key, no data leaves your laptop.
  - Downloaded once (~130 MB) on the first run, then cached.
  - 384-dimensional vectors, cosine similarity.

After building, it runs a smoke test: 6 questions whose correct paragraph we already know.
Run from the repo root:  python scripts/embed_store.py

Step 5 imports search() from this file, so the same model and settings are used for retrieval.
"""
import json
import sys
import time
from pathlib import Path

import chromadb
from fastembed import TextEmbedding

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
DB_DIR = ROOT / "data" / "vectorstore"
COLLECTION = "rbi_credit_v0"

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
# BGE models retrieve better when the QUESTION (not the stored text) carries this instruction.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(EMBED_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in get_model().embed(texts, batch_size=32)]


def embed_query(question: str) -> list[float]:
    return next(iter(get_model().embed([QUERY_PREFIX + question]))).tolist()


def get_collection(client=None):
    client = client or chromadb.PersistentClient(path=str(DB_DIR))
    return client.get_collection(COLLECTION)


def search(question: str, k: int = 5, collection=None) -> list[dict]:
    """Return the k chunks closest to the question, best first."""
    collection = collection or get_collection()
    res = collection.query(query_embeddings=[embed_query(question)], n_results=k,
                           include=["documents", "metadatas", "distances"])
    hits = []
    for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({"id": cid, "text": doc, "similarity": round(1 - dist, 3), **meta})
    return hits


def to_metadata(chunk: dict) -> dict:
    """Chroma metadata values must be str / int / float / bool - no None, no lists."""
    return {
        "source": chunk["source"],
        "title": chunk["title"],
        "reference": chunk["reference"],
        "updated_as_on": chunk["updated_as_on"],
        "chapter": chunk["chapter"],
        "para": chunk["para"],
        "part": chunk["part"],
        "parts": chunk["parts"],
        "page_start": chunk["page_start"] if chunk["page_start"] is not None else -1,
        "page_end": chunk["page_end"] if chunk["page_end"] is not None else -1,
        "citation": chunk["citation"],
        "amendments_on_these_pages": " | ".join(chunk["amendments_on_these_pages"]),
    }


def build() -> chromadb.Collection:
    if not CHUNKS.exists():
        raise SystemExit("chunks.jsonl not found - run scripts/clean.py and scripts/chunk.py first")
    chunks = [json.loads(line) for line in CHUNKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(chunks)} chunks")

    print(f"Loading embedding model {EMBED_MODEL} (downloads ~130 MB on the first run)...")
    t0 = time.time()
    vectors = embed_texts([c["embed_text"] for c in chunks])   # header + text, see chunk.py
    print(f"Embedded {len(vectors)} chunks in {time.time() - t0:.0f}s (dimension {len(vectors[0])})")

    client = chromadb.PersistentClient(path=str(DB_DIR))
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)                   # rebuild from scratch every run
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine",
                                                                "embed_model": EMBED_MODEL})
    for i in range(0, len(chunks), 500):                       # add in batches
        batch = chunks[i:i + 500]
        collection.add(ids=[c["id"] for c in batch],
                       embeddings=vectors[i:i + 500],
                       documents=[c["text"] for c in batch],
                       metadatas=[to_metadata(c) for c in batch])
    print(f"Stored {collection.count()} chunks in {DB_DIR} (collection '{COLLECTION}')")
    return collection


# Questions whose correct paragraph is known (from prompts/test_context.md and the ingestion notes)
SMOKE_TESTS = [
    ("What is the maximum LTV for a gold loan of 4 lakh?", "CF Para 44"),
    ("What LTV and risk weight apply to a home loan of 80 lakh?", "CF Para 111"),
    ("How much compensation does a customer get if their credit report correction is delayed?", "CIR Para 36"),
    ("How many valuation reports are needed for a property worth 60 crore?", "CRM Para 70"),
    ("Is a bank guarantee a funded or non-funded exposure for country risk?", "CRM Para 47"),
    ("What does paragraph 52 of the Credit Facilities directions say?", "CF deleted paragraphs"),
]


def smoke_test(collection) -> None:
    print("\nSmoke test - is the right paragraph in the top 5?\n")
    passed = 0
    for question, expected in SMOKE_TESTS:
        hits = search(question, k=5, collection=collection)
        cites = [h["citation"].strip("[]") for h in hits]
        rank = next((i + 1 for i, c in enumerate(cites) if c == expected), None)
        passed += rank is not None
        status = f"PASS (rank {rank})" if rank else "MISS"
        print(f"{status:14} {question}\n{'':14} expected {expected}; got {', '.join(cites)}\n")
    print(f"{passed}/{len(SMOKE_TESTS)} found in the top 5")


if __name__ == "__main__":
    smoke_test(build())