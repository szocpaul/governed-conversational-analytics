"""Normalize GraphJin results into Evidence for grounded answering (T005).

Produces a stable, JSON-serializable Evidence object. Aggregation results are
flattened to {function_field: value} (count stays {count: value}). List
results become a row list plus row_count. No data is invented here: empty
results stay empty.

spec 005: grouped results normalize to per-group rows with a truncation
flag, and the having post-aggregation filter is applied here as a pure
function over already-executed group rows (research.md Decision 4 — GraphJin
v3 has no native HAVING). The filter never touches the database.
"""
from __future__ import annotations

import operator

from app.api.schemas import Evidence, HavingApplied, StructuredQueryRequest

_HAVING_OPS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
}


def apply_having(evidence: Evidence, req: StructuredQueryRequest) -> Evidence:
    """Apply the post-aggregation group filter to executed group rows.

    Pure function: no I/O, no database access. Drops groups whose aggregate
    value fails the having comparison and records the filter in evidence.
    """
    having = req.having
    if having is None:
        return evidence
    if having.function == "count":
        pk = {"tickets": "ticket_id", "merchants": "merchant_id",
              "agents": "agent_id"}[req.entity]
        agg_col = f"count_{pk}"
    else:
        agg_col = f"{having.function}_{having.field}"
    cmp = _HAVING_OPS[having.op]
    kept: list[dict] = []
    dropped = 0
    for row in evidence.rows:
        value = row.get(agg_col)
        if value is None or not cmp(value, having.value):
            dropped += 1
        else:
            kept.append(row)
    return evidence.model_copy(update={
        "rows": kept,
        "row_count": len(kept),
        "having_applied": HavingApplied(
            function=having.function, field=having.field, op=having.op,
            value=having.value, groups_dropped=dropped),
    })


def normalize_result(req: StructuredQueryRequest, raw: dict) -> Evidence:
    data = raw.get("data") or {}

    if req.operation == "aggregate" and req.group_by:
        # Grouped aggregation (spec 005): GraphJin returns one row per group
        # under the plain entity field, each carrying the grouping fields
        # plus the aggregate column (or aliased ratio expression).
        rows = data.get(req.entity) or []
        clean_rows = [dict(r) for r in rows]
        # The governed limit applies to groups; a full page means the
        # breakdown may be truncated (spec edge case: answers must be able
        # to say so).
        truncated = len(clean_rows) >= req.limit
        return Evidence(rows=clean_rows, aggregate=None,
                        row_count=len(clean_rows), groups_truncated=truncated)

    if req.operation == "aggregate":
        fn = req.aggregate.function
        if fn == "ratio":
            # Global ratio: aliased expression aggregate returned as a
            # single row under the plain entity field (research.md D3).
            rows = data.get(req.entity) or []
            value = None
            if rows:
                value = rows[0].get(f"ratio_{req.aggregate.field}")
            return Evidence(rows=[], aggregate={f"ratio_{req.aggregate.field}": value},
                            row_count=0)
        node = data.get(f"{req.entity}_aggregate") or {}
        agg = (node.get("aggregate") or {})
        flat: dict = {}
        if fn == "count":
            flat["count"] = agg.get("count")
        else:
            inner = agg.get(fn) or {}
            flat[f"{fn}_{req.aggregate.field}"] = inner.get(req.aggregate.field)
        return Evidence(rows=[], aggregate=flat, row_count=0)

    rows = data.get(req.entity) or []
    # Ensure plain dicts and JSON-safe values.
    clean_rows = [dict(r) for r in rows]
    return Evidence(rows=clean_rows, aggregate=None, row_count=len(clean_rows))
