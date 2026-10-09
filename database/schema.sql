-- schema.sql: application schema, tables, constraints, and indexes.
-- Idempotent: safe to run multiple times.
CREATE SCHEMA IF NOT EXISTS itsm;

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
    csat_score          double precision CHECK (csat_score BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS idx_tickets_merchant_id       ON itsm.tickets (merchant_id);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned_agent_id ON itsm.tickets (assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_tickets_priority          ON itsm.tickets (priority);
CREATE INDEX IF NOT EXISTS idx_tickets_category          ON itsm.tickets (category);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at        ON itsm.tickets (created_at);
