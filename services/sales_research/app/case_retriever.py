"""
Internal case study retriever (pgvector + sentence-transformers).

Responsibilities:
- Embed the input query (company description / industry hint) into a 384-dim
  vector using sentence-transformers/all-MiniLM-L6-v2.
- Run a HNSW cosine similarity query against `case_study_chunks`.
- Apply MMR (Maximum Marginal Relevance) to diversify results — without MMR
  the top 3 are usually three chunks of the same case.
- Return up to TOP_K case studies as CaseStudyChunk instances.

Why pgvector not Pinecone: we already run PostgreSQL for VoC. Adding a separate
vector DB would mean a second auth surface, second backup, second cost line.

TODO (Wei, Task 2):
- Implement `embed_query()` (cache the model in-process — first load is slow).
- Implement `retrieve_case_studies()` against `case_study_chunks` table.
- Implement MMR reranking on top-K * 3 candidates.
- Ingestion-side script `scripts/ingest_case_studies.py` (separate file) loads
  PDFs through pypdf, chunks, embeds, inserts.
"""

from __future__ import annotations

import os

from .contracts import CaseStudyChunk

EMBEDDING_MODEL = os.getenv("SALES_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384
TOP_K = 3
MMR_LAMBDA = 0.5  # 1.0 = pure relevance, 0.0 = pure diversity


class CaseRetrieverError(Exception):
    """Raised when embedding or DB query fails."""


def embed_query(text: str) -> list[float]:
    """Return a 384-dim embedding for the input text. Model cached in-process."""
    raise NotImplementedError(
        "embed_query() is a Task 2 deliverable — load all-MiniLM-L6-v2 and infer."
    )


def retrieve_case_studies(
    query: str,
    industry_hint: str | None = None,
    top_k: int = TOP_K,
) -> list[CaseStudyChunk]:
    """Return up to `top_k` case study chunks ranked by semantic similarity.

    Filters by `industry_tags` when `industry_hint` is provided to keep the
    embedding search scoped (banking queries should not pull retail case
    studies even if the embedding distance is small).
    """
    raise NotImplementedError(
        "retrieve_case_studies() is a Task 2 deliverable — pgvector HNSW + MMR rerank."
    )
