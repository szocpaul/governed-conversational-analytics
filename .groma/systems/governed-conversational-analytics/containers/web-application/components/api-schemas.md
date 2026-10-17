---
type: C4 Component
title: Typed request & evidence schemas
status: stable
groma:
  id: api-schemas
  parent: web-application
  code:
    - scanner: python
      file: app/api/schemas.py
    - scanner: python
      file: app/api/__init__.py
  group: API & UI
description: Pydantic models that enforce the governed entity/field allowlist at the type boundary.
---

StructuredQueryRequest (entity, operation, fields, filters, aggregate, relationships, group_by, having, order_by, limit) with type-level allowlist validation. Evidence (rows, aggregate, row_count, groups_truncated, having_applied) for grounded answering. QueryResponse (status, answer, evidence, trace, latency_ms). RetrievalResult (ticket_ids, scores, trace) for the governed retrieval path. ENTITIES, RELATIONSHIPS, COLUMN_TYPES, and MAX_LIMIT mirror the GraphJin policy and database schema.
