---
type: C4 Component
title: Import dataset (script)
status: stable
groma:
  id: import-dataset
  parent: script-import-dataset
  code:
    - scanner: python
      file: scripts/import_dataset.py
  group: Database setup
description: Entry point for the atomic dataset import.
---

scripts/import_dataset.py. Imports the pinned CSVs, generated text columns, and embedding column into PostgreSQL in a single transaction. Verifies SHA-256 checksums. Idempotent.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [import-dataset](import-dataset.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Imports dataset atomically | psycopg (itsm_owner role) |
