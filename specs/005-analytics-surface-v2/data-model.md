# Phase 1 Data Model: Analytics Surface v2

**Date**: 2026-10-10 | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

No database schema changes. All changes are in the typed request/evidence
models (`app/api/schemas.py`) and their deterministic validation.

## Extended: StructuredQueryRequest

Existing fields unchanged. New optional fields:

| Field | Type | Default | Validation rules |
|-------|------|---------|------------------|
| `group_by` | `list[str]` | `[]` | Every element MUST be in the entity's allowlisted fields; max 3 grouping fields; only valid with `operation = "aggregate"` |
| `having` | `HavingFilter \| None` | `None` | Only valid when `group_by` is non-empty; `function` in {count, sum, avg, min, max}; `op` in {eq, ne, gt, gte, lt, lte}; `value` MUST be numeric; when `function != "count"`, `field` MUST be an allowlisted numeric column |
| `filters[].op` | + `is_null`, `is_not_null` | — | For these ops the filter `value` MUST be null/absent; field MUST be allowlisted |

New aggregate function:

| Function | Field requirement | Semantics |
|----------|-------------------|-----------|
| `ratio` | `field` REQUIRED, MUST be an allowlisted **boolean** column | count(rows where field is true) / count(all rows matching base filters); result in [0, 1]; null when the denominator is zero (empty base set) |

Type-level enforcement mirrors the existing pattern: pydantic models fail
fast at the type boundary; `validate_request` re-checks every rule
deterministically before any GraphJin call.

### Shape invariants (validator-enforced)

- `group_by` non-empty ⇒ `operation == "aggregate"` and `aggregate` present.
- `having` present ⇒ `group_by` non-empty.
- `ratio` aggregate ⇒ `group_by` may be present (ratio per group) or absent
  (global ratio); both valid.
- `is_null` / `is_not_null` filters carry no value; any non-null value with
  these ops is rejected.
- All existing invariants (limit 1..100, allowlisted fields/relationships,
  numeric-only avg/sum, orderable min/max) unchanged.

## Extended: Evidence

`Evidence.rows` already carries grouped result rows (each row = group field
values + aggregate values, e.g. `{"category": "Payments & Checkout",
"count_ticket_id": 483}`). Additions:

| Field | Type | Purpose |
|-------|------|---------|
| `aggregate.ratio` | float \| null | global ratio result in [0, 1] |
| `groups_truncated` | bool | true when the executed grouped query hit the result limit, so answers can state possible truncation |
| `having_applied` | object \| null | records the post-aggregation filter applied client-side (function, op, value, groups_dropped) for traceability |

## New evaluation case shapes

Evaluation cases (`evaluation/dev_cases.json`, `evaluation/cases.json`)
gain optional expectation keys, normalized by `evaluation/metrics.py`:

- `expected.request.group_by` / `expected.request.having` / filter ops
  `is_null` / `is_not_null` / aggregate `ratio` — request-shape matching.
- `expected.result.groups` — list of expected group rows (order-sensitive
  only when the question implies ranking); compared after normalization.
- `expected.result.ratio` — float compared with tolerance 0.001 (absolute).

Version fields of both sets are bumped; case IDs remain stable and unique;
held-out IDs are never consumed by optimization.

## Entities (unchanged)

`tickets`, `merchants`, `agents` with the existing allowlisted fields and
relationships; no new columns, no derived fields, no writes.
