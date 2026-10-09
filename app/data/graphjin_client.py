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
        parts.append(f"{flt.field}: {{{flt.op}: {_gql_literal(flt.value)}}}")
    return "where: {" + ", ".join(parts) + "}"


def build_graphql(req: StructuredQueryRequest) -> str:
    """Build a governed GraphQL query string from a typed request."""
    args = []
    where = _build_where(req)
    if where:
        args.append(where)

    if req.operation == "aggregate":
        fn = req.aggregate.function
        if fn == "count":
            agg_body = "count"
        else:
            agg_body = f"{fn} {{ {req.aggregate.field} }}"
        arg_str = f"({', '.join(args)})" if args else ""
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
