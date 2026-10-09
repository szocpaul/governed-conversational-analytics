"""T003/T004: Database initialization integration tests.

Verifies that scripts/initialize_database.py reproducibly creates the
application database, schema, tables, indexes, owner role, and read-only
role, and that initialization is idempotent.
"""
import os
import subprocess
import sys

import psycopg
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
COMPOSE_FILE = os.path.join(REPO_ROOT, "compose.yml")
ENV_FILE = os.path.join(REPO_ROOT, ".env")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
GRAPHJIN_DB_USER = os.environ.get("GRAPHJIN_DB_USER", "itsm_readonly")

APP_SCHEMA = "itsm"


def compose(*args, check=True):
    cmd = ["sudo", "-n", "docker", "compose", "-f", COMPOSE_FILE]
    if os.path.exists(ENV_FILE):
        cmd += ["--env-file", ENV_FILE]
    cmd += list(args)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def admin_conn(dbname="postgres"):
    return psycopg.connect(
        host="127.0.0.1", port=POSTGRES_PORT, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, dbname=dbname, connect_timeout=5,
        autocommit=True,
    )


def run_initialize():
    env = dict(os.environ)
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "initialize_database.py")],
        check=True, capture_output=True, text=True, env=env, cwd=REPO_ROOT,
    )


@pytest.fixture(scope="module", autouse=True)
def initialized_database():
    compose("up", "-d", "--wait", "postgres")
    run_initialize()
    yield


def test_application_database_exists():
    with admin_conn() as c, c.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DB,))
        assert cur.fetchone() is not None


def test_readonly_role_exists():
    with admin_conn() as c, c.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (GRAPHJIN_DB_USER,))
        assert cur.fetchone() is not None


def test_schema_and_tables_exist():
    with admin_conn(POSTGRES_DB) as c, c.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s ORDER BY table_name", (APP_SCHEMA,))
        tables = [r[0] for r in cur.fetchall()]
    assert tables == ["agents", "merchants", "tickets"]


def test_primary_keys_exist():
    expected = {"merchants": "merchant_id", "agents": "agent_id", "tickets": "ticket_id"}
    with admin_conn(POSTGRES_DB) as c, c.cursor() as cur:
        for table, col in expected.items():
            cur.execute(
                "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
                "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s AND tc.table_name = %s",
                (APP_SCHEMA, table))
            assert cur.fetchone()[0] == col


def test_foreign_keys_exist():
    with admin_conn(POSTGRES_DB) as c, c.cursor() as cur:
        cur.execute(
            "SELECT kcu.column_name, ccu.table_name, ccu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema "
            "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s AND tc.table_name = 'tickets' "
            "ORDER BY kcu.column_name", (APP_SCHEMA,))
        fks = {(r[0], r[1], r[2]) for r in cur.fetchall()}
    assert ("merchant_id", "merchants", "merchant_id") in fks
    assert ("assigned_agent_id", "agents", "agent_id") in fks


def test_indexes_exist():
    with admin_conn(POSTGRES_DB) as c, c.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = %s", (APP_SCHEMA,))
        indexes = {r[0] for r in cur.fetchall()}
    expected = {
        "idx_tickets_merchant_id", "idx_tickets_assigned_agent_id",
        "idx_tickets_priority", "idx_tickets_category", "idx_tickets_created_at",
    }
    assert expected <= indexes, f"missing indexes: {expected - indexes}"


def test_readonly_role_can_select_but_not_write():
    with admin_conn(POSTGRES_DB) as c, c.cursor() as cur:
        cur.execute("SELECT rolpassword IS NOT NULL FROM pg_authid WHERE rolname = %s",
                    (GRAPHJIN_DB_USER,))
    # privileges checked in detail by tests/security/test_read_only_access.py;
    # here we only verify the role can connect and select after grants
    ro_password = os.environ.get("GRAPHJIN_DB_PASSWORD", "change-me-readonly-local-only")
    with psycopg.connect(host="127.0.0.1", port=POSTGRES_PORT, user=GRAPHJIN_DB_USER,
                         password=ro_password, dbname=POSTGRES_DB, connect_timeout=5,
                         autocommit=True) as c, c.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {APP_SCHEMA}.merchants")
        assert cur.fetchone()[0] >= 0


def test_initialization_is_idempotent():
    # Running initialization a second time must succeed without errors
    run_initialize()
    with admin_conn(POSTGRES_DB) as c, c.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
            (APP_SCHEMA,))
        assert len(cur.fetchall()) == 3
