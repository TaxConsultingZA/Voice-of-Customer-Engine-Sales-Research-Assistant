"""
Internal case study retriever (pgvector + sentence-transformers).

Responsibilities:
- Embed the input query (company description / industry hint) into a 384-dim
  vector using sentence-transformers/all-MiniLM-L6-v2.
- Run a HNSW cosine similarity query against `case_study_chunks`.
- Deduplicate by case_id (one best chunk per case) to keep results diverse.
- Return up to TOP_K case studies as CaseStudyChunk instances.

Why pgvector not Pinecone: we already run PostgreSQL for VoC. Adding a separate
vector DB would mean a second auth surface, second backup, second cost line.

Degrades silently to [] when:
- sentence-transformers is not installed
- DATABASE_URL is absent
- case_study_chunks table is empty or pgvector extension is missing
"""

from __future__ import annotations

import os

from .contracts import CaseStudyChunk

EMBEDDING_MODEL = os.getenv("SALES_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384
TOP_K = 3
MMR_LAMBDA = 0.5  # retained for future true-MMR upgrade


class CaseRetrieverError(Exception):
    """Raised when embedding or DB query fails non-gracefully."""


def _get_model():
    """Load and cache SentenceTransformer in-process. Returns None if unavailable."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        # Module-level singleton — first call is slow (~2s), subsequent calls are instant.
        if not hasattr(_get_model, "_model"):
            _get_model._model = SentenceTransformer(EMBEDDING_MODEL)
        return _get_model._model
    except Exception:
        return None


def embed_query(text: str) -> list[float] | None:
    """Return a 384-dim embedding for the input text, or None if unavailable."""
    model = _get_model()
    if model is None:
        return None
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def retrieve_case_studies(
    query: str,
    industry_hint: str | None = None,
    top_k: int = TOP_K,
) -> list[CaseStudyChunk]:
    """Return up to `top_k` diverse case study chunks ranked by semantic similarity.

    Deduplicates by case_id so the AE sees distinct cases, not multiple
    chunks from the same story.
    Returns [] gracefully when the DB, embeddings, or table are unavailable.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return []

    vec = embed_query(query)
    if vec is None:
        return []

    vec_literal = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
    fetch_k = top_k * 4  # over-fetch so dedup still yields top_k unique cases

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(db_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if industry_hint:
                    cur.execute(
                        """
                        SELECT case_id, title, chunk_index, content, industry_tags,
                               1 - (embedding <=> %s::vector) AS score
                        FROM case_study_chunks
                        WHERE %s = ANY(industry_tags)
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (vec_literal, industry_hint.lower(), vec_literal, fetch_k),
                    )
                else:
                    cur.execute(
                        """
                        SELECT case_id, title, chunk_index, content, industry_tags,
                               1 - (embedding <=> %s::vector) AS score
                        FROM case_study_chunks
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (vec_literal, vec_literal, fetch_k),
                    )
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        return []

    if not rows:
        return []

    # Deduplicate: keep the highest-scoring chunk per case_id.
    seen: dict[str, dict] = {}
    for row in rows:
        cid = row["case_id"]
        if cid not in seen or row["score"] > seen[cid]["score"]:
            seen[cid] = dict(row)

    deduped = sorted(seen.values(), key=lambda r: r["score"], reverse=True)[:top_k]

    return [
        CaseStudyChunk(
            case_id=r["case_id"],
            title=r["title"],
            chunk_index=r["chunk_index"],
            content=r["content"],
            industry_tags=list(r.get("industry_tags") or []),
        )
        for r in deduped
    ]
