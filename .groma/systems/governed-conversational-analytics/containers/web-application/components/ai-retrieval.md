---
type: C4 Component
title: Governed retrieval channel
status: stable
groma:
  id: ai-retrieval
  parent: web-application
  code:
    - scanner: python
      file: app/ai/retrieval.py
  group: Query pipeline
description: A governed, read-only, deterministic hybrid retrieval channel over the generated ticket text fields.
---

Connects as the itsm_readonly role and issues a fixed set of parameterized SQL statements (lexical ts_rank, semantic pgvector cosine, deterministic RRF k=60 fusion) built by code over an explicit allowlist of the three generated text fields. Not through GraphJin (whose semantic search is catalog-level, not row-level). Enforces the result limit (default 10, max 25), read-only role, and returns a sanitized trace. Also implements the governed hybrid COUNT query (feature 012): a true total (no LIMIT) with up to 5 example ticket_ids, using a calibrated semantic threshold from a versioned artifact.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [ai-retrieval](ai-retrieval.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Runs parameterized read-only SQL | psycopg (itsm_readonly role) |
