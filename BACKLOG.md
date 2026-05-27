# Backlog — parked ideas (do NOT implement before submission)

Things that would be cool but are explicitly out of scope for the 5-7 day build. In interview, "what would you do next" answers come from here.

## Retrieval improvements
- HyDE (Hypothetical Document Embeddings)
- Query rewriting / multi-query retrieval
- A/B test different embedding models
- Tune alpha weight on hybrid scoring via dev-set tuning
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
