"""T008: Read-only access security tests with database-effect verification.

Proves that the GraphJin runtime (connected as the itsm_readonly PostgreSQL
role) cannot perform INSERT, UPDATE, DELETE, TRUNCATE, CREATE, ALTER, or
DROP, and that every attempted write leaves ZERO database changes. Both
layers are verified: GraphJin policy rejection AND PostgreSQL role denial.
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

GRAPHJIN_PORT = int(os.environ.get("GRAPHJIN_PORT", "8081"))
BASE = f"http://127.0.0.1:{GRAPHJIN_PORT}"

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
RO_USER = os.environ.get("GRAPHJIN_DB_USER", "itsm_readonly")
RO_PASSWORD = os.environ.get("GRAPHJIN_DB_PASSWORD", "change-me-readonly-local-only")

EXPECTED_COUNTS = {"merchants": 112, "agents": 20, "tickets": 2057}


def compose(*args, check=True):
    cmd = ["sudo", "-n", "docker", "compose", "-f", COMPOSE_FILE]
    if os.path.exists(ENV_FILE):
        cmd += ["--env-file", ENV_FILE]
    cmd += list(args)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


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


def wait_ready(attempts=60, delay=2.0):
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


def owner_conn():
    return psycopg.connect(
        host="127.0.0.1", port=POSTGRES_PORT, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, dbname=POSTGRES_DB,
        connect_timeout=5, autocommit=True)


def ro_conn():
    return psycopg.connect(
        host="127.0.0.1", port=POSTGRES_PORT, user=RO_USER,
        password=RO_PASSWORD, dbname=POSTGRES_DB,
        connect_timeout=5, autocommit=True)


def snapshot():
    with owner_conn() as c, c.cursor() as cur:
        out = {}
        for t in ("merchants", "agents", "tickets"):
            cur.execute(f"SELECT count(*) FROM itsm.{t}")
            out[t] = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'itsm'")
        out["tables"] = cur.fetchone()[0]
        return out


@pytest.fixture(scope="module", autouse=True)
def stack():
    compose("up", "-d", "--wait", "postgres")
    subprocess.run(["python3", os.path.join(REPO_ROOT, "scripts", "initialize_database.py")],
                   check=True, capture_output=True, cwd=REPO_ROOT)
    subprocess.run(["python3", os.path.join(REPO_ROOT, "scripts", "import_dataset.py")],
                   check=True, capture_output=True, cwd=REPO_ROOT)
    compose("up", "-d", "graphjin")
    wait_ready()
    yield


# ---------- PostgreSQL role layer (direct connection as itsm_readonly) ----------

def test_readonly_role_select_succeeds():
    with ro_conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM itsm.tickets")
        assert cur.fetchone()[0] == EXPECTED_COUNTS["tickets"]


@pytest.mark.parametrize("statement", [
    "INSERT INTO itsm.merchants (merchant_id, merchant_name, sector, tier, region) "
    "VALUES (9999, 'x', 'x', 'x', 'x')",
    "UPDATE itsm.merchants SET merchant_name = 'hacked' WHERE merchant_id = 101",
    "DELETE FROM itsm.tickets WHERE ticket_id = 847201",
    "TRUNCATE itsm.tickets",
    "CREATE TABLE itsm.evil (id integer)",
    "ALTER TABLE itsm.tickets ADD COLUMN evil text",
    "DROP TABLE itsm.agents",
])
def test_readonly_role_write_and_ddl_fail(statement):
    before = snapshot()
    with pytest.raises(psycopg.errors.Error):
        with ro_conn() as c, c.cursor() as cur:
            cur.execute(statement)
    assert snapshot() == before, f"database changed after rejected: {statement}"


def test_readonly_role_cannot_escalate():
    with ro_conn() as c, c.cursor():
        with pytest.raises(psycopg.errors.Error):
            c.cursor().execute("SET ROLE itsm_owner")
        with pytest.raises(psycopg.errors.Error):
            c.cursor().execute("ALTER ROLE itsm_readonly SUPERUSER")


# ---------- GraphJin layer (GraphQL mutations through the runtime) ----------

@pytest.mark.parametrize("mutation", [
    'mutation { insert_merchants(objects: [{merchant_id: 9998, merchant_name: "x", sector: "x", tier: "x", region: "x"}]) { merchant_id } }',
    'mutation { update_merchants(set: {merchant_name: "hacked"}, where: {merchant_id: {eq: 101}}) { merchant_id } }',
    'mutation { delete_tickets(where: {ticket_id: {eq: 847201}}) { ticket_id } }',
])
def test_graphjin_mutations_rejected(mutation):
    before = snapshot()
    status, body = graphql(mutation)
    assert body.get("errors"), f"expected rejection, got {body}"
    assert snapshot() == before, f"database changed after rejected mutation: {mutation}"


def test_graphjin_sql_injection_attempt_has_no_effect():
    before = snapshot()
    # attempt to smuggle SQL through a filter value
    status, body = graphql(
        '{ tickets(where: { priority: { eq: "P1\'; DROP TABLE itsm.tickets; --" } }) '
        "{ ticket_id } }")
    assert snapshot() == before
    # response must not contain prohibited data; either an error or empty rows
    rows = (body.get("data") or {}).get("tickets") or []
    assert rows == [] or body.get("errors")


def test_graphjin_cannot_read_system_catalogs():
    status, body = graphql("{ pg_roles { rolname } }")
    assert not (body.get("data") or {}).get("pg_roles"), body
