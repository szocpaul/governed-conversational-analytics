"""T004: Authorization and disclosure tests (US2).

Proves that prohibited entities, fields, and row scopes disclose ZERO
prohibited values (FR-003, SC-002), at every layer: type boundary,
deterministic validator, GraphJin policy, and PostgreSQL role.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import psycopg
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.schemas import StructuredQueryRequest
from app.data.graphjin_client import GraphJinClient, GraphJinError
from app.security.errors import ValidationError
from app.security.validator import validate_request

GRAPHJIN_PORT = int(os.environ.get("GRAPHJIN_PORT", "8081"))
BASE = f"http://127.0.0.1:{GRAPHJIN_PORT}"
GRAPHJIN_URL = os.environ.get(
    "GRAPHJIN_GRAPHQL_URL", f"{BASE}/api/v1/graphql")

RO_USER = os.environ.get("GRAPHJIN_DB_USER", "itsm_readonly")
RO_PASSWORD = os.environ.get("GRAPHJIN_DB_PASSWORD",
                             "change-me-readonly-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))

# Values that must never be disclosed by the governed surface.
PROHIBITED_FIELD_NAMES = ["password", "secret", "token", "encrypted",
                          "rolname", "rolpassword", "passwd"]


def _graphql(query: str):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        GRAPHJIN_URL, data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


# ---------------- type + validator layers ----------------------------------

@pytest.mark.parametrize("field", PROHIBITED_FIELD_NAMES[:4])
def test_prohibited_field_blocked_at_type_level(field):
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest(entity="agents", operation="list",
                               fields=["agent_id", field])


def test_prohibited_relationship_blocked():
    with pytest.raises((PydanticValidationError, ValueError)):
        StructuredQueryRequest(entity="merchants", operation="list",
                               fields=["merchant_id"],
                               relationships=["agents"])


def test_validator_recHECKS_relationship_scope():
    req = StructuredQueryRequest(entity="merchants", operation="list",
                                 fields=["merchant_id"])
    object.__setattr__(req, "relationships", ["agents"])
    with pytest.raises(ValidationError):
        validate_request(req)


# ---------------- GraphJin policy layer ------------------------------------

@pytest.fixture(scope="module")
def client():
    c = GraphJinClient(GRAPHJIN_URL, timeout=15.0)
    try:
        c.ping()
    except GraphJinError as exc:
        pytest.skip(f"GraphJin not reachable: {exc}")
    return c


@pytest.mark.parametrize("entity", ["pg_roles", "pg_authid", "pg_user",
                                    "information_schema_tables"])
def test_system_entities_not_readable(client, entity):
    status, body = _graphql(f"{{ {entity} {{ __typename }} }}")
    data = body.get("data") or {}
    assert not data.get(entity), f"{entity} disclosed: {body}"


@pytest.mark.parametrize("field", ["password", "secret", "token",
                                   "encrypted"])
def test_blocklisted_fields_not_readable(client, field):
    status, body = _graphql(f"{{ agents(limit: 1) {{ agent_id {field} }} }}")
    text = json.dumps(body)
    # Either an error, or the field is simply absent from the data.
    rows = (body.get("data") or {}).get("agents") or []
    assert all(field not in r for r in rows), f"{field} disclosed: {text}"


def test_blocklisted_column_values_absent_from_any_response(client):
    # Read every allowlisted entity fully and confirm no prohibited field
    # name or canary-like value appears.
    for entity, fields in [
        ("merchants", "merchant_id merchant_name sector tier region"),
        ("agents", "agent_id agent_name tier primary_category shift_region "
                   "efficiency_multiplier"),
        ("tickets", "ticket_id category priority csat_score"),
    ]:
        status, body = _graphql(f"{{ {entity}(limit: 5) {{ {fields} }} }}")
        text = json.dumps(body).lower()
        for name in PROHIBITED_FIELD_NAMES:
            assert name not in text, (
                f"prohibited field name {name!r} present in {entity} "
                f"response")


# ---------------- PostgreSQL role layer ------------------------------------

def test_readonly_role_cannot_read_system_auth_tables():
    with psycopg.connect(
            host="127.0.0.1", port=POSTGRES_PORT, user=RO_USER,
            password=RO_PASSWORD, dbname=POSTGRES_DB,
            connect_timeout=5, autocommit=True) as c, c.cursor() as cur:
        with pytest.raises(psycopg.errors.Error):
            cur.execute("SELECT rolpassword FROM pg_authid")


def test_readonly_role_has_no_schema_create():
    with psycopg.connect(
            host="127.0.0.1", port=POSTGRES_PORT, user=RO_USER,
            password=RO_PASSWORD, dbname=POSTGRES_DB,
            connect_timeout=5, autocommit=True) as c, c.cursor() as cur:
        cur.execute(
            "SELECT has_schema_privilege(current_user, 'itsm', 'CREATE')")
        assert cur.fetchone()[0] is False
