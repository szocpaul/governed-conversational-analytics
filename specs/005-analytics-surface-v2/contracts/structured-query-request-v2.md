# Contract: Structured Query Request v2

**Feature**: 005-analytics-surface-v2 | **Date**: 2026-10-10

The typed request contract between the DSPy planner, the deterministic
validator, and the governed GraphJin execution path. JSON shape emitted by
the planner and consumed by `StructuredQueryRequest.model_validate`.

## Base shape (unchanged)

```json
{
  "entity": "tickets",
  "operation": "list | aggregate",
  "fields": ["ticket_id", "category"],
  "filters": [{"field": "priority", "op": "eq", "value": "P1"}],
  "aggregate": {"function": "count", "field": null},
  "relationships": ["merchants"],
  "order_by": "created_at",
  "order_dir": "asc",
  "limit": 100
}
```

## New: grouped aggregation

```json
{
  "entity": "tickets",
  "operation": "aggregate",
  "aggregate": {"function": "count", "field": null},
  "group_by": ["category"],
  "filters": [{"field": "created_at", "op": "gte", "value": "2026-01-01"}],
  "order_by": "count",
  "order_dir": "desc",
  "limit": 100
}
```

- `group_by`: 1-3 allowlisted fields of the entity.
- `order_by` on a grouped request may name a grouping field or the string
  `"count"` / `"<function>_<field>"` (the aggregate column); the builder
  maps it to the GraphJin aggregate column name.
- Result: one row per group with grouping fields plus the aggregate column.

## New: having (post-aggregation group filter)

```json
{
  "group_by": ["merchant_id"],
  "aggregate": {"function": "count", "field": null},
  "having": {"function": "count", "field": null, "op": "gt", "value": 50}
}
```

- Only valid with non-empty `group_by`.
- `function` ∈ {count, sum, avg, min, max}; `op` ∈ {eq, ne, gt, gte, lt, lte};
  `value` numeric.
- Applied deterministically client-side over executed groups (GraphJin v3
  has no native HAVING; see research.md Decision 4). Recorded in evidence
  as `having_applied`.

## New: missing-value filters

```json
{"filters": [{"field": "assigned_agent_id", "op": "is_null", "value": null}]}
{"filters": [{"field": "closed_at", "op": "is_not_null", "value": null}]}
```

- `value` MUST be null (or omitted) for these ops.
- "Open tickets" = `closed_at` `is_null`; "closed" = `is_not_null`.

## New: ratio aggregate

```json
{
  "entity": "tickets",
  "operation": "aggregate",
  "aggregate": {"function": "ratio", "field": "resolution_breached"},
  "filters": [],
  "limit": 100
}
```

- `field` REQUIRED and MUST be an allowlisted boolean column.
- Global ratio: no `group_by` → single value in [0, 1] (null when the base
  set is empty).
- Ratio per group: with `group_by` → one ratio value per group row.
- Answers format ratios as percentages (e.g. 50.4%) with the underlying
  counts traceable in evidence.

## Rejection contract (unchanged principle, extended coverage)

The validator rejects deterministically, before any database access:

- any field/op/function outside the allowlists (including via the new
  shapes, e.g. `group_by` on a non-allowlisted field, `ratio` on a
  non-boolean field, `having` with a string threshold);
- any write-shaped request (mutations remain impossible end-to-end);
- malformed new shapes (`having` without `group_by`, value on `is_null`,
  `group_by` on `list` operation).

Rejections map to the stable `unsupported` / `clarification` categories;
zero database effect.
