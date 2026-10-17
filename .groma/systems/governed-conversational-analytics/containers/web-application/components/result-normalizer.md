---
type: C4 Component
title: Result normalizer
status: stable
groma:
  id: result-normalizer
  parent: web-application
  code:
    - scanner: python
      file: app/data/result_normalizer.py
  group: Data access
description: Normalizes GraphJin results into a stable Evidence object for grounded answering.
---

Produces a JSON-serializable Evidence object. Aggregation results are flattened to {function_field: value} (count stays {count: value}); list results become a row list plus row_count. Grouped results normalize to per-group rows with a truncation flag. apply_having() applies the post-aggregation group filter as a pure function over already-executed group rows (no database access). Empty results stay empty — no data is invented.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/data/result_normalizer.py](../../../../../../app/data/result_normalizer.py) | [app/api/schemas.py](../../../../../../app/api/schemas.py) | Produces Evidence | Python (Pydantic) |
