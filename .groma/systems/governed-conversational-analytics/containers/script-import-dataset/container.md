---
type: C4 Container
title: Import dataset
status: stable
groma:
  id: script-import-dataset
  parent: governed-conversational-analytics
description: Atomic import of the pinned ITSM dataset, text fields, and embeddings into PostgreSQL.
---

Imports the pinned CSVs (merchants, agents, tickets), the generated text columns, and the embedding column into the itsm schema in a single transaction. The raw source files are immutable; the import is atomic (all-or-nothing). Verifies SHA-256 checksums against the import manifest. Idempotent: re-running produces the same database state.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [script-import-dataset](container.md) | [postgresql-database](../../../../externals/postgresql-database.md) | Imports the dataset atomically | psycopg (itsm_owner role) |
