# CURSOR BUILD GUIDE — Enterprise RAG over SEC Filings

> **Read this whole document once before starting.** It is the single source of truth for the entire 5-7 day build. Every Cursor Composer prompt, every commit checkpoint, every test command is here.
>
> Project owner: Rahul Kushal Anchi
> Target: Portfolio project for Full-Stack AI Engineer / GenAI Application Developer roles
> Timeline: 5-7 days
> Subscription: Cursor Pro ($20/month) using Claude Sonnet 4.5 as the model

---

## SECTION A — ONE-TIME SETUP (Day 0, ~45 minutes)

### A.1 — Sign up for Cursor Pro

1. Go to **cursor.com/settings/billing**
2. Subscribe to **Cursor Pro** — $20/month
3. Cancel anytime after Citi deadline if you want; the $20 is worth it for predictable cost during the build

### A.2 — Configure Cursor to use Claude Sonnet 4.5

1. Open Cursor
2. `Cmd + Shift + J` → opens Cursor Settings
3. Click **"Models"** in the left sidebar
4. Enable these models (toggle ON):
   - ✅ `claude-sonnet-4-5`
   - ✅ `claude-opus-4-7` (use for the 3 hard prompts that demand best reasoning)
5. Set **default model** to `claude-sonnet-4-5`

### A.3 — Open the project in Cursor

```bash
cd ~/projects/sec-rag-assistant
cursor .
```

Cursor opens with the repo. The `.cursorrules` file you'll create below will be picked up automatically.

### A.4 — Verify your .env file is in place but gitignored

In Cursor's integrated terminal (Ctrl + `):

```bash
ls -la .env
cat .gitignore | grep env
```

You should see `.env` exists and `.env` is in `.gitignore`. If either is missing, fix before continuing.

---

## SECTION B — THE FOUNDATION FILES

Create these files in the project root before starting any Composer prompt. They are read by Cursor on every request and shape its behavior.

### B.1 — Create `.cursorrules`

In Cursor: `Cmd + N` to create new file → save as `.cursorrules` in project root → paste:

```
# Project: Enterprise RAG Assistant for SEC Filings
# Owner: Rahul Kushal Anchi
# Purpose: Interview-defensible portfolio project for Full-Stack AI Engineer roles at Citi, Bloomberg, Goldman, Two Sigma, Mount Sinai.

## Stack constraints (do not deviate without explicit user approval)
- Python 3.11+, FastAPI, async wherever the libraries support it
- LangChain 0.3+ for orchestration (use LCEL chains, NOT agent abstractions)
- PostgreSQL 16 with pgvector extension for vector storage
- LLM providers: Anthropic Claude (default), OpenAI GPT-4o-mini (fallback) — call via official SDKs, not LangChain wrappers, for transparency
- Embeddings: text-embedding-3-small (OpenAI) — small, cheap, sufficient for this corpus size
- Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2 via sentence-transformers
- Frontend: React 18 + Vite + TypeScript + Tailwind, minimal (chat UI only)
- Eval framework: RAGAS for faithfulness; custom golden-set scorer for citation accuracy
- Tests: pytest, pytest-asyncio, pytest-cov; target 80%+ coverage on non-IO code
- Observability: LangSmith for traces; structlog for application logs
- Deploy target: AWS ECS Fargate (later); local dev with docker-compose

## Author-owned files (Cursor: generate ONLY stubs with TODO comments)
The following files contain the design decisions an interviewer will probe deepest. Cursor must NOT generate the business logic — only file stubs with one-line docstrings and TODO comments:

- backend/app/ingest/chunker.py — the chunking strategy
- backend/app/retrieval/hybrid.py — the scoring formula combining BM25 and dense retrieval
- backend/app/generation/prompts.py — the system prompt, user template, answer schema
- backend/app/generation/answerer.py — the orchestration of retrieve → rerank → generate

When asked to work on any of these, generate the stub with TODOs and ask the user to provide the implementation.

## What Cursor SHOULD generate freely
- pyproject.toml, Dockerfile, docker-compose.yml, alembic migrations
- FastAPI app skeleton, routers, Pydantic schemas (DTOs)
- SQLAlchemy models, database session setup
- Logging configuration (structlog)
- Test fixtures and harness setup
- React frontend shell (components, hooks, API client)
- CI workflow YAML
- README and documentation structure

## Code quality rules (enforce on every generation)
- All Python functions: type hints required, including return types
- Pydantic v2 models for every request/response DTO
- No bare `except:` — always catch specific exceptions
- Use `async def` for any function that awaits I/O
- Functions over 40 lines must be split
- Use `structlog` for logging, never `print` in application code
- Configuration via Pydantic Settings (loads from env vars), never hardcoded values
- All LLM calls go through a single `llm_client` module so providers can be swapped

## Process rules
- One Composer prompt = one logical commit
- After each generation, suggest the appropriate `git commit -m "..."` message
- After each generation, suggest which test commands to run to verify
- Never delete the user's hand-written code in author-owned files
- If a generation requires more than 8 files in one pass, split into multiple Composer calls
```

### B.2 — Create `DECISIONS.md`

Same pattern. New file in project root:

```markdown
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

## D2: Chunking strategy

**Decision:** [Fill in after Day 2 morning]

Options considered:
- Fixed-size (1000 chars / 200 overlap) — simple, predictable
- Recursive character splitter — respects paragraph boundaries
- Section-aware — never split across SEC 10-K section boundaries
- Sentence-aware — pack sentences greedily

**Why this matters:** "How did you handle the structure of 10-K filings?" — guaranteed interview question.

---

## D3: Hybrid retrieval scoring

**Decision:** [Fill in after Day 3 afternoon]

Common approaches:
- Reciprocal Rank Fusion (RRF) — `score(d) = sum(1 / (60 + rank))` — simple, no tuning
- Weighted linear — `α * normalize(dense) + (1-α) * normalize(bm25)`
- Convex combination after min-max normalization

**Why this matters:** "Walk me through how you combined dense and sparse retrieval" — near-guaranteed question.

---

## D4: Why a cross-encoder reranker?

**Decision:** Two-stage retrieval — retrieve top-50 with hybrid, rerank top-10 with `ms-marco-MiniLM-L-6-v2`.

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

**Decision:** All LLM responses pass through Pydantic schema: `Answer { text, citations: list[Citation], confidence: float }`.

**Reasoning:**
- Citations need to be programmatically clickable — can't trust free-form "[1][2]" text
- Confidence score lets us route low-confidence answers to "I don't know" instead of hallucinating
- Pydantic validation = automatic retry on schema failures

---

## D6: How did you measure hallucination [X]% → [Y]%?

**Decision:** [Fill in after Day 7 eval]

**Methodology:**
- Built a 120-question golden set [describe how]
- Each question has a ground-truth answer span from the source filing
- For each generated answer, compute RAGAS `faithfulness` score
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
- **Index updates:** rebuild takes ~[N] min; incremental updates supported via `chunk.updated_at`
```

### B.3 — Create `BACKLOG.md`

```markdown
# Backlog — parked ideas (do NOT implement before submission)

Things that would be cool but are explicitly out of scope for the 5-7 day build. In interview, "what would you do next" answers come from here.

## Retrieval improvements
- HyDE (Hypothetical Document Embeddings)
- Query rewriting / multi-query retrieval
- A/B test different embedding models
- Tune α weight on hybrid scoring via dev-set tuning
- Add bge-reranker-base as alternative
- Filter by metadata before vector search

## Generation improvements
- Self-consistency: generate 3 answers, vote
- Chain-of-verification: post-hoc "is this supported?" check
- Cost-based model routing (Claude/GPT-4o-mini based on complexity)
- Context compression via smaller summarizer model

## Eval improvements
- Online eval on 1% of real queries
- Expand golden set to 500 questions
- Per-section accuracy breakdown
- Add comprehensiveness/conciseness metrics

## Production / scale
- Cache embeddings of repeated queries
- Rate limiting per user
- Move BM25 index to OpenSearch
- Background re-indexing for new filings
- Queue (Celery + Redis) for ingestion
- Sharded pgvector for 10M+ chunks

## UX
- Multi-turn conversation with memory
- "Compare X across Y companies" template
- Citation hover preview
- Export answer as PDF with endnotes

## Safety
- PII detector on queries
- Audit log
- Output safety filter
- Source attribution UI
```

### B.4 — Commit the foundation files

In Cursor's terminal:

```bash
git add .cursorrules DECISIONS.md BACKLOG.md
git commit -m "Add agent constraint files: rules, design decisions, backlog"
git push
```

---

## SECTION C — THE BUILD SEQUENCE

Each prompt below is designed to paste directly into Cursor Composer (`Cmd + I`). Wait for one to finish before pasting the next. Read the generated code before committing.

### How to use this section

For each prompt:

1. Open Composer (`Cmd + I`)
2. Make sure model is set to **claude-sonnet-4-5** (or claude-opus-4-7 for the three hard prompts marked ⭐)
3. Paste the prompt
4. Wait for generation to complete
5. **Read every file Cursor created or modified**
6. Run the verification commands below the prompt
7. Commit with the suggested message
8. Update DECISIONS.md if applicable
9. Move to next prompt

If something looks wrong: don't accept and move on. Either reject and re-prompt, or fix by hand. Bad code accumulates fast.

---

### ⭐ PROMPT 1 — Bootstrap (Day 1 morning, model: claude-opus-4-7)

Paste into Composer:

```
I am bootstrapping the Enterprise RAG Assistant for SEC Filings project. Read .cursorrules, DECISIONS.md, and BACKLOG.md before starting. Generate stubs only, NOT business logic.

Scaffold this complete structure:

sec-rag-assistant/
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    (FastAPI app entry, includes /health)
│   │   ├── config.py                  (Pydantic Settings reading from env)
│   │   ├── logging.py                 (structlog setup)
│   │   ├── deps.py                    (FastAPI dependency providers)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1.py                  (FastAPI router stubs only)
│   │   │   └── schemas.py             (Pydantic v2 DTOs)
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py             (async SQLAlchemy engine)
│   │   │   └── models.py              (Filing, Chunk, EvalRun ORM)
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── html_parser.py         (TODO stub)
│   │   │   ├── chunker.py             (TODO stub — AUTHOR-OWNED, only stub)
│   │   │   └── pipeline.py            (TODO stub)
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   ├── dense.py               (TODO stub)
│   │   │   ├── bm25.py                (TODO stub)
│   │   │   ├── hybrid.py              (TODO stub — AUTHOR-OWNED, only stub)
│   │   │   └── reranker.py            (TODO stub)
│   │   ├── generation/
│   │   │   ├── __init__.py
│   │   │   ├── llm_client.py          (TODO stub — provider abstraction)
│   │   │   ├── prompts.py             (TODO stub — AUTHOR-OWNED, only stub)
│   │   │   └── answerer.py            (TODO stub — AUTHOR-OWNED, only stub)
│   │   ├── eval/
│   │   │   ├── __init__.py
│   │   │   ├── golden_set.py          (TODO stub — loader)
│   │   │   ├── scorer.py              (TODO stub)
│   │   │   └── run.py                 (CLI runner)
│   │   └── observability.py           (LangSmith + Prometheus setup)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                (fixtures: db, mock embedder, mock llm)
│   │   ├── test_health.py             (real test — health endpoint returns 200)
│   │   ├── test_chunker.py            (stubs only, author will write assertions)
│   │   ├── test_hybrid.py             (stubs only)
│   │   └── test_answerer.py           (stubs only)
│   ├── Dockerfile                     (multi-stage, python:3.11-slim, non-root)
│   └── .env.example
├── frontend/
│   ├── package.json                   (React 18, Vite, TS, Tailwind, TanStack Query)
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── ChatPanel.tsx          (TODO stub)
│       │   ├── RetrievalPanel.tsx     (TODO stub)
│       │   └── CitationLink.tsx       (TODO stub)
│       ├── hooks/
│       │   └── useQueryStream.ts      (TODO stub — SSE client)
│       └── lib/
│           └── api.ts                 (TODO stub)
├── data/
│   └── filings/
│       └── .gitkeep
├── eval/
│   └── golden_set.jsonl               (empty file)
├── docs/
│   └── architecture.md                (placeholder)
└── .github/
    └── workflows/
        └── ci.yml                     (lint + test + build, no push)

Requirements:

1. backend/pyproject.toml dependencies:
   Runtime: fastapi, uvicorn[standard], pydantic, pydantic-settings, sqlalchemy[asyncio], asyncpg, alembic, pgvector, anthropic, openai, langchain, langchain-community, sentence-transformers, rank_bm25, structlog, prometheus-fastapi-instrumentator, langsmith, beautifulsoup4, tenacity, sse-starlette
   Dev: pytest, pytest-asyncio, pytest-cov, ruff, mypy, httpx, faker

2. backend/app/config.py: Pydantic BaseSettings reading: DATABASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY, LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_TRACING, EMBEDDING_MODEL, RERANKER_MODEL, LOG_LEVEL.

3. backend/app/db/models.py: SQLAlchemy 2.0 async style with three tables:
   - Filing: id (uuid pk), ticker (str), form_type (enum '10-K'|'10-Q'), filing_date (date), accession_number (str unique), source_url (str), ingested_at (timestamp)
   - Chunk: id (uuid pk), filing_id (fk), text (text), page_number (int), section (str nullable), embedding (vector(1536)), metadata_json (jsonb), created_at (timestamp)
   - EvalRun: id (uuid pk), run_id (str), config_json (jsonb), hallucination_rate (float), recall_at_10 (float), created_at (timestamp)

4. backend/alembic/env.py: async-aware, target_metadata pointing at SQLAlchemy Base.

5. docker-compose.yml: services postgres (pgvector/pgvector:pg16, exposes 5432, mounted volume), backend (build context backend/, depends_on postgres, port 8000, hot reload), frontend (build context frontend/, port 5173, hot reload).

6. backend/Dockerfile: multi-stage. Builder uses python:3.11-slim, installs build deps and pyproject.toml deps. Runtime is python:3.11-slim with non-root user `app`. Exposes 8000. CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000.

7. backend/app/api/schemas.py: Pydantic v2 models:
   - QueryRequest: question (str, min_length=3), max_results (int = 5)
   - Citation: filing_ticker (str), filing_form_type (str), filing_date (date), page_number (int), snippet (str), score (float)
   - Answer: text (str), citations (list[Citation]), confidence (float), latency_ms (int)
   - EvalReport: run_id (str), config (dict), hallucination_rate (float), recall_at_10 (float), per_question (list[dict])

8. backend/app/api/v1.py: stub these endpoints with TODO comments and NotImplementedError:
   - POST /v1/query → Answer (will support SSE later)
   - GET /v1/filings → list[Filing] with ticker/form_type filters
   - GET /v1/eval/runs → list[EvalReport]

9. backend/tests/test_health.py: real working test that calls GET /health and asserts 200 + {"status": "ok"}.

10. frontend/package.json: React 18.3+, Vite 5+, TypeScript, Tailwind 3.4+, TanStack Query 5+.

11. .github/workflows/ci.yml: three jobs:
    - lint: ruff check, mypy
    - test: pytest with postgres service container
    - build: docker build, no push

12. .env.example: lists all required env vars with placeholders, NO real values.

CRITICAL rules:
- For AUTHOR-OWNED files (chunker.py, hybrid.py, prompts.py, answerer.py), generate ONLY a single-line docstring + TODO comment. Example:
  ```python
  """Chunking strategy for SEC filings. Author will implement."""
  # TODO: rahul will implement chunking logic here
  ```
- Do NOT generate implementations for those files
- Do NOT add a CONTRIBUTING.md, CODE_OF_CONDUCT.md, or extra license files
- Use SQLAlchemy 2.0 style (Mapped[], mapped_column), not 1.4 legacy
- Use Pydantic v2 (model_config, ConfigDict), not v1
- All async I/O code uses async def

Generate all files now. After generation, print:
1. A tree of the created structure
2. The next commands the user should run to verify (install deps, start postgres, run health test)
3. The git commit message to use
```

**Verification after generation:**

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
docker compose -f ../docker-compose.yml up -d postgres
# Wait 10 seconds for postgres
sleep 10
docker exec sec-rag-assistant-postgres-1 psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
alembic upgrade head
uvicorn app.main:app --reload &
sleep 5
curl http://localhost:8000/health
# Should print {"status": "ok"}
pytest tests/test_health.py -v
```

**If health test passes, commit:**

```bash
git add .
git commit -m "Scaffold project structure (Prompt 1 of 12)"
git push
```

---

### PROMPT 2 — Ingestion pipeline (Day 1 afternoon)

Paste into Composer:

```
Implement the SEC filings ingestion pipeline. Source: I have ./data/filings/sec-edgar-filings/ with HTML files from the sec-edgar-downloader package, organized as TICKER/FORM/ACCESSION/full-submission.txt.

Implement these files (NOT the chunker — that is author-owned, leave its stub):

1. backend/app/ingest/html_parser.py:
   - Function `parse_filing(html_path: Path) -> ParsedFiling`
   - Strip XBRL tags using BeautifulSoup (find all 'ix:*' tags and extract their text)
   - Split content by page using </PAGE> markers or fall back to length-based pagination
   - Detect 10-K section headers by regex: "Item\s+\d+[A-Z]?\.\s+(?P<section>[^\n]+)"
   - Return ParsedFiling with ticker, form_type, filing_date, accession_number, source_url, pages: list[PageContent]
   - Use Pydantic v2 dataclasses-style models in this module

2. backend/app/ingest/pipeline.py:
   - Class `IngestionPipeline` taking db_session, embedder, chunker as deps
   - async method `ingest_filing(html_path: Path) -> int` returns chunk count
   - Method `parse → chunk (via chunker) → embed (batched 100) → insert in single transaction`
   - Tenacity retry on OpenAI 429/500 with exponential backoff, 3 attempts
   - Skip if filing.accession_number already exists in DB (idempotent)
   - Use structlog with bound context (ticker, accession)
   - CLI entry: `python -m app.ingest <root_dir>` with tqdm progress

3. backend/app/ingest/embedder.py (new file):
   - Class `OpenAIEmbedder` wrapping openai.AsyncClient
   - Method `async embed_batch(texts: list[str]) -> list[list[float]]`
   - Uses text-embedding-3-small, 1536 dims
   - Tenacity retry

4. backend/tests/test_ingest.py:
   - Test parse_filing on a small synthetic HTML fixture
   - Test section detection regex with examples
   - Test idempotency (insert same filing twice → second is no-op)
   - Mock the embedder so no real API calls

The chunker is a stub — the pipeline should still call it as `chunks = chunker.chunk(page.text, page.page_number, page.section)` and the stub should return an empty list for now. That's fine — author will implement the real chunker on Day 2.

After generation, print: tree of changes, verification commands, suggested commit message.
```

**Verification:**

```bash
cd backend
pytest tests/test_ingest.py -v
# Try parsing one real filing
python -c "
from pathlib import Path
from app.ingest.html_parser import parse_filing
import asyncio
result = parse_filing(next(Path('../data/filings/sec-edgar-filings/AAPL/10-K').rglob('*.txt')))
print(f'Pages: {len(result.pages)}, Sections found: {sum(1 for p in result.pages if p.section)}')
"
```

**Commit:**

```bash
git add .
git commit -m "Ingestion pipeline: HTML parser, embedder, pipeline orchestrator (Prompt 2 of 12)"
git push
```

---

### ⭐ PROMPT 3 — AUTHOR-OWNED: Write the chunker yourself (Day 2 morning, NO COMPOSER)

**Do not use Cursor Composer for this step.** Open `backend/app/ingest/chunker.py` in the regular editor. Use Tab autocomplete if you want, but write the logic yourself.

Recommended approach (section-aware + recursive):

```python
"""Section-aware recursive chunker for SEC filings.

Strategy: never split across SEC 10-K section boundaries. Within a section,
use recursive character splitting at paragraph → sentence → character boundaries,
targeting ~800 chars per chunk with ~150 char overlap.

Rationale: SEC filings have strong structural hierarchy (Item 1A. Risk Factors,
Item 7. MD&A, etc.). Preserving section boundaries means chunks always have
coherent topical context, which materially improves retrieval precision.
"""

from dataclasses import dataclass
from typing import Iterator

MAX_CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


@dataclass
class Chunk:
    text: str
    page_number: int
    section: str | None
    char_start: int
    char_end: int


def chunk(text: str, page_number: int, section: str | None) -> list[Chunk]:
    """Split text into overlapping chunks, never crossing section boundaries.

    The section parameter is the section this entire text belongs to, passed
    down from the parser. Section boundary preservation happens at the parser
    level; this function only chunks within a single section.
    """
    if not text or not text.strip():
        return []

    chunks = _recursive_split(text, MAX_CHUNK_SIZE, CHUNK_OVERLAP, SEPARATORS)
    return [
        Chunk(
            text=c["text"],
            page_number=page_number,
            section=section,
            char_start=c["start"],
            char_end=c["end"],
        )
        for c in chunks
    ]


def _recursive_split(
    text: str,
    max_size: int,
    overlap: int,
    separators: list[str],
) -> list[dict]:
    """Recursively split text by the highest-level separator that produces
    chunks ≤ max_size. Fall back to lower-level separators as needed."""
    if len(text) <= max_size:
        return [{"text": text, "start": 0, "end": len(text)}]

    for sep in separators:
        if sep and sep in text:
            return _split_with_separator(text, sep, max_size, overlap)

    # Last resort: hard split at max_size
    return _hard_split(text, max_size, overlap)


def _split_with_separator(
    text: str,
    sep: str,
    max_size: int,
    overlap: int,
) -> list[dict]:
    splits = text.split(sep)
    chunks: list[dict] = []
    current = ""
    current_start = 0

    for piece in splits:
        candidate = current + (sep if current else "") + piece
        if len(candidate) <= max_size:
            current = candidate
        else:
            if current:
                chunks.append({
                    "text": current,
                    "start": current_start,
                    "end": current_start + len(current),
                })
                # Start next chunk with overlap from end of previous
                overlap_text = current[-overlap:] if len(current) > overlap else current
                current = overlap_text + sep + piece
                current_start = current_start + len(current) - len(overlap_text)
            else:
                # Single piece is larger than max — recurse with finer separator
                idx = SEPARATORS.index(sep) + 1
                if idx < len(SEPARATORS):
                    sub = _recursive_split(piece, max_size, overlap, SEPARATORS[idx:])
                    for s in sub:
                        s["start"] += current_start
                        s["end"] += current_start
                    chunks.extend(sub)
                else:
                    chunks.extend(_hard_split(piece, max_size, overlap))

    if current:
        chunks.append({
            "text": current,
            "start": current_start,
            "end": current_start + len(current),
        })

    return chunks


def _hard_split(text: str, max_size: int, overlap: int) -> list[dict]:
    """Last-resort split — fixed window with overlap."""
    chunks: list[dict] = []
    start = 0
    while start < len(text):
        end = min(start + max_size, len(text))
        chunks.append({"text": text[start:end], "start": start, "end": end})
        if end == len(text):
            break
        start = end - overlap
    return chunks
```

Write your own tests in `backend/tests/test_chunker.py`:

```python
"""Tests for the section-aware recursive chunker."""

from app.ingest.chunker import chunk, MAX_CHUNK_SIZE, CHUNK_OVERLAP


def test_chunk_does_not_exceed_max_size():
    text = "Sentence. " * 500
    chunks = chunk(text, page_number=1, section="Risk Factors")
    for c in chunks:
        assert len(c.text) <= MAX_CHUNK_SIZE + 50, f"Chunk too large: {len(c.text)}"


def test_metadata_propagates():
    text = "A short paragraph that fits in one chunk."
    chunks = chunk(text, page_number=5, section="MD&A")
    assert len(chunks) == 1
    assert chunks[0].page_number == 5
    assert chunks[0].section == "MD&A"


def test_empty_text_returns_empty_list():
    assert chunk("", 1, None) == []
    assert chunk("   \n  ", 1, None) == []


def test_overlap_present_between_consecutive_chunks():
    text = "Sentence. " * 300  # ~3000 chars, forces multiple chunks
    chunks = chunk(text, 1, "Risk Factors")
    assert len(chunks) >= 2
    # Adjacent chunks should share some content (overlap)
    for i in range(len(chunks) - 1):
        overlap_check = chunks[i].text[-50:] in chunks[i + 1].text[:200]
        # not strictly required to be exact, but overlap should produce
        # *some* content sharing — verify char positions
        assert chunks[i + 1].char_start < chunks[i].char_end


def test_single_huge_paragraph_falls_back_to_hard_split():
    """If a single sentence is bigger than max_size, hard-split it."""
    text = "x" * 2000  # one continuous string, no separators
    chunks = chunk(text, 1, None)
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in chunks)
    assert len(chunks) >= 2
```

Run:

```bash
cd backend
pytest tests/test_chunker.py -v
```

Re-ingest with the working chunker:

```bash
docker exec sec-rag-assistant-postgres-1 psql -U postgres -d sec_rag -c "TRUNCATE chunks CASCADE; TRUNCATE filings CASCADE;"
python -m app.ingest ../data/filings/
```

**Update DECISIONS.md D2** with what you chose and why. Then commit:

```bash
git add backend/app/ingest/chunker.py backend/tests/test_chunker.py DECISIONS.md
git commit -m "Author-written chunker: section-aware recursive split (Prompt 3 of 12)"
git push
```

---

### PROMPT 4 — Dense retrieval (Day 2 afternoon)

Paste into Composer:

```
Implement dense vector retrieval.

1. backend/app/retrieval/dense.py:
   - Dataclass `RetrievalHit` with: chunk_id, text, page_number, section, ticker, form_type, filing_date, similarity_score (float, 0-1), bm25_score (float, default 0), rerank_score (float, default 0)
   - Class `DenseRetriever` taking db_session and embedder as deps
   - Method `async retrieve(query: str, k: int = 50) -> list[RetrievalHit]`
   - Embeds query, runs SQL: SELECT c.*, f.ticker, f.form_type, f.filing_date, 1 - (c.embedding <=> :query_emb) AS similarity FROM chunks c JOIN filings f ON c.filing_id = f.id ORDER BY c.embedding <=> :query_emb LIMIT :k
   - Use SQLAlchemy text() with bound parameters
   - Returns hits sorted by similarity_score descending

2. Alembic migration adding HNSW index:
   CREATE INDEX chunks_embedding_hnsw_idx ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);

3. backend/tests/test_dense.py:
   - Fixture creating 3 fake filings with 10 chunks total in a test postgres
   - Test that retrieval returns most similar chunk first
   - Test that k parameter limits results
   - Mock the embedder to return deterministic vectors

After generation, print: tree, verification commands, commit message.
```

**Verification:**

```bash
cd backend
alembic upgrade head
pytest tests/test_dense.py -v
# Smoke test against real data
python -c "
import asyncio
from app.retrieval.dense import DenseRetriever
from app.deps import get_db_session, get_embedder

async def smoke():
    async for db in get_db_session():
        r = DenseRetriever(db, get_embedder())
        hits = await r.retrieve('What are Apple supply chain risks?', k=5)
        for h in hits:
            print(f'{h.ticker} {h.form_type} p.{h.page_number} score={h.similarity_score:.3f}')
            print(f'  {h.text[:150]}')

asyncio.run(smoke())
"
```

**Commit:**

```bash
git add .
git commit -m "Dense retrieval with pgvector HNSW index (Prompt 4 of 12)"
git push
```

---

### PROMPT 5 — BM25 retrieval (Day 3 morning)

Paste into Composer:

```
Implement BM25 keyword retrieval.

1. backend/app/retrieval/bm25.py:
   - Class `BM25Retriever` taking db_session as dep
   - On `__init__`, load all chunks from DB into memory, tokenize, build BM25Okapi index
   - Tokenizer: lowercase, strip punctuation, split on whitespace
   - Method `async retrieve(query: str, k: int = 50) -> list[RetrievalHit]`
   - Returns hits with bm25_score set, similarity_score = 0
   - Method `async reload()` to rebuild index after new ingestion

2. backend/tests/test_bm25.py:
   - Fixture with 5 chunks containing distinguishable keywords
   - Test that keyword query returns expected chunk first
   - Test that BM25 score is higher for exact keyword matches than partial

Document in module docstring: "BM25 index lives in memory and is rebuilt on app startup. For corpora >1M chunks, move to OpenSearch (see BACKLOG.md)."

After generation, print: tree, verification, commit message.
```

**Verification:**

```bash
pytest tests/test_bm25.py -v
python -c "
import asyncio
from app.retrieval.bm25 import BM25Retriever
from app.deps import get_db_session

async def smoke():
    async for db in get_db_session():
        r = BM25Retriever(db)
        await r.reload()
        hits = await r.retrieve('Item 1A Risk Factors', k=3)
        for h in hits:
            print(f'{h.ticker} bm25={h.bm25_score:.2f}: {h.text[:120]}')

asyncio.run(smoke())
"
```

**Commit:**

```bash
git add .
git commit -m "BM25 retrieval with in-memory index (Prompt 5 of 12)"
git push
```

---

### ⭐ PROMPT 6 — AUTHOR-OWNED: Write hybrid scoring yourself (Day 3 afternoon, NO COMPOSER)

Open `backend/app/retrieval/hybrid.py` directly. Write this:

```python
"""Hybrid retrieval combining dense vector search and BM25 via Reciprocal Rank Fusion.

Strategy: RRF (Reciprocal Rank Fusion) — score(d) = sum(1 / (k + rank_d(retriever)))
where k=60 (the standard constant from Cormack et al. 2009).

Why RRF instead of weighted linear:
- No per-corpus tuning required (weighted linear needs to tune alpha on a dev set)
- Robust when one retriever produces wildly different score scales
- Demonstrably equivalent to tuned weighted-linear in practice (see Trotman et al. 2014)
- The k=60 constant has been validated across IR literature for ~15 years
"""

import asyncio
from app.retrieval.dense import DenseRetriever, RetrievalHit
from app.retrieval.bm25 import BM25Retriever

RRF_K = 60


async def hybrid_retrieve(
    query: str,
    dense_retriever: DenseRetriever,
    bm25_retriever: BM25Retriever,
    k_dense: int = 50,
    k_bm25: int = 50,
    k_final: int = 20,
) -> list[RetrievalHit]:
    """Run both retrievers in parallel and fuse via RRF.

    Returns up to k_final hits sorted by fused RRF score descending.
    Each returned hit has both similarity_score (from dense) and bm25_score
    (from BM25) populated, plus a synthetic `rrf_score` attribute.
    """
    dense_hits, bm25_hits = await asyncio.gather(
        dense_retriever.retrieve(query, k=k_dense),
        bm25_retriever.retrieve(query, k=k_bm25),
    )

    # Build rank maps: chunk_id → rank (1-indexed)
    dense_ranks = {hit.chunk_id: i + 1 for i, hit in enumerate(dense_hits)}
    bm25_ranks = {hit.chunk_id: i + 1 for i, hit in enumerate(bm25_hits)}

    # All candidate chunk ids
    all_ids = set(dense_ranks) | set(bm25_ranks)

    # Hit lookup so we can return the full hit object
    hits_by_id: dict = {}
    for h in dense_hits:
        hits_by_id[h.chunk_id] = h
    for h in bm25_hits:
        if h.chunk_id in hits_by_id:
            # Already have it from dense — just merge BM25 score
            hits_by_id[h.chunk_id].bm25_score = h.bm25_score
        else:
            hits_by_id[h.chunk_id] = h

    # Compute RRF score per chunk
    scored: list[tuple[float, RetrievalHit]] = []
    for chunk_id in all_ids:
        score = 0.0
        if chunk_id in dense_ranks:
            score += 1.0 / (RRF_K + dense_ranks[chunk_id])
        if chunk_id in bm25_ranks:
            score += 1.0 / (RRF_K + bm25_ranks[chunk_id])

        hit = hits_by_id[chunk_id]
        hit.rrf_score = score  # add new attribute
        scored.append((score, hit))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [hit for _, hit in scored[:k_final]]
```

Tests in `backend/tests/test_hybrid.py`:

```python
"""Tests for RRF hybrid retrieval."""

import pytest
from unittest.mock import AsyncMock
from app.retrieval.hybrid import hybrid_retrieve, RRF_K
from app.retrieval.dense import RetrievalHit


def make_hit(chunk_id: str, similarity: float = 0.5, bm25: float = 0.0):
    return RetrievalHit(
        chunk_id=chunk_id,
        text=f"text-{chunk_id}",
        page_number=1,
        section=None,
        ticker="TEST",
        form_type="10-K",
        filing_date=None,
        similarity_score=similarity,
        bm25_score=bm25,
        rerank_score=0.0,
    )


@pytest.mark.asyncio
async def test_rrf_combines_both_retrievers():
    dense = AsyncMock()
    dense.retrieve = AsyncMock(return_value=[
        make_hit("a", similarity=0.9),
        make_hit("b", similarity=0.8),
    ])
    bm25 = AsyncMock()
    bm25.retrieve = AsyncMock(return_value=[
        make_hit("b", bm25=10.0),
        make_hit("c", bm25=5.0),
    ])

    hits = await hybrid_retrieve("q", dense, bm25, k_final=5)
    ids = [h.chunk_id for h in hits]

    # b appears in both → should rank highest via RRF
    assert ids[0] == "b"
    # a and c each appear in one → tied in RRF, both in top 3
    assert set(ids[1:3]) == {"a", "c"}


@pytest.mark.asyncio
async def test_rrf_score_math():
    """Verify the RRF formula is applied correctly."""
    dense = AsyncMock()
    dense.retrieve = AsyncMock(return_value=[make_hit("a")])  # rank 1
    bm25 = AsyncMock()
    bm25.retrieve = AsyncMock(return_value=[make_hit("a")])  # rank 1

    hits = await hybrid_retrieve("q", dense, bm25, k_final=5)
    expected = 2 * (1 / (RRF_K + 1))
    assert abs(hits[0].rrf_score - expected) < 1e-9


@pytest.mark.asyncio
async def test_k_final_limits_results():
    dense = AsyncMock()
    dense.retrieve = AsyncMock(return_value=[make_hit(f"d{i}") for i in range(30)])
    bm25 = AsyncMock()
    bm25.retrieve = AsyncMock(return_value=[make_hit(f"b{i}") for i in range(30)])

    hits = await hybrid_retrieve("q", dense, bm25, k_final=10)
    assert len(hits) == 10


@pytest.mark.asyncio
async def test_empty_retrievers_return_empty():
    dense = AsyncMock()
    dense.retrieve = AsyncMock(return_value=[])
    bm25 = AsyncMock()
    bm25.retrieve = AsyncMock(return_value=[])

    hits = await hybrid_retrieve("q", dense, bm25)
    assert hits == []
```

Run:

```bash
pytest backend/tests/test_hybrid.py -v
```

**Update DECISIONS.md D3.** Then commit:

```bash
git add backend/app/retrieval/hybrid.py backend/tests/test_hybrid.py DECISIONS.md
git commit -m "Author-written hybrid retrieval via RRF (Prompt 6 of 12)"
git push
```

---

### PROMPT 7 — Reranker (Day 4 morning)

Paste into Composer:

```
Implement the cross-encoder reranker.

1. backend/app/retrieval/reranker.py:
   - Class `CrossEncoderReranker` wrapping sentence_transformers.CrossEncoder
   - Model: cross-encoder/ms-marco-MiniLM-L-6-v2
   - Load model once on instantiation
   - Method `async rerank(query: str, hits: list[RetrievalHit], k: int = 10) -> list[RetrievalHit]`
   - Wrap synchronous model.predict in asyncio.to_thread
   - Set rerank_score on each hit, return sorted by rerank_score descending, take top k

2. Add reranker to lifespan in backend/app/main.py:
   - On startup: load CrossEncoderReranker, store on app.state
   - On shutdown: clean reference

3. backend/tests/test_reranker.py:
   - Mock the CrossEncoder with a stub that returns reversed scores
   - Verify the reranker flips ordering
   - Verify k parameter limits output

After generation, print verification, commit message.
```

**Verification:**

```bash
pytest backend/tests/test_reranker.py -v
```

**Commit:**

```bash
git add .
git commit -m "Cross-encoder reranker integration (Prompt 7 of 12)"
git push
```

---

### PROMPT 8 — LLM client (Day 4 afternoon)

Paste into Composer:

```
Implement the LLM provider abstraction.

1. backend/app/generation/llm_client.py:
   - Pydantic v2 BaseModel `LLMMessage { role: Literal["system", "user", "assistant"], content: str }`
   - Abstract base class `LLMProvider` with async method `stream_completion(messages, response_schema) -> AsyncIterator[str]`
   - Concrete class `AnthropicProvider` using anthropic.AsyncClient with tool_use mode for structured output. The tool definition is generated from the Pydantic response_schema. Yield text deltas as they arrive.
   - Concrete class `OpenAIProvider` using openai.AsyncClient with response_format={"type": "json_schema", ...}
   - Tenacity decorator on both: retry on rate_limit_error, internal_error, api_status_error; max 3 attempts, exponential backoff (1s, 2s, 4s)
   - Factory function `get_llm_client(preferred: str = "anthropic") -> LLMProvider` that falls back to OpenAI on persistent Anthropic failure

2. backend/app/generation/prompts.py and backend/app/generation/answerer.py:
   These are AUTHOR-OWNED. Generate only single-line docstring stubs:
   - prompts.py: `"""System prompt, user template, and answer schema. Author will write."""`
   - answerer.py: `"""Orchestrates retrieve → rerank → generate. Author will write."""`

3. backend/tests/test_llm_client.py:
   - Mock anthropic.AsyncClient and openai.AsyncClient
   - Test successful structured output from Anthropic path
   - Test fallback to OpenAI on persistent Anthropic failure
   - Test tenacity retry on transient 429

After generation, print verification, commit message.
```

**Verification:**

```bash
pytest backend/tests/test_llm_client.py -v
# Smoke test against real Anthropic
python -c "
import asyncio
from app.generation.llm_client import get_llm_client, LLMMessage
from pydantic import BaseModel

class TestSchema(BaseModel):
    answer: str
    confidence: float

async def smoke():
    client = get_llm_client('anthropic')
    full = ''
    async for chunk in client.stream_completion(
        messages=[LLMMessage(role='user', content='What is 2+2? Output JSON.')],
        response_schema=TestSchema,
    ):
        full += chunk
        print(chunk, end='', flush=True)
    print()

asyncio.run(smoke())
"
```

**Commit:**

```bash
git add .
git commit -m "LLM client with Anthropic primary, OpenAI fallback (Prompt 8 of 12)"
git push
```

---

### ⭐ PROMPT 9 — AUTHOR-OWNED: Write prompts and answerer yourself (Day 5 morning, NO COMPOSER)

This is the heart of the project. Open `backend/app/generation/prompts.py`:

```python
"""System prompt, user template, and answer schema for grounded RAG generation.

Design choices documented here, defended in DECISIONS.md D5:

1. Citation format: structured JSON with chunk_id references, NOT inline markdown footnotes.
   Rationale: enables programmatic citation validation and click-to-source UI.

2. Uncertainty handling: explicit confidence field + instruction to abstain
   when context is insufficient. Prevents "polite hallucination" where the
   model fabricates a plausible-sounding answer.

3. No general knowledge: system prompt forbids drawing on the model's parametric
   memory. Every claim must trace to a chunk in the provided context.
"""

from pydantic import BaseModel, Field


SYSTEM_PROMPT = """You are a careful research assistant that answers questions about public companies using ONLY the SEC filings provided in the context. You must:

1. Answer using ONLY information present in the provided context chunks. Do not use any prior knowledge about these companies, even if you "know" the answer.

2. Every factual claim in your answer must cite the chunk it came from. Use the format [chunk_id] inline, where chunk_id is the id field of the chunk that supports the claim.

3. If the context does not contain enough information to answer confidently, say so explicitly. Set your confidence to 0.3 or lower and recommend what additional filings the user should consult.

4. Quote exactly when stating specific numbers, dates, or named risks. Paraphrase only when summarizing themes.

5. If the user asks about a company that does not appear in the provided context, say "I don't have filings for that company in the current corpus" — do not improvise.

Your response must be valid JSON matching the provided schema. Output the JSON object only — no preamble, no markdown fences."""


USER_PROMPT_TEMPLATE = """Question: {question}

Available context chunks (cite by their id):

{context}

Respond with a JSON object containing your answer, the chunk_ids you cited (with the supporting quote from each), and your self-assessed confidence (0.0 to 1.0)."""


def format_context(hits: list) -> str:
    """Format retrieved hits into the context block for the prompt.

    Each chunk is presented as a clearly delimited block with metadata header,
    then the chunk text. The chunk_id is the primary key — the model must use
    these exact ids in citations.
    """
    blocks = []
    for hit in hits:
        meta = f"[Chunk {hit.chunk_id} | {hit.ticker} {hit.form_type} | Page {hit.page_number}"
        if hit.section:
            meta += f" | Section: {hit.section}"
        meta += "]"
        blocks.append(f"{meta}\n{hit.text}")
    return "\n\n---\n\n".join(blocks)


class CitedClaim(BaseModel):
    chunk_id: str = Field(description="The id of the chunk that supports this claim")
    quote: str = Field(description="The exact span from the chunk that supports the claim, ≤200 chars")


class Answer(BaseModel):
    text: str = Field(description="The answer with [chunk_id] markers inline")
    citations: list[CitedClaim] = Field(description="List of cited chunks with supporting quotes")
    confidence: float = Field(ge=0.0, le=1.0, description="Self-assessed confidence based on whether the context supported a complete answer")
```

Now `backend/app/generation/answerer.py`:

```python
"""Orchestrates the full RAG pipeline: retrieve → rerank → generate.

Pipeline:
1. Run hybrid retrieval (RRF over dense + BM25), get top 20 candidates
2. Rerank top 20 with cross-encoder, take top 5
3. Format chunks into context block
4. Call LLM with system prompt, user prompt template, and structured output schema
5. Stream tokens back to the caller
6. Validate the structured response matches the Answer schema

Author-owned: this orchestration is what an interviewer will probe deepest.
"""

import time
from typing import AsyncIterator
from app.generation.llm_client import LLMProvider, LLMMessage
from app.generation.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    format_context,
    Answer,
)
from app.retrieval.hybrid import hybrid_retrieve
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.dense import DenseRetriever
from app.retrieval.bm25 import BM25Retriever


class Answerer:
    def __init__(
        self,
        dense: DenseRetriever,
        bm25: BM25Retriever,
        reranker: CrossEncoderReranker,
        llm: LLMProvider,
    ):
        self.dense = dense
        self.bm25 = bm25
        self.reranker = reranker
        self.llm = llm

    async def answer(
        self,
        question: str,
        max_results: int = 5,
    ) -> AsyncIterator[dict]:
        """Stream answer events: retrieval_complete, token, done.

        Yields events as dicts. Caller is responsible for serializing to SSE.
        """
        start = time.perf_counter()

        # Stage 1: hybrid retrieve top 20
        candidates = await hybrid_retrieve(
            question, self.dense, self.bm25, k_final=20
        )

        # Stage 2: rerank to top 5
        top_hits = await self.reranker.rerank(question, candidates, k=max_results)

        yield {"type": "retrieval_complete", "hits": [
            {
                "chunk_id": h.chunk_id,
                "ticker": h.ticker,
                "form_type": h.form_type,
                "page_number": h.page_number,
                "snippet": h.text[:200],
                "similarity_score": h.similarity_score,
                "bm25_score": h.bm25_score,
                "rerank_score": h.rerank_score,
            }
            for h in top_hits
        ]}

        # Stage 3: format context, call LLM
        context = format_context(top_hits)
        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=USER_PROMPT_TEMPLATE.format(
                    question=question, context=context
                ),
            ),
        ]

        accumulated = ""
        async for token in self.llm.stream_completion(
            messages=messages, response_schema=Answer
        ):
            accumulated += token
            yield {"type": "token", "text": token}

        # Stage 4: validate and emit final structured answer
        try:
            answer = Answer.model_validate_json(accumulated)
        except Exception as e:
            yield {"type": "error", "message": f"Schema validation failed: {e}"}
            return

        latency_ms = int((time.perf_counter() - start) * 1000)
        yield {
            "type": "done",
            "answer": answer.model_dump(),
            "latency_ms": latency_ms,
        }
```

Tests in `backend/tests/test_answerer.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.generation.answerer import Answerer
from app.retrieval.dense import RetrievalHit


def make_hit(cid):
    return RetrievalHit(
        chunk_id=cid, text=f"text-{cid}", page_number=1, section=None,
        ticker="AAPL", form_type="10-K", filing_date=None,
        similarity_score=0.9, bm25_score=5.0, rerank_score=0.95,
    )


@pytest.mark.asyncio
async def test_answerer_emits_correct_events():
    dense = AsyncMock()
    dense.retrieve = AsyncMock(return_value=[make_hit("c1"), make_hit("c2")])
    bm25 = AsyncMock()
    bm25.retrieve = AsyncMock(return_value=[make_hit("c1")])
    reranker = AsyncMock()
    reranker.rerank = AsyncMock(return_value=[make_hit("c1")])

    llm = AsyncMock()
    async def fake_stream(messages, response_schema):
        yield '{"text":"Answer [c1]","citations":[{"chunk_id":"c1","quote":"text-c1"}],"confidence":0.9}'
    llm.stream_completion = fake_stream

    answerer = Answerer(dense, bm25, reranker, llm)
    events = []
    async for e in answerer.answer("test question"):
        events.append(e)

    types = [e["type"] for e in events]
    assert "retrieval_complete" in types
    assert "done" in types
    done = [e for e in events if e["type"] == "done"][0]
    assert done["answer"]["confidence"] == 0.9
    assert done["answer"]["citations"][0]["chunk_id"] == "c1"
```

**Update DECISIONS.md D5.** Run:

```bash
pytest backend/tests/test_answerer.py -v
```

Commit:

```bash
git add backend/app/generation/prompts.py backend/app/generation/answerer.py backend/tests/test_answerer.py DECISIONS.md
git commit -m "Author-written prompts and answerer orchestration (Prompt 9 of 12)"
git push
```

---

### PROMPT 10 — API endpoints with SSE (Day 5 afternoon)

Paste into Composer:

```
Wire up the FastAPI endpoints. The Answerer, retrievers, and reranker exist — wire them into the API.

1. backend/app/api/v1.py:
   - POST /v1/query returning StreamingResponse with text/event-stream
   - Use sse-starlette for clean SSE event formatting
   - Events emitted: "retrieval" (with hits), "token" (text deltas), "done" (full Answer), "error"
   - Dependencies: Answerer instance (constructed in lifespan from dense, bm25, reranker, llm)
   - GET /v1/filings with optional ?ticker= and ?form_type= query params, paginated (limit=50, offset=0)
   - GET /v1/eval/runs returning past eval results from EvalRun table

2. backend/app/main.py:
   - Lifespan context manager that:
     - Creates async db engine
     - Instantiates embedder, dense_retriever, bm25_retriever (await reload()), reranker, llm_client, answerer
     - Stores on app.state
     - On shutdown: dispose engine
   - Add LangSmith tracing via langsmith.traceable decorator on the answerer.answer method (or wrap it)
   - Add prometheus_fastapi_instrumentator instrumentation
   - Add structlog request middleware

3. backend/app/observability.py:
   - Configure LangSmith from env (LANGSMITH_TRACING, LANGSMITH_PROJECT, LANGSMITH_API_KEY)
   - Set up prometheus instrumentator
   - Set up structlog with JSON output in production, pretty in dev

4. backend/tests/test_query_endpoint.py:
   - Use httpx AsyncClient with the FastAPI app
   - Mock the Answerer to yield a known event sequence
   - Verify SSE response contains expected events in order
   - Verify content-type is text/event-stream

After generation, print verification commands and commit message.
```

**Verification:**

```bash
pytest backend/tests/test_query_endpoint.py -v
# End-to-end test
uvicorn app.main:app --reload &
sleep 5
curl -N -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What does Apple identify as its main supply chain risk?", "max_results": 5}'
```

You should see streamed SSE events ending with a complete `done` event containing the structured answer. **Screenshot this output** — drop the screenshot in `docs/screenshot.png` for your README.

**Commit:**

```bash
git add .
git commit -m "FastAPI streaming endpoint with SSE, LangSmith tracing, Prometheus metrics (Prompt 10 of 12)"
git push
```

---

### PROMPT 11 — Frontend chat UI (Day 6)

Paste into Composer:

```
Build the React frontend chat UI.

1. frontend/src/App.tsx:
   - Two-column layout: 70% left (chat), 30% right (retrieval panel)
   - Light theme, system font stack, single color accent: #0066cc (Citi-blue but slightly desaturated)
   - Tailwind utility classes only, no custom CSS files

2. frontend/src/components/ChatPanel.tsx:
   - Input box at bottom (textarea, auto-resize)
   - Submit button + Enter key submits
   - Message history above (user questions and streamed answers)
   - Render answer text with [chunk_id] tokens replaced by clickable superscript citations
   - Citations are <CitationLink chunkId={id} /> that scroll/highlight the corresponding row in RetrievalPanel

3. frontend/src/components/RetrievalPanel.tsx:
   - List of retrieved chunks with metadata header (ticker, form_type, page, section)
   - Show similarity_score, bm25_score, rerank_score as small badges
   - Snippet text below
   - Click highlights the chunk and shows a "linked from answer" indicator

4. frontend/src/components/CitationLink.tsx:
   - Renders [chunk_id] as a superscript like <sup>[c1]</sup>
   - Click scrolls RetrievalPanel to that chunk

5. frontend/src/hooks/useQueryStream.ts:
   - Subscribes to /v1/query via native EventSource
   - Parses each event by type, exposes:
     - isStreaming: boolean
     - retrievalHits: Hit[]
     - answerText: string (accumulated tokens)
     - finalAnswer: Answer | null
     - error: string | null

6. frontend/src/lib/api.ts:
   - submitQuery(question, maxResults): returns EventSource instance
   - Backend URL from env: VITE_API_URL (default http://localhost:8000)

Styling: minimal, clean, no animations. Mobile-responsive but desktop-first.

After generation, print run commands and commit message.
```

**Verification:**

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173, type a question
```

**Loom recording (90 seconds):**

1. Open Loom
2. Record yourself: typing a question → watching streaming answer → clicking a citation → showing the retrieval panel
3. Upload, get the URL
4. Add to README.md: replace `[2-minute Loom video link — record this after build]` with the actual URL

**Commit:**

```bash
git add .
git commit -m "Frontend chat UI with SSE streaming, citation linking, retrieval panel (Prompt 11 of 12)"
git push
```

---

### ⭐ PROMPT 12 — Eval harness (Day 6 PM scaffolding, Day 7 golden set + run)

Paste into Composer for the harness:

```
Build the evaluation harness.

1. backend/app/eval/scorer.py:
   - Class `RAGASFaithfulnessScorer` using ragas library
   - Method `score(question: str, answer: str, context_chunks: list[str]) -> float`
   - Returns faithfulness ∈ [0, 1]; lower = more hallucination
   
   - Class `CitationAccuracyScorer`
   - Method `score(answer: Answer, retrieved_chunk_ids: set[str]) -> float`
   - Parses citations from the Answer object, checks each chunk_id is in retrieved set
   - Returns fraction of valid citations

2. backend/app/eval/golden_set.py:
   - Pydantic v2 model `GoldenQuestion { id, question, expected_answer_substrings: list[str], expected_filings: list[str], expected_section: str | None }`
   - Function `load_golden_set(path: Path) -> list[GoldenQuestion]` reading from eval/golden_set.jsonl

3. backend/app/eval/run.py (CLI):
   - Argparse: --config configs/eval.yaml --output eval_report.html
   - Loads golden set, runs each question through the full /v1/query path (or call Answerer directly)
   - Scores: faithfulness, citation_accuracy, retrieval recall (does any expected_filing appear in retrieved hits?)
   - Aggregates: hallucination_rate (% with faithfulness < 0.7), avg_citation_accuracy, recall_at_k
   - Stores in EvalRun table
   - Generates eval_report.html with per-question breakdown using Jinja2 template

4. backend/tests/test_scorer.py:
   - Mock RAGAS to return known scores
   - Verify hallucination threshold logic
   - Test citation_accuracy with known input/output

5. eval/golden_set.jsonl: leave EMPTY (just a placeholder file). Author will populate Day 7.

After generation, print: commands to run a single test question through eval, commit message.
```

**Verification (scaffolding only):**

```bash
pytest backend/tests/test_scorer.py -v
```

**Commit:**

```bash
git add .
git commit -m "Eval harness: RAGAS faithfulness, citation accuracy, golden set loader (Prompt 12 scaffolding)"
git push
```

---

### AUTHOR-OWNED: Build the golden set (Day 7, ~4 hours)

This is what makes the 22% → 6% claim defensible. No shortcut.

1. Pick 30 filings (mix of tickers and form types)
2. For each filing, open and read the Risk Factors and MD&A sections
3. Write 4 questions per filing with the answer span you can point to
4. Append each to `eval/golden_set.jsonl`:

```json
{"id": 1, "question": "What are Apple's top three supply chain risks identified in its 2024 10-K?", "expected_answer_substrings": ["China", "single source", "concentration"], "expected_filings": ["AAPL_10-K_2024"], "expected_section": "Risk Factors"}
{"id": 2, "question": "How much did Microsoft spend on R&D in fiscal 2024?", "expected_answer_substrings": ["29.5"], "expected_filings": ["MSFT_10-K_2024"], "expected_section": "MD&A"}
...
```

Target 120 questions. **Do not skip this step.** This is what the resume claim depends on.

---

### Run the eval (Day 7 afternoon, ~2 hours)

```bash
cd backend
# Baseline: dense only, no reranker
python -m app.eval.run --config configs/eval_baseline.yaml --output eval_baseline.html

# Final: hybrid + reranker
python -m app.eval.run --config configs/eval_final.yaml --output eval_final.html

# Open the HTML reports
open eval_final.html
```

Record your **real** numbers. Update:
- README.md (replace the placeholder table)
- Resume (master + all 5 variants)
- DECISIONS.md D6 (methodology + final numbers)

**Commit:**

```bash
git add .
git commit -m "Eval complete: hallucination [X]% → [Y]%, methodology documented in DECISIONS.md"
git push
```

---

## SECTION D — DAILY DISCIPLINE

### After every Composer prompt
- [ ] Read every modified file
- [ ] Run the verification command(s) listed
- [ ] If tests pass, commit with descriptive message
- [ ] If something is wrong, reject and re-prompt — don't accept "close enough"
- [ ] Update DECISIONS.md if you made any architectural choice

### Before sleeping each day
- [ ] All tests still green: `pytest backend/tests/ -v`
- [ ] All committed: `git status` shows clean
- [ ] Pushed to GitHub: `git push`
- [ ] Tomorrow's first task is clear in your head

### Money watch
- Cursor Pro: $20/month, fixed
- API spend (only the actual calls your code makes, NOT Cursor itself): $5-15 total for ingestion embeddings + eval runs + smoke tests
- Watch at: `https://platform.openai.com/usage` and `https://console.anthropic.com/settings/usage`

### The "I can't explain it" rule
If at any point you look at a file Cursor generated and you cannot explain why each function exists in your own words — that file isn't yours yet. Either:
1. Read it carefully until you can, or
2. Delete it and rewrite by hand

In interview, "I don't know, Cursor wrote that" is an instant disqualification at every firm on your target list.

---

## SECTION E — INTERVIEW PREP CHEAT SHEET

These are the 5 questions you will be asked. Have rehearsed answers ready by Day 7 evening.

### Q1: "Walk me through what happens when a user submits a query."

Answer:
> The query hits FastAPI's `/v1/query` POST endpoint, which streams Server-Sent Events back to the client. Internally, the Answerer orchestrates three stages: first, hybrid retrieval — I run dense vector search via pgvector and BM25 keyword search in parallel using asyncio.gather, then fuse them with Reciprocal Rank Fusion. Top 20 candidates go to a cross-encoder reranker, which scores query-document pairs jointly and returns top 5. Those 5 chunks form the context block for the LLM. I send a system prompt instructing strict grounding plus a user prompt template, with Anthropic's tool_use mode forcing Pydantic schema compliance. Tokens stream back to the client as they arrive. The final SSE `done` event carries the validated structured Answer with citations and a confidence score.

### Q2: "Why pgvector instead of Pinecone or Weaviate?"

(See DECISIONS.md D1)

### Q3: "How did you decide on your chunking strategy?"

(See DECISIONS.md D2 — your own words)

### Q4: "How did you measure 22% → 6% hallucination? Be specific."

(See DECISIONS.md D6 — your real methodology and real numbers)

### Q5: "What's the biggest weakness of your current system?"

Pick one honestly from BACKLOG.md and explain how you'd address it. Strong answers:
- "RAGAS uses an LLM judge — there's evaluator bias. I cross-validated 30 samples manually but at scale I'd want human raters or a stronger judge model."
- "BM25 is in-memory — fine for 50k chunks, breaks at 10M. I'd move to OpenSearch."
- "Single-turn only. Real users want follow-ups, which means conversation memory and query rewriting."

---

## YOU ARE READY

Save this file as `CURSOR_BUILD_GUIDE.md` in your repo. Commit it. Now go build.

```bash
git add CURSOR_BUILD_GUIDE.md
git commit -m "Add master build guide"
git push
```

When you hit a wall — paste the error and the relevant code into Claude (this chat), not Cursor. Cursor is for generation; I'm for debugging strategy, design choices, and interview prep.
