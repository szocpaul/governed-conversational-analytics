-- schema.sql: application schema, tables, constraints, and indexes.
-- Idempotent: safe to run multiple times.
CREATE SCHEMA IF NOT EXISTS itsm;

-- GENERATED (feature 010): the vector extension is provided by the pinned
-- pgvector/pgvector:pg16 image (pgvector 0.8.7); required for the embedding
-- column and HNSW index below.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS itsm.merchants (
    merchant_id   integer      PRIMARY KEY,
    merchant_name text         NOT NULL,
    sector        text         NOT NULL,
    tier          text         NOT NULL,
    region        text         NOT NULL
);

CREATE TABLE IF NOT EXISTS itsm.agents (
    agent_id              integer       PRIMARY KEY,
    agent_name            text          NOT NULL,
    tier                  text          NOT NULL,
    primary_category      text          NOT NULL,
    shift_region          text          NOT NULL,
    efficiency_multiplier numeric(6, 3) NOT NULL
);

CREATE TABLE IF NOT EXISTS itsm.tickets (
    ticket_id           integer     PRIMARY KEY,
    merchant_id         integer     NOT NULL REFERENCES itsm.merchants (merchant_id),
    category            text        NOT NULL,
    sub_category        text        NOT NULL,
    priority            text        NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    created_at          timestamptz NOT NULL,
    is_legacy           boolean     NOT NULL,
    assigned_agent_id   integer     REFERENCES itsm.agents (agent_id),
    category_mismatch   boolean,
    first_response_at   timestamptz,
    closed_at           timestamptz,
    ttfr_hours          double precision,
    resolution_hours    double precision,
    response_breached   boolean,
    resolution_breached boolean,
    is_reopened         boolean     NOT NULL,
    is_reopen_child     boolean     NOT NULL,
    is_incident_ticket  boolean     NOT NULL,
    csat_score          double precision CHECK (csat_score BETWEEN 0 AND 1),
    -- GENERATED (feature 009, synthetic text from pinned artifact data/raw/tickets_texts.jsonl)
    short_description   text,
    -- GENERATED (feature 009, synthetic text from pinned artifact data/raw/tickets_texts.jsonl)
    description         text,
    -- GENERATED (feature 009, synthetic text from pinned artifact data/raw/tickets_texts.jsonl)
    resolution_notes    text,
    -- GENERATED (feature 010, embedding from pinned artifact data/raw/tickets_embeddings.jsonl)
    embedding           vector(768),
    -- GENERATED (feature 010, full-text search over the three generated text fields)
    fts                 tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
          coalesce(short_description, '') || ' ' ||
          coalesce(description, '')       || ' ' ||
          coalesce(resolution_notes, ''))
    ) STORED
);

-- GENERATED (feature 009): idempotent column adds for databases initialized
-- before the generated columns existed. Fresh setups get them from the CREATE
-- TABLE above; these keep existing databases convergent without a reset.
ALTER TABLE itsm.tickets ADD COLUMN IF NOT EXISTS short_description text;
ALTER TABLE itsm.tickets ADD COLUMN IF NOT EXISTS description text;
ALTER TABLE itsm.tickets ADD COLUMN IF NOT EXISTS resolution_notes text;

-- GENERATED (feature 010): idempotent column adds for databases initialized
-- before the embedding/fts columns existed (same dual discipline as 009).
ALTER TABLE itsm.tickets ADD COLUMN IF NOT EXISTS embedding vector(768);
ALTER TABLE itsm.tickets ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
          coalesce(short_description, '') || ' ' ||
          coalesce(description, '')       || ' ' ||
          coalesce(resolution_notes, ''))
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_tickets_merchant_id       ON itsm.tickets (merchant_id);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned_agent_id ON itsm.tickets (assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_tickets_priority          ON itsm.tickets (priority);
CREATE INDEX IF NOT EXISTS idx_tickets_category          ON itsm.tickets (category);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at        ON itsm.tickets (created_at);

-- GENERATED (feature 010): HNSW index on the embedding (cosine operator
-- class) and a GIN index on the generated fts column.
CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw
    ON itsm.tickets USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS tickets_fts_gin
    ON itsm.tickets USING gin (fts);
