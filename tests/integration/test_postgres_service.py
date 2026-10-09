"""T002: PostgreSQL service integration tests.

Verifies the pinned PostgreSQL service defined in compose.yml reaches a
healthy state and accepts a connection to the configured application database.
"""
import os
import subprocess
import sys
import time

import psycopg
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
COMPOSE_FILE = os.path.join(REPO_ROOT, "compose.yml")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))


def compose(*args, check=True, **kwargs):
    cmd = ["sudo", "-n", "docker", "compose", "-f", COMPOSE_FILE]
    if os.path.exists(ENV_FILE):
        cmd += ["--env-file", ENV_FILE]
    cmd += list(args)
    return subprocess.run(cmd, check=check, capture_output=True, text=True, **kwargs)


@pytest.fixture(scope="module", autouse=True)
def postgres_service():
    compose("up", "-d", "--wait", "postgres")
    # The application database is created explicitly by initialization (T004).
    subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "initialize_database.py")],
        check=True, capture_output=True, text=True, cwd=REPO_ROOT,
    )
    yield
    # leave service running for other test modules; smoke test manages teardown


def conn(dbname=None):
    return psycopg.connect(
        host="127.0.0.1",
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=dbname or POSTGRES_DB,
        connect_timeout=5,
        autocommit=True,
    )


def test_postgres_container_healthy():
    result = compose("ps", "--format", "json")
    import json as _json
    services = [_json.loads(line) for line in result.stdout.strip().splitlines() if line.strip()]
    pg = [s for s in services if s.get("Service") == "postgres"]
    assert pg, "postgres service not found in compose ps output"
    assert pg[0].get("Health") == "healthy" or pg[0].get("State") == "running", pg[0]


def test_postgres_accepts_connection_to_app_database():
    with conn() as c:
        with c.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == POSTGRES_DB


def test_postgres_version_is_pinned_major():
    with conn() as c:
        with c.cursor() as cur:
            cur.execute("SHOW server_version")
            version = cur.fetchone()[0]
    assert version.startswith("16."), f"expected pinned PostgreSQL 16.x, got {version}"
