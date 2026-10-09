"""T005/T006: Dataset import integration tests.

Verifies validated, atomic import of the pinned ITSM dataset and that a
clean reset followed by initialization and import reproduces identical
validated row counts and relationships.
"""
import json
import os
import subprocess
import sys

import psycopg
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
COMPOSE_FILE = os.path.join(REPO_ROOT, "compose.yml")
ENV_FILE = os.path.join(REPO_ROOT, ".env")
MANIFEST = os.path.join(REPO_ROOT, "artifacts", "import-manifest.json")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))

EXPECTED_COUNTS = {"merchants": 112, "agents": 20, "tickets": 2057}


def compose(*args, check=True):
    cmd = ["sudo", "-n", "docker", "compose", "-f", COMPOSE_FILE]
    if os.path.exists(ENV_FILE):
        cmd += ["--env-file", ENV_FILE]
    cmd += list(args)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def run_script(name, check=True):
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", name)],
        check=check, capture_output=True, text=True, cwd=REPO_ROOT)


def conn():
    return psycopg.connect(
        host="127.0.0.1", port=POSTGRES_PORT, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, dbname=POSTGRES_DB,
        connect_timeout=5, autocommit=True)


def table_counts():
    with conn() as c, c.cursor() as cur:
        return {
            t: cur.execute(f"SELECT count(*) FROM itsm.{t}") or cur.fetchone()[0]
            for t in ("merchants", "agents", "tickets")
        }


def counts():
    with conn() as c, c.cursor() as cur:
        out = {}
        for t in ("merchants", "agents", "tickets"):
            cur.execute(f"SELECT count(*) FROM itsm.{t}")
            out[t] = cur.fetchone()[0]
        return out


@pytest.fixture(scope="module", autouse=True)
def imported_database():
    compose("up", "-d", "--wait", "postgres")
    run_script("initialize_database.py")
    run_script("import_dataset.py")
    yield


def test_row_counts_match_source():
    assert counts() == EXPECTED_COUNTS


def test_no_duplicate_business_keys():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM (SELECT merchant_id FROM itsm.merchants "
            "GROUP BY merchant_id HAVING count(*) > 1) d")
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT count(*) FROM (SELECT agent_id FROM itsm.agents "
            "GROUP BY agent_id HAVING count(*) > 1) d")
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT count(*) FROM (SELECT ticket_id FROM itsm.tickets "
            "GROUP BY ticket_id HAVING count(*) > 1) d")
        assert cur.fetchone()[0] == 0


def test_foreign_keys_resolve():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM itsm.tickets t "
            "LEFT JOIN itsm.merchants m ON m.merchant_id = t.merchant_id "
            "WHERE m.merchant_id IS NULL")
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT count(*) FROM itsm.tickets t "
            "LEFT JOIN itsm.agents a ON a.agent_id = t.assigned_agent_id "
            "WHERE t.assigned_agent_id IS NOT NULL AND a.agent_id IS NULL")
        assert cur.fetchone()[0] == 0


def test_required_fields_not_null():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM itsm.tickets WHERE merchant_id IS NULL "
            "OR category IS NULL OR priority IS NULL OR created_at IS NULL "
            "OR is_legacy IS NULL")
        assert cur.fetchone()[0] == 0


def test_types_converted():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT pg_typeof(created_at)::text, pg_typeof(is_legacy)::text, "
            "pg_typeof(ttfr_hours)::text FROM itsm.tickets LIMIT 1")
        row = cur.fetchone()
    assert row[0].startswith("timestamp with time zone")
    assert row[1] == "boolean"
    assert row[2] == "double precision"


def test_manifest_records_import_results():
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    imp = manifest.get("import")
    assert imp is not None, "manifest missing import results"
    assert imp["row_counts"] == EXPECTED_COUNTS
    assert imp["validation"]["passed"] is True
    assert manifest["dataset"]["pinned_commit_sha"] == (
        "cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b")


def test_reimport_is_idempotent_no_duplicates():
    run_script("import_dataset.py")
    assert counts() == EXPECTED_COUNTS


def test_reset_reimport_reproduces_identical_counts():
    run_script("reset_database.py")
    run_script("initialize_database.py")
    run_script("import_dataset.py")
    assert counts() == EXPECTED_COUNTS
    test_foreign_keys_resolve()
