---
type: C4 Container
title: Initialize database
status: stable
groma:
  id: script-initialize-database
  parent: governed-conversational-analytics
description: Idempotent creation of the database schema, tables, indexes, and roles.
---

Creates the itsm database, schema, tables (tickets, merchants, agents), indexes (including HNSW and GIN for the embedding and fts columns), the itsm_owner role, and the itsm_readonly role (SELECT-only, statement_timeout 5s). Idempotent: safe to re-run. Runs via the PostgreSQL Docker service in compose.yml.
