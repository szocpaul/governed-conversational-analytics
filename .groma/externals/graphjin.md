---
type: C4 System
title: GraphJin
status: stable
groma:
  id: graphjin
  technology: GraphJin v3 (pinned Docker image)
---

The governed GraphQL access boundary. A policy-controlled, read-only surface over PostgreSQL with default_block: true, explicit entity/field/operation allowlists, and a hard row-limit cap. The runtime structured-query path executes only through GraphJin; no arbitrary SQL is ever constructed or sent.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [graphjin](graphjin.md) | [postgresql-database](postgresql-database.md) | Executes read-only queries | SQL (itsm_readonly role) |
