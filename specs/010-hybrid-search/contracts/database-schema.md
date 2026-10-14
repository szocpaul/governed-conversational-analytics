# Contract: Database Schema Change (pgvector + full-text search)

**Files**: `compose.yml` (image pin), `database/schema.sql` (extension, columns,
indexes), `scripts/initialize_database.py` (idempotent setup),
`scripts/import_dataset.py` (atomic import).

## 1. Image pin (compose.yml)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16   # pinned; provides the vector extension (0.8.7)
```

Rationale: the stock `postgres:16.10-alpine` image has no `vector` extension
(verified: 61 available extensions, none `vector`). The pinned
`pgvector/pgvector:pg16` image provides it (verified: PostgreSQL 16.15,
pgvector 0.8.7). Applied through the clean reset path; no in-place migration.

## 2. Extension + columns + indexes (database/schema.sql)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE itsm.tickets
  ADD COLUMN IF NOT EXISTS embedding vector(768);   -- GENERATED (feature 010)

ALTER TABLE itsm.tickets
  ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      coalesce(short_description,'') || ' ' ||
      coalesce(description,'')       || ' ' ||
      coalesce(resolution_notes,''))
  ) STORED;                                          -- GENERATED (feature 010)

CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw
  ON itsm.tickets USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS tickets_fts_gin
  ON itsm.tickets USING gin (fts);
```

The same columns/indexes are also added to the CREATE TABLE definition for
fresh setups (same dual discipline as feature 009). All DDL is idempotent.

## 3. Read-only role (database/roles.sql) — unchanged grants, new coverage

The existing `itsm_readonly` role (SELECT only, statement_timeout 5s, writes
and DDL revoked) is the ONLY role the retrieval channel uses. The new
`embedding` and `fts` columns are covered by the existing
`GRANT SELECT ON ALL TABLES IN SCHEMA itsm` + default privileges; no new
grants are needed and no write/DDL privilege is granted.

## 4. Import (scripts/import_dataset.py)

Inside the SAME single transaction as the pinned-data import: load
`data/raw/tickets_embeddings.jsonl`, verify (a) SHA-256 ==
`embeddings-manifest.json` record, (b) coverage == pinned 2057, (c) every
vector dimension == 768; then upsert the `embedding` column per ticket
(`ON CONFLICT (ticket_id) DO UPDATE` of the embedding column only) and
re-check row counts. Any failure rolls back EVERYTHING. Idempotent on
re-run. The `fts` column is generated (never imported).

## Guarantees (verified by tests)

- The `vector` extension is present and its version recorded.
- All 2057 rows have a 768-dim embedding after import; the fts column and
  both indexes exist.
- Pinned columns (19 + 3 text) match the pinned raw data exactly.
- Writes through the read-only role remain rejected with zero database
  changes (existing security tests plus the new retrieval-security test).
