# Design Decisions

Living document. Update as you make each choice. Each entry is your interview crib sheet.

---

## D1: Why pgvector and not Pinecone / Weaviate / FAISS?

**Decision:** Postgres + pgvector

**Reasoning to defend in interview:**
- Single datastore for both relational metadata and vectors — no separate vector DB to sync
- pgvector supports HNSW indexes giving sub-100ms ANN search at this scale (~500 docs, ~50k chunks)
- Citi specifically lists "PostgreSQL, Vector DBs" together in their JD
- Trade-off: at billions of vectors, dedicated vector DBs win. Not our scale.

**What I would do differently at 100x scale:** evaluate Qdrant or Vespa.

---

## D2: Chunk Size, Overlap, and Recursive Splitting

We chose an 800-character target chunk size — roughly 200 tokens for
text-embedding-3-small — because SEC filing pages are dense, and this
size is large enough to preserve financial context while still staying
small enough for reliable embedding and retrieval. The 150-character
overlap is about 18% of the chunk size, which gives the next chunk
enough carryover context without creating too much duplicate text in
the vector store. Instead of cutting every 800 characters blindly, the
chunker uses recursive separators so it can prefer paragraph breaks,
then line breaks, then sentence boundaries, then word boundaries before
falling back to raw character splitting. This matters because SEC
filings often contain long risk disclosures, legal language, tables
converted into text, and section-based narratives where meaning can be
lost if a sentence or paragraph is split in the wrong place. The result
is a chunking strategy that balances retrieval accuracy, storage
efficiency, and readability when answering questions from 10-K filings.

---

## D3: Hybrid retrieval scoring

**Decision:** [Fill in after Day 3 afternoon]

Common approaches:
- Reciprocal Rank Fusion (RRF) — score(d) = sum(1 / (60 + rank)) — simple, no tuning
- Weighted linear — alpha * normalize(dense) + (1-alpha) * normalize(bm25)
- Convex combination after min-max normalization

**Why this matters:** "Walk me through how you combined dense and sparse retrieval" — near-guaranteed question.

---

## D4: Why a cross-encoder reranker?

**Decision:** Two-stage retrieval — retrieve top-50 with hybrid, rerank top-10 with ms-marco-MiniLM-L-6-v2.

**Reasoning:**
- Bi-encoders (dense embeddings) lose fine-grained relevance because query and doc are encoded independently
- Cross-encoders see query+doc together, much more accurate but too slow on full corpus
- Two-stage gets 80% of cross-encoder benefit at 5% of the cost

**Numbers from my eval:**
- Recall@10 without reranker: [fill in]
- Recall@10 with reranker: [fill in]
- Latency added by reranker: [fill in]ms

---

## D5: Why structured outputs (Pydantic) instead of free-form generation?

**Decision:** All LLM responses pass through Pydantic schema: Answer { text, citations: list[Citation], confidence: float }.

**Reasoning:**
- Citations need to be programmatically clickable — can't trust free-form "[1][2]" text
- Confidence score lets us route low-confidence answers to "I don't know" instead of hallucinating
- Pydantic validation = automatic retry on schema failures

---

## D6: How did you measure hallucination [X]% to [Y]%?

**Decision:** [Fill in after Day 7 eval]

**Methodology:**
- Built a 120-question golden set [describe how]
- Each question has a ground-truth answer span from the source filing
- For each generated answer, compute RAGAS faithfulness score
- Threshold: faithfulness < 0.7 = hallucination
- Baseline (naive dense retrieval): [X]% hallucination
- Final (hybrid + rerank + structured output): [Y]%

**Honest caveat:** RAGAS uses an LLM judge with its own bias. Cross-validated 30 samples manually; LLM judge agreed with me on [N]/30.

---

## D7: Why streaming responses?

**Decision:** Stream tokens via SSE from FastAPI to React.

**Reasoning:** First-token latency matters more than total latency for chat UX.

---

## D8: What didn't work / what would you do next?

[Fill in honestly during the build — every failure mode you discovered]

---

## D9: Production concerns

- **Cost:** Embedding 500 filings = $[X]; ongoing query embeddings = $[Y]/1k queries
- **PII / safety:** SEC filings are public, no PII concern. Would change for internal docs.
- **Online eval:** would sample 1% of real queries, run through stronger judge model offline
- **Index updates:** rebuild takes ~[N] min; incremental updates supported via chunk.updated_at
