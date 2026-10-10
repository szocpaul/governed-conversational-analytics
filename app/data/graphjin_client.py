"""GraphJin governed GraphQL client (T005).

Builds a GraphQL query from a validated StructuredQueryRequest and executes it
against the governed GraphJin surface. This is the ONLY database access path
for the runtime query flow; no arbitrary SQL is ever constructed or sent.
"""
from __future__ import annotations

import json

import httpx

from app.api.schemas import StructuredQueryRequest


class GraphJinError(RuntimeError):
    """Raised when GraphJin execution fails or returns errors."""


def _gql_literal(value: object) -> str:
    """Render a Python value as a GraphQL literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_gql_literal(v) for v in value) + "]"
    # string
    return json.dumps(str(value))


def _build_where(req: StructuredQueryRequest) -> str:
    if not req.filters:
        return ""
    parts = []
    for flt in req.filters:
        if flt.op in ("is_null", "is_not_null"):
            # GraphJin v3 null filtering (research.md Decision 2).
            val = "true" if flt.op == "is_null" else "false"
            parts.append(f"{flt.field}: {{is_null: {val}}}")
        else:
            parts.append(
                f"{flt.field}: {{{flt.op}: {_gql_literal(flt.value)}}}")
    return "where: {" + ", ".join(parts) + "}"


# Primary-key column per entity; GraphJin names grouped count columns
# count_<pk> (verified live, research.md Decision 1).
_PK = {"tickets": "ticket_id", "merchants": "merchant_id",
       "agents": "agent_id"}


def _agg_column(req: StructuredQueryRequest) -> str:
    """Return the GraphJin aggregate column name for a grouped request."""
    fn = req.aggregate.function
    if fn == "count":
        return f"count_{_PK[req.entity]}"
    if fn == "ratio":
        # Aliased expression aggregate (research.md Decision 3).
        return f"ratio_{req.aggregate.field}"
    return f"{fn}_{req.aggregate.field}"


def _ratio_expr(field: str) -> str:
    """Render the verified avg(case) expression aggregate for a ratio."""
    return (
        "avg(expr: {case: {arms: [{when: {"
        f"{field}: {{eq: true}}"
        "}, then: 1.0}], else: 0.0}})"
    )


def build_graphql(req: StructuredQueryRequest) -> str:
    """Build a governed GraphQL query string from a typed request."""
    args = []
    where = _build_where(req)
    if where:
        args.append(where)

    if req.operation == "aggregate":
        fn = req.aggregate.function

        # Grouped aggregation (spec 005): GraphJin grouped-summary form via
        # distinct + aggregate columns (research.md Decision 1). HAVING is
        # NOT rendered here — GraphJin v3 has no native HAVING; the
        # post-aggregation filter is applied client-side (Decision 4).
        if req.group_by:
            distinct = "distinct: [" + ", ".join(req.group_by) + "]"
            args.append(distinct)
            if req.order_by:
                order_col = req.order_by
                if order_col not in req.group_by:
                    # "count" / "<fn>_<field>" map to the aggregate column.
                    order_col = _agg_column(req)
                args.append(
                    f"order_by: {{{order_col}: {req.order_dir}}}")
            args.append(f"limit: {req.limit}")
            if fn == "ratio":
                agg_sel = f"{_agg_column(req)}: {_ratio_expr(req.aggregate.field)}"
            elif fn == "count":
                agg_sel = _agg_column(req)
            else:
                agg_sel = f"{fn}_{req.aggregate.field}"
            arg_str = f"({', '.join(args)})" if args else ""
            return (
                f"{{ {req.entity}{arg_str} "
                f"{{ {' '.join(req.group_by)} {agg_sel} }} }}"
            )

        if fn == "count":
            agg_body = "count"
        elif fn == "ratio":
            # Global ratio: aliased expression aggregate on the plain
            # entity field set (verified live, research.md Decision 3).
            agg_body = None
        else:
            agg_body = f"{fn} {{ {req.aggregate.field} }}"
        arg_str = f"({', '.join(args)})" if args else ""
        if fn == "ratio":
            return (
                f"{{ {req.entity}{arg_str} "
                f"{{ {_agg_column(req)}: {_ratio_expr(req.aggregate.field)} }} }}"
            )
        return (
            f"{{ {req.entity}_aggregate{arg_str} "
            f"{{ aggregate {{ {agg_body} }} }} }}"
        )

    # list operation
    if req.order_by:
        args.append(f"order_by: {{{req.order_by}: {req.order_dir}}}")
    args.append(f"limit: {req.limit}")
    fields = list(req.fields)
    for rel in req.relationships:
        # include the related entity's readable fields minimally
        if rel == "merchants":
            fields.append("merchants { merchant_id merchant_name sector tier region }")
        elif rel == "agents":
            fields.append("agents { agent_id agent_name tier primary_category shift_region efficiency_multiplier }")
        elif rel == "tickets":
            fields.append("tickets { ticket_id category priority }")
    if not fields:
        # default to primary key if no fields requested
        pk = {"tickets": "ticket_id", "merchants": "merchant_id",
              "agents": "agent_id"}[req.entity]
        fields = [pk]
    arg_str = f"({', '.join(args)})" if args else ""
    return f"{{ {req.entity}{arg_str} {{ {' '.join(fields)} }} }}"


class GraphJinClient:
    """Minimal governed GraphQL executor for the GraphJin surface."""

    def __init__(self, url: str, timeout: float = 30.0):
        self.url = url
        self.timeout = timeout

    def ping(self) -> bool:
        raw = self.execute_raw("{ merchants(limit: 1) { merchant_id } }")
        return "data" in raw

    def execute_raw(self, query: str) -> dict:
        """Execute a raw GraphQL string. Mutations are rejected upstream."""
        try:
            resp = httpx.post(
                self.url, json={"query": query}, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise GraphJinError(f"GraphJin request failed: {exc}") from exc
        payload = resp.json()
        if "errors" in payload and payload["errors"]:
            raise GraphJinError(f"GraphJin errors: {payload['errors']}")
        return payload

    def execute(self, req: StructuredQueryRequest) -> dict:
        """Build and execute a governed query for a typed request."""
        return self.execute_raw(build_graphql(req))
