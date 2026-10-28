"""
Week 2, Step 5 - Retrieve and generate.

Takes a question, retrieves the most relevant RBI paragraphs from the Chroma store,
and asks Claude to answer ONLY from them, with citations (system prompt: prompts/system_prompt_v1.md).
Week 3: retrieval can be "semantic" (Week 2 baseline) or "hybrid" (adds paragraph lookup and keyword
search, see scripts/keyword_search.py). Set RETRIEVAL_MODE below.

Run from the repo root:
  python scripts/answer.py "What is the maximum LTV for a gold loan of 4 lakh?"
  python scripts/answer.py                      (interactive: type questions, blank line to quit)
  python scripts/answer.py --show-context "..."  (also print exactly what Claude was given)

Needs: ANTHROPIC_API_KEY in the .env file at the repo root (set up in Week 1).
If your key is not scoped to a workspace, also add ANTHROPIC_WORKSPACE_ID=wrkspc_... to .env.
Each question is one API call; with the default model it costs well under one US cent.
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from embed_store import search          # same embedding model and settings as Step 4
from keyword_search import keyword_search, lookup   # Week 3: keyword search + paragraph lookup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MODEL = "claude-sonnet-5-5"     # current Sonnet model ID; try "claude-haiku-5-5" later for the cost comparison
MAX_TOKENS = 2000               # ceiling on output INCLUDING Claude's thinking; the prompt keeps answers < 150 words
EFFORT = "medium"               # how much Claude thinks first: "low", "medium" or "high" (model default is higher)
SYSTEM_PROMPT_FILE = ROOT / "prompts" / "system_prompt_v1.md"
K_CHUNKS = 10                   # chunks fetched from Chroma
K_PARAS = 5                     # distinct paragraphs passed to Claude (parts of one paragraph count once)
RETRIEVAL_MODE = "hybrid"       # "semantic" = Week 2 baseline (embeddings only)
                                # "hybrid"   = Week 3: + paragraph lookup + keyword (BM25) search, merged by rank
K_KEYWORD = 10                  # chunks fetched by keyword search in hybrid mode
RRF_K = 60                      # standard constant for merging two ranked lists (reciprocal rank fusion)

# Short names match the citation style in the system prompt: [Credit Facilities, Para 44]
SHORT_NAMES = {
    "CB_Credit_Facilities_2025": "Credit Facilities",
    "CB_Credit_Information_Reporting_2025": "Credit Information Reporting",
    "CB_Credit_Risk_Management_2025": "Credit Risk Management",
}
DOC_NOTES = {   # from docs/ingestion_notes.md
    "CB_Credit_Information_Reporting_2025": "In this document, 'CI' means credit institution, i.e. the bank.",
}


def load_system_prompt() -> str:
    """The prompt file has notes around it; the prompt itself is the first ``` code block."""
    if not SYSTEM_PROMPT_FILE.exists():
        raise SystemExit(f"System prompt not found: {SYSTEM_PROMPT_FILE}")
    raw = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
    block = re.search(r"```[a-z]*\n(.*?)```", raw, re.S)
    return (block.group(1) if block else raw).strip()


def candidate_chunks(question: str) -> list[dict]:
    """Chunks in best-first order.

    semantic: embedding search only (the Week 2 baseline).
    hybrid:   1. paragraphs named in the question ("Para 70 of Credit Risk Management") come first;
              2. then embedding results and keyword results, merged with reciprocal rank fusion:
                 each chunk scores 1/(60 + rank) in each list it appears in, so a chunk that ranks
                 well in both lists rises to the top, and a chunk only one method found still gets in.
    The 'similarity' shown in the logs is the embedding score, or 'keyword' / 'lookup' for chunks
    that only those methods found.
    """
    semantic = search(question, k=K_CHUNKS)
    if RETRIEVAL_MODE == "semantic":
        return semantic

    named = [dict(c, similarity="lookup") for c in lookup(question)]
    scores: dict[str, float] = {}
    chunk_by_id: dict[str, dict] = {}
    for rank, hit in enumerate(semantic, start=1):
        scores[hit["id"]] = scores.get(hit["id"], 0) + 1 / (RRF_K + rank)
        chunk_by_id[hit["id"]] = hit
    for rank, hit in enumerate(keyword_search(question, k=K_KEYWORD), start=1):
        scores[hit["id"]] = scores.get(hit["id"], 0) + 1 / (RRF_K + rank)
        chunk_by_id.setdefault(hit["id"], dict(hit, similarity="keyword"))
    fused = sorted(chunk_by_id.values(), key=lambda h: -scores[h["id"]])
    named_ids = {c["id"] for c in named}
    return named + [h for h in fused if h["id"] not in named_ids]


def retrieve(question: str) -> list[dict]:
    """Top chunks, grouped so that parts of the same paragraph form one excerpt (fix from the smoke test)."""
    groups: dict[tuple, dict] = {}
    for hit in candidate_chunks(question):
        key = (hit["source"], hit["para"])
        if key not in groups:
            if len(groups) == K_PARAS:
                continue
            groups[key] = {**hit, "best_similarity": hit["similarity"], "parts_text": {}}
        groups[key]["parts_text"][hit["part"]] = hit["text"]
    excerpts = []
    for g in groups.values():                     # dict keeps best-first order
        g["text"] = "\n...\n".join(g["parts_text"][p] for p in sorted(g["parts_text"]))
        excerpts.append(g)
    return excerpts


def build_documents(excerpts: list[dict]) -> str:
    """The <documents> block, in the same shape as prompts/test_context.md."""
    by_doc: dict[str, list[dict]] = {}
    for ex in excerpts:
        by_doc.setdefault(ex["source"], []).append(ex)
    out = ["<documents>"]
    for source, items in by_doc.items():
        first = items[0]
        note = f' note="{DOC_NOTES[source]}"' if source in DOC_NOTES else ""
        out.append(f'<doc name="{SHORT_NAMES.get(source, source)}" title="{first["title"]}" '
                   f'ref="{first["reference"]}" updated="{first["updated_as_on"]}"{note}>')
        for ex in items:
            label = ex["para"] if ex["para"].startswith(("Annex", "Intro", "deleted")) else f'Para {ex["para"]}'
            pages = f'{ex["page_start"]}-{ex["page_end"]}' if ex["page_start"] != -1 else "n/a"
            out.append(f'<excerpt para="{label}" chapter="{ex["chapter"]}" pages="{pages}">\n{ex["text"]}\n</excerpt>')
        out.append("</doc>")
    out.append("</documents>")
    return "\n".join(out)


def thinking_tokens(usage) -> int | None:
    """How many of the output tokens were Claude's internal reasoning (None if the API didn't report it)."""
    details = getattr(usage, "output_tokens_details", None)
    if details is None and getattr(usage, "model_extra", None):
        details = usage.model_extra.get("output_tokens_details")
    if isinstance(details, dict):
        return details.get("thinking_tokens")
    return getattr(details, "thinking_tokens", None)


def make_client() -> anthropic.Anthropic:
    """Some API keys are not tied to one workspace; those must name the workspace on every request
    with the 'anthropic-workspace-id' header. Set ANTHROPIC_WORKSPACE_ID=wrkspc_... in .env for that."""
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
    headers = {"anthropic-workspace-id": workspace} if workspace else None
    return anthropic.Anthropic(default_headers=headers)


def answer(question: str, client: anthropic.Anthropic | None = None) -> dict:
    client = client or make_client()
    t0 = time.time()
    excerpts = retrieve(question)
    t_retrieve = time.time() - t0

    documents = build_documents(excerpts)
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=load_system_prompt(),
        messages=[{"role": "user", "content": f"{documents}\n\nQuestion: {question}"}],
        extra_body={"output_config": {"effort": EFFORT}},
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return {
        "question": question,
        "answer": text,
        "retrieved": [f'{SHORT_NAMES.get(e["source"], e["source"])}, '
                      f'{e["para"] if e["para"].startswith(("Annex", "Intro", "deleted")) else "Para " + e["para"]}'
                      f' ({e["best_similarity"]})' for e in excerpts],
        "documents": documents,
        "model": MODEL,
        "retrieval_mode": RETRIEVAL_MODE,
        "retrieval_seconds": round(t_retrieve, 2),
        "total_seconds": round(time.time() - t0, 2),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "thinking_tokens": thinking_tokens(response.usage),
        "stop_reason": response.stop_reason,
    }


def show(result: dict, show_context: bool) -> None:
    if show_context:
        print("\n----- What Claude was given -----\n" + result["documents"])
    print("\n----- Answer -----\n" + result["answer"])
    print("\n----- Retrieved (paragraph, similarity) -----")
    for r in result["retrieved"]:
        print("  " + r)
    print(f"\n{result['model']} (effort {EFFORT}, {RETRIEVAL_MODE} retrieval) | {result['total_seconds']}s total ({result['retrieval_seconds']}s retrieval) | "
          f"{result['input_tokens']} in / {result['output_tokens']} out tokens"
          + (f" ({result['thinking_tokens']} of them thinking)" if result["thinking_tokens"] is not None else ""))
    if result["stop_reason"] == "max_tokens":
        print("WARNING: answer was cut off at MAX_TOKENS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", help="question in quotes; omit for interactive mode")
    parser.add_argument("--show-context", action="store_true", help="print the excerpts sent to Claude")
    args = parser.parse_args()

    client = make_client()                  # reads ANTHROPIC_API_KEY (and ANTHROPIC_WORKSPACE_ID) from .env
    if args.question:
        show(answer(args.question, client), args.show_context)
        return
    print("Ask a question about the RBI credit directions (blank line to quit).")
    while True:
        q = input("\nQuestion: ").strip()
        if not q:
            break
        show(answer(q, client), args.show_context)


if __name__ == "__main__":
    main()