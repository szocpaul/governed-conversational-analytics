"""GraphQL builder tests for the v2 surface (spec 005, T003).

Every rendering expectation below was first verified live against the
running GraphJin 3.21.6 instance (research.md Decisions 1-3): grouped
summaries via distinct + aggregate columns, is_null/is_not_null filters,
ratio via avg(expr: {case: ...}), and ratio per group.
"""
from __future__ import annotations

from app.api.schemas import StructuredQueryRequest
from app.data.graphjin_client import build_graphql


def _req(**over):
    base = dict(entity="tickets", operation="aggregate",
                aggregate={"function": "count", "field": None})
    base.update(over)
    return StructuredQueryRequest.model_validate(base)


# ---------------------------------------------------------------------------
# Grouped aggregation (distinct + aggregate columns)
# ---------------------------------------------------------------------------

def test_grouped_count_uses_distinct_and_count_column():
    q = build_graphql(_req(group_by=["category"]))
    assert "distinct: [category]" in q
    assert "count_ticket_id" in q
    assert q.startswith("{ tickets(")
    assert "tickets_aggregate" not in q


def test_grouped_order_by_count_maps_to_aggregate_column():
    q = build_graphql(_req(group_by=["category"], order_by="count",
                           order_dir="desc"))
    assert "order_by: {count_ticket_id: desc}" in q


def test_grouped_order_by_aggregate_column_name():
    q = build_graphql(_req(group_by=["category"],
                           order_by="count_ticket_id", order_dir="desc"))
    assert "order_by: {count_ticket_id: desc}" in q


def test_grouped_order_by_grouping_field():
    q = build_graphql(_req(group_by=["category"], order_by="category",
                           order_dir="asc"))
    assert "order_by: {category: asc}" in q


def test_grouped_multi_field():
    q = build_graphql(_req(group_by=["category", "priority"]))
    assert "distinct: [category, priority]" in q
    assert "category priority count_ticket_id" in q


def test_grouped_with_filters():
    q = build_graphql(_req(
        group_by=["category"],
        filters=[{"field": "priority", "op": "in", "value": ["P1", "P2"]},
                 {"field": "created_at", "op": "gte", "value": "2026-01-01"}]))
    assert 'where: {priority: {in: ["P1", "P2"]}, created_at: {gte: "2026-01-01"}}' in q
    assert "distinct: [category]" in q


def test_grouped_limit_applied():
    q = build_graphql(_req(group_by=["category"], limit=50))
    assert "limit: 50" in q


def test_grouped_avg_aggregate_column():
    q = build_graphql(_req(group_by=["category"],
                           aggregate={"function": "avg",
                                      "field": "resolution_hours"}))
    assert "avg_resolution_hours" in q
    assert "distinct: [category]" in q


def test_grouped_having_not_in_graphql():
    # GraphJin v3 has no HAVING (research.md Decision 4): the post-filter is
    # applied client-side, so the GraphQL must NOT contain a having clause.
    q = build_graphql(_req(
        group_by=["merchant_id"],
        having={"function": "count", "field": None, "op": "gt",
                "value": 50}))
    assert "having" not in q


# ---------------------------------------------------------------------------
# is_null / is_not_null filters
# ---------------------------------------------------------------------------

def test_is_null_filter_rendering():
    q = build_graphql(_req(
        group_by=[],
        filters=[{"field": "assigned_agent_id", "op": "is_null",
                  "value": None}]))
    assert "assigned_agent_id: {is_null: true}" in q


def test_is_not_null_filter_rendering():
    q = build_graphql(StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="list", fields=["ticket_id"],
        filters=[{"field": "closed_at", "op": "is_not_null"}],
        order_by="created_at", order_dir="asc", limit=5)))
    assert "closed_at: {is_null: false}" in q
    assert "order_by: {created_at: asc}" in q
    assert "limit: 5" in q


def test_is_null_combined_with_other_filters():
    q = build_graphql(_req(
        group_by=[],
        filters=[{"field": "priority", "op": "eq", "value": "P1"},
                 {"field": "assigned_agent_id", "op": "is_null",
                  "value": None}]))
    assert 'priority: {eq: "P1"}' in q
    assert "assigned_agent_id: {is_null: true}" in q


# ---------------------------------------------------------------------------
# ratio aggregate (expression aggregate)
# ---------------------------------------------------------------------------

def test_ratio_global_rendering():
    q = build_graphql(_req(
        group_by=[],
        aggregate={"function": "ratio", "field": "resolution_breached"}))
    assert "ratio_resolution_breached: avg(expr:" in q
    assert ("case: {arms: [{when: {resolution_breached: {eq: true}}, "
            "then: 1.0}], else: 0.0}") in q
    # Global ratio is a plain aggregate query, not a grouped one.
    assert "distinct" not in q


def test_ratio_with_base_filters():
    q = build_graphql(_req(
        group_by=[],
        aggregate={"function": "ratio", "field": "resolution_breached"},
        filters=[{"field": "priority", "op": "eq", "value": "P1"}]))
    assert 'where: {priority: {eq: "P1"}}' in q
    assert "avg(expr:" in q


def test_ratio_per_group_rendering():
    q = build_graphql(_req(
        group_by=["category"],
        aggregate={"function": "ratio", "field": "resolution_breached"}))
    assert "distinct: [category]" in q
    assert "ratio_resolution_breached: avg(expr:" in q
    assert "category" in q


# ---------------------------------------------------------------------------
# Existing shapes unchanged
# ---------------------------------------------------------------------------

def test_plain_count_unchanged():
    q = build_graphql(_req())
    assert q == "{ tickets_aggregate { aggregate { count } } }"


def test_plain_list_unchanged():
    q = build_graphql(StructuredQueryRequest.model_validate(dict(
        entity="tickets", operation="list", fields=["ticket_id"],
        limit=3)))
    assert q == "{ tickets(limit: 3) { ticket_id } }"
