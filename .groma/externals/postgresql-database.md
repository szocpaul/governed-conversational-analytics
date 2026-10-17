---
type: C4 System
title: PostgreSQL database
status: stable
groma:
  id: postgresql-database
  technology: PostgreSQL 16 (pgvector/pgvector:pg16)
---

The pinned ITSM data store. Holds the tickets, merchants, and agents tables with the generated text columns, a pgvector embedding column, and an fts tsvector column. Access is through two roles: itsm_owner (setup/import) and itsm_readonly (SELECT-only, statement_timeout 5s). The governed retrieval channel and the evaluation security snapshot connect directly as their respective roles.
