"""T007: GraphJin governed query integration tests.

Verifies that allowed entity/field/relationship queries succeed through the
GraphJin GraphQL surface and that prohibited entities and fields disclose
nothing. GraphJin connects with the read-only PostgreSQL role only.
"""
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
COMPOSE_FILE = os.path.join(REPO_ROOT, "compose.yml")
ENV_FILE = os.path.join(REPO_ROOT, ".env")

GRAPHJIN_PORT = int(os.environ.get("GRAPHJIN_PORT", "8081"))
BASE = f"http://127.0.0.1:{GRAPHJIN_PORT}"


def compose(*args, check=True):
    cmd = ["sudo", "-n", "docker", "compose", "-f", COMPOSE_FILE]
    if os.path.exists(ENV_FILE):
        cmd += ["--env-file", ENV_FILE]
    cmd += list(args)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def graphql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/v1/graphql", data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def wait_ready(attempts=60, delay=2.0):
    """Poll the GraphQL endpoint until the query engine is initialized."""
    probe = "{ __typename }"
    for _ in range(attempts):
        try:
            body = json.dumps({"query": probe}).encode()
            req = urllib.request.Request(
                f"{BASE}/api/v1/graphql", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                payload = json.loads(resp.read())
            # initialized engine answers __typename without "not initialized"
            errs = payload.get("errors") or []
            if not any("not initialized" in str(e) for e in errs):
                return
        except Exception:
            pass
        time.sleep(delay)
    raise RuntimeError("GraphJin did not become ready")


@pytest.fixture(scope="module", autouse=True)
def graphjin_service():
    compose("up", "-d", "--wait", "postgres", "graphjin")
    wait_ready()
    yield


def test_allowed_entity_query_returns_records():
    status, body = graphql("{ merchants(limit: 5) { merchant_id merchant_name sector tier region } }")
    assert status == 200, body
    data = body.get("data", {})
    assert "merchants" in data, body
    rows = data["merchants"]
    assert 1 <= len(rows) <= 5
    assert set(rows[0].keys()) == {"merchant_id", "merchant_name", "sector", "tier", "region"}


def test_relationship_query_tickets_with_merchant():
    status, body = graphql(
        "{ tickets(limit: 3) { ticket_id priority merchants { merchant_name } } }")
    assert status == 200, body
    rows = body["data"]["tickets"]
    assert len(rows) >= 1
    assert rows[0]["merchants"]["merchant_name"]


def test_result_limit_is_enforced():
    status, body = graphql("{ tickets { ticket_id } }")
    assert status == 200, body
    rows = body["data"]["tickets"]
    # configured default_limit caps results well below the 2057 total
    assert len(rows) <= 100


def test_prohibited_entity_is_rejected():
    # pg_tables / arbitrary system entities must not be exposed
    status, body = graphql("{ pg_tables { tablename } }")
    text = json.dumps(body)
    assert "tablename" not in text or body.get("errors"), body
    assert not (body.get("data", {}) or {}).get("pg_tables"), body


def test_mutation_is_rejected():
    status, body = graphql(
        'mutation { update_tickets(set: { priority: "P1" }, where: {}) { ticket_id } }')
    assert body.get("errors"), f"expected mutation rejection, got {body}"
    assert not (body.get("data") or {}).get("update_tickets")


def test_insert_mutation_is_rejected():
    status, body = graphql(
        'mutation { insert_merchants(objects: [{ merchant_id: 9999, merchant_name: "x", '
        'sector: "x", tier: "x", region: "x" }]) { merchant_id } }')
    assert body.get("errors"), f"expected insert rejection, got {body}"
    assert not (body.get("data") or {}).get("insert_merchants")
