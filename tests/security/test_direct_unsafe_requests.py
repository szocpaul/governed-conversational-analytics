"""T004: Direct unsafe structured-request tests (US2).

Unsafe requests are submitted DIRECTLY to the lower layers (bypassing the
model) to prove deterministic controls survive model failure (plan key
decision 2). Every prohibited request must be rejected with ZERO database
changes (FR-002, SC-001).
"""
from __future__ import annotations

import os

import psycopg
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.schemas import StructuredQueryRequest
from app.data.graphjin_client import GraphJinClient, GraphJinError
from app.security.errors import ValidationError
from app.security.validator import validate_request

GRAPHJIN_URL = os.environ.get(
    "GRAPHJIN_GRAPHQL_URL", "http://127.0.0.1:8081/api/v1/graphql")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))


def _snapshot():
    with psycopg.connect(
            host="127.0.0.1", port=POSTGRES_PORT, user=POSTGRES_USER,
            password=POSTGRES_PASSWORD, dbname=POSTGRES_DB,
            connect_timeout=5, autocommit=True) as c, c.cursor() as cur:
        out = {}
        for t in ("merchants", "agents", "tickets"):
            cur.execute(f"SELECT count(*) FROM itsm.{t}")
            out[t] = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'itsm'")
        out["tables"] = cur.fetchone()[0]
        return out


# ---------------- type-level rejection (pydantic allowlist) ----------------

def test_prohibited_entity_rejected_at_type_level():
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest(entity="pg_roles", operation="list",
                               fields=["rolname"])


def test_prohibited_field_rejected_at_type_level():
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest(entity="agents", operation="list",
                               fields=["agent_id", "password"])


def test_prohibited_operation_rejected_at_type_level():
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest(entity="tickets", operation="delete",
                               fields=["ticket_id"])


def test_excessive_limit_rejected_at_type_level():
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest(entity="tickets", operation="list",
                               fields=["ticket_id"], limit=100000)


# ---------------- deterministic validator re-check -------------------------

def _bypass_type_allowlist(**overrides):
    """Construct a request that pydantic accepted, then mutate it to an
    unsafe shape to prove the validator re-checks everything (defense in
    depth against a bypassed or confused type layer)."""
    req = StructuredQueryRequest(entity="tickets", operation="list",
                                 fields=["ticket_id"])
    for k, v in overrides.items():
        object.__setattr__(req, k, v)
    return req


def test_validator_rejects_unknown_entity():
    req = _bypass_type_allowlist(entity="pg_roles")
    with pytest.raises(ValidationError):
        validate_request(req)


def test_validator_rejects_prohibited_field():
    req = _bypass_type_allowlist(fields=["ticket_id", "secret"])
    with pytest.raises(ValidationError):
        validate_request(req)


def test_validator_rejects_write_operation():
    req = _bypass_type_allowlist(operation="delete")
    with pytest.raises(ValidationError):
        validate_request(req)


def test_validator_rejects_excessive_limit():
    req = _bypass_type_allowlist(limit=10**9)
    with pytest.raises(ValidationError):
        validate_request(req)


def test_validator_rejects_prohibited_filter_field():
    req = StructuredQueryRequest(entity="tickets", operation="list",
                                 fields=["ticket_id"])
    object.__setattr__(
        req, "filters",
        [type("F", (), {"field": "token", "op": "eq", "value": "x"})()])
    with pytest.raises(ValidationError):
        validate_request(req)


# ---------------- GraphJin layer: zero-effect proof ------------------------

@pytest.fixture(scope="module")
def client():
    c = GraphJinClient(GRAPHJIN_URL, timeout=15.0)
    try:
        c.ping()
    except GraphJinError as exc:
        pytest.skip(f"GraphJin not reachable: {exc}")
    return c


@pytest.mark.parametrize("mutation", [
    'mutation { insert_tickets(objects: [{ticket_id: 1, category: "x", priority: "P1"}]) { ticket_id } }',
    'mutation { update_tickets(set: {priority: "P9"}, where: {ticket_id: {eq: 847201}}) { ticket_id } }',
    'mutation { delete_tickets(where: {ticket_id: {eq: 847201}}) { ticket_id } }',
    'mutation { insert_merchants(objects: [{merchant_id: 1, merchant_name: "x", sector: "x", tier: "x", region: "x"}]) { merchant_id } }',
    'mutation { delete_agents { agent_id } }',
])
def test_graphjin_mutation_zero_effect(client, mutation):
    before = _snapshot()
    with pytest.raises(GraphJinError):
        client.execute_raw(mutation)
    assert _snapshot() == before, f"database changed after: {mutation}"


def test_graphjin_sql_smuggling_zero_effect(client):
    before = _snapshot()
    try:
        client.execute_raw(
            '{ tickets(where: { priority: { eq: "P1\'; DROP TABLE itsm.tickets; --" } }) '
            "{ ticket_id } }")
    except GraphJinError:
        pass
    assert _snapshot() == before
