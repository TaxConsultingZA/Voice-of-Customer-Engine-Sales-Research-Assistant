-- Sales Research Assistant — Postgres schema bootstrap.
-- Run once against the staging / production database before first deploy:
--   psql $DATABASE_URL -f scripts/init-sales-schema.sql

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid()

-- ─────────────────────────────────────────────────────────────────────
-- sales_briefs: one row per generated brief. Doubles as the 7-day cache.
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sales_briefs (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name    TEXT            NOT NULL,
    ae_email        TEXT,
    generated_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    cached_until    TIMESTAMPTZ     NOT NULL,
    brief_payload   JSONB           NOT NULL,
    source_urls     TEXT[]          NOT NULL DEFAULT '{}',
    confidence      REAL            NOT NULL,
    ae_rating       SMALLINT        CHECK (ae_rating BETWEEN 1 AND 5),
    ae_feedback     TEXT
);

CREATE INDEX IF NOT EXISTS idx_briefs_company_cache
    ON sales_briefs (LOWER(company_name), cached_until DESC);

CREATE INDEX IF NOT EXISTS idx_briefs_generated_at
    ON sales_briefs (generated_at DESC);

-- ─────────────────────────────────────────────────────────────────────
-- case_study_chunks: pgvector RAG store for internal case study library.
-- Embedding dim = 384 matches sentence-transformers/all-MiniLM-L6-v2.
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS case_study_chunks (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         TEXT            NOT NULL,
    title           TEXT            NOT NULL,
    chunk_index     INT             NOT NULL,
    content         TEXT            NOT NULL,
    embedding       vector(384),
    industry_tags   TEXT[]          NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (case_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_case_chunks_embedding_hnsw
    ON case_study_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_case_chunks_case_id
    ON case_study_chunks (case_id);

CREATE INDEX IF NOT EXISTS idx_case_chunks_industry_tags
    ON case_study_chunks USING gin (industry_tags);
