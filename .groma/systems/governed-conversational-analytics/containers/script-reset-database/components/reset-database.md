---
type: C4 Component
title: Database reset script
status: stable
groma:
  id: reset-database
  parent: script-reset-database
  code:
    - scanner: python
      file: scripts/reset_database.py
      symbol: main
  group: Database setup
description: Entry point for the clean local database reset.
---

scripts/reset_database.py. Drops and recreates the database from the SQL files in database/. Does not touch the immutable raw source files.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [reset-database](reset-database.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Drops and recreates database | psycopg (itsm_owner role) |
