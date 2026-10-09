"""T009: Foundation smoke test.

Covers the complete path from a clean state:
  1. start PostgreSQL and wait for health
  2. initialize the database (schema, roles)
  3. import the pinned dataset
  4. start GraphJin
  5. execute one authorized relationship query
  6. verify one unauthorized query is rejected
"""
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

import psycopg
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
COMPOSE_FILE = os.path.join(REPO_ROOT, "compose.yml")
ENV_FILE = os.path.join(REPO_ROOT, ".env")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
GRAPHJIN_PORT = int(os.environ.get("GRAPHJIN_PORT", "8081"))
BASE = f"http://127.0.0.1:{GRAPHJIN_PORT}"

EXPECTED_COUNTS = {"merchants": 112, "agents": 20, "tickets": 2057}


def compose(*args, check=True):
    cmd = ["sudo", "-n", "docker", "compose", "-f", COMPOSE_FILE]
    if os.path.exists(ENV_FILE):
        cmd += ["--env-file", ENV_FILE]
    cmd += list(args)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def run_script(name):
    return subprocess.run(
        ["python3", os.path.join(REPO_ROOT, "scripts", name)],
        check=True, capture_output=True, text=True, cwd=REPO_ROOT)


def graphql(query):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/v1/graphql", data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def wait_graphjin_ready(attempts=60, delay=2.0):
    for _ in range(attempts):
        try:
            body = json.dumps({"query": "{ __typename }"}).encode()
            req = urllib.request.Request(
                f"{BASE}/api/v1/graphql", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                payload = json.loads(resp.read())
            errs = payload.get("errors") or []
            if not any("not initialized" in str(e) for e in errs):
                return
        except Exception:
            pass
        time.sleep(delay)
    raise RuntimeError("GraphJin did not become ready")


def test_foundation_end_to_end():
    # 1. Start PostgreSQL and wait for health
    compose("up", "-d", "--wait", "postgres")
    result = compose("ps", "--format", "json")
    services = [json.loads(line) for line in result.stdout.strip().splitlines() if line.strip()]
    pg = [s for s in services if s.get("Service") == "postgres"]
    assert pg and pg[0].get("Health") == "healthy", pg

    # 2. Initialize the database (idempotent)
    run_script("initialize_database.py")

    # 3. Import the pinned dataset (validated, atomic)
    run_script("import_dataset.py")

    # verify row counts through the owner connection
    with psycopg.connect(host="127.0.0.1", port=POSTGRES_PORT, user=POSTGRES_USER,
                         password=POSTGRES_PASSWORD, dbname=POSTGRES_DB,
                         connect_timeout=5, autocommit=True) as c, c.cursor() as cur:
        for table, expected in EXPECTED_COUNTS.items():
            cur.execute(f"SELECT count(*) FROM itsm.{table}")
            assert cur.fetchone()[0] == expected, table

    # 4. Start GraphJin
    compose("up", "-d", "graphjin")
    wait_graphjin_ready()

    # 5. Authorized relationship query succeeds
    status, body = graphql(
        "{ tickets(limit: 3) { ticket_id priority merchants { merchant_name region } } }")
    assert status == 200, body
    rows = body["data"]["tickets"]
    assert len(rows) == 3
    assert rows[0]["merchants"]["merchant_name"]

    # 6. Unauthorized query is rejected (mutation through the governed surface)
    status, body = graphql(
        'mutation { delete_merchants(where: {}) { merchant_id } }')
    assert body.get("errors"), f"expected rejection, got {body}"
    assert not (body.get("data") or {}).get("delete_merchants")

    # and the database is unchanged
    with psycopg.connect(host="127.0.0.1", port=POSTGRES_PORT, user=POSTGRES_USER,
                         password=POSTGRES_PASSWORD, dbname=POSTGRES_DB,
                         connect_timeout=5, autocommit=True) as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM itsm.merchants")
        assert cur.fetchone()[0] == EXPECTED_COUNTS["merchants"]
