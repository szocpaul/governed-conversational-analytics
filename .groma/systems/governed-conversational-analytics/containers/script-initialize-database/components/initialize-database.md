---
type: C4 Component
title: Database initialization script
status: stable
groma:
  id: initialize-database
  parent: script-initialize-database
  code:
    - scanner: python
      file: scripts/initialize_database.py
  group: Database setup
description: Entry point for the idempotent database initialization.
---

scripts/initialize_database.py. Creates the database, schema, tables, indexes, and roles from the SQL files in database/. Idempotent.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [initialize-database](initialize-database.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Creates schema, tables, roles | psycopg (itsm_owner role) |
