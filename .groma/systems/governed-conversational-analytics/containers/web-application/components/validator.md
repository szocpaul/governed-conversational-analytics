---
type: C4 Component
title: Deterministic request validator
status: stable
groma:
  id: validator
  parent: web-application
  code:
    - scanner: python
      file: app/security/validator.py
    - scanner: python
      file: app/security/__init__.py
  group: Security controls
description: Re-checks every governed constraint on a StructuredQueryRequest before any GraphJin execution.
---

A pure function with no LLM and no I/O: the same input always produces the same decision. Validates entity, operation, fields, filters (with type compatibility), relationships, limit, aggregate (function, field, numeric requirement for avg/sum, boolean requirement for ratio), group_by (1-3 fields, aggregate-only), and having (post-aggregation group filter, numeric value, numeric field for non-count). Rejects type-incompatible filter values and aggregates before any GraphJin call, turning them into the stable "unsupported" category with zero governed calls.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/security/validator.py](../../../../../../app/security/validator.py) | [app/api/schemas.py](../../../../../../app/api/schemas.py) | Validates against allowlist | Python (Pydantic) |
