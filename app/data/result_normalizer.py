"""Normalize GraphJin results into Evidence for grounded answering (T005).

Produces a stable, JSON-serializable Evidence object. Aggregation results are
flattened to {function_field: value} (count stays {count: value}). List
results become a row list plus row_count. No data is invented here: empty
results stay empty.
"""
from __future__ import annotations

from app.api.schemas import Evidence, StructuredQueryRequest


def normalize_result(req: StructuredQueryRequest, raw: dict) -> Evidence:
    data = raw.get("data") or {}

    if req.operation == "aggregate":
        node = data.get(f"{req.entity}_aggregate") or {}
        agg = (node.get("aggregate") or {})
        flat: dict = {}
        fn = req.aggregate.function
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
