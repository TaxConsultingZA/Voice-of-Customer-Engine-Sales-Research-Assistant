-- VoC Engine — application tables
-- Auto-run by postgres container on first start (runs after 01-init.sql).

CREATE TABLE IF NOT EXISTS uec_events (
    event_id             TEXT PRIMARY KEY,
    channel              TEXT NOT NULL,
    event_timestamp      TIMESTAMPTZ,
    taxonomy_path        TEXT,
    intent               TEXT,
    sentiment_polarity   DOUBLE PRECISION,
    sentiment_confidence DOUBLE PRECISION,
    customer_id          TEXT,
    customer_arr         DOUBLE PRECISION,
    raw_text_hash        TEXT,
    at_risk_flag         BOOLEAN NOT NULL DEFAULT FALSE,
    payload              JSONB NOT NULL,
    ingested_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_uec_events_timestamp ON uec_events (event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_uec_events_channel   ON uec_events (channel);
CREATE INDEX IF NOT EXISTS idx_uec_events_customer  ON uec_events (customer_id);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id      TEXT PRIMARY KEY,
    status           TEXT NOT NULL,
    escalation_tier  TEXT NOT NULL,
    crisis_score     DOUBLE PRECISION,
    customer_arr     DOUBLE PRECISION,
    watchlist_flag   BOOLEAN NOT NULL DEFAULT FALSE,
    approved_actions JSONB NOT NULL DEFAULT '[]',
    blocked_actions  JSONB NOT NULL DEFAULT '[]',
    created_at       TIMESTAMPTZ,
    resolved_at      TIMESTAMPTZ,
    resolved_by      TEXT,
    notes            TEXT NOT NULL DEFAULT '',
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_status  ON decisions (status);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions (created_at DESC);

CREATE TABLE IF NOT EXISTS watchlist (
    customer_id TEXT PRIMARY KEY,
    arr         DOUBLE PRECISION NOT NULL,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
