"""T015: Integration tests for the generated-texts database import (feature 009 US2).

Verifies the atomic, idempotent import of the pinned, human-approved generated
artifact into itsm.tickets as three additive columns, with provenance recorded
in artifacts/import-manifest.json. Negative paths (unapproved manifest,
tampered artifact) fail with ZERO database changes and never touch the real
pinned files (env-var path overrides point the import at tmp fixture copies).
"""
import hashlib
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
TEXTS_ARTIFACT = os.path.join(REPO_ROOT, "data", "raw", "tickets_texts.jsonl")
TEXTS_MANIFEST = os.path.join(REPO_ROOT, "data", "raw", "texts-manifest.json")
TICKETS_CSV = os.path.join(REPO_ROOT, "data", "raw", "tickets.csv")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))

EXPECTED_COUNTS = {"merchants": 112, "agents": 20, "tickets": 2057}
EXPECTED_OPEN = 250
EXPECTED_CLOSED = 1807


def compose(*args, check=True):
    cmd = ["sudo", "-n", "docker", "compose", "-f", COMPOSE_FILE]
    if os.path.exists(ENV_FILE):
        cmd += ["--env-file", ENV_FILE]
    cmd += list(args)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def run_import(check=True, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "import_dataset.py")],
        check=check, capture_output=True, text=True, cwd=REPO_ROOT, env=env)


def conn():
    return psycopg.connect(
        host="127.0.0.1", port=POSTGRES_PORT, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, dbname=POSTGRES_DB,
        connect_timeout=5, autocommit=True)


def counts():
    with conn() as c, c.cursor() as cur:
        out = {}
        for t in ("merchants", "agents", "tickets"):
            cur.execute(f"SELECT count(*) FROM itsm.{t}")
            out[t] = cur.fetchone()[0]
        return out


def texts_state():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM itsm.tickets WHERE short_description IS NOT NULL")
        n_short = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM itsm.tickets WHERE description IS NOT NULL")
        n_desc = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM itsm.tickets WHERE resolution_notes IS NOT NULL")
        n_notes = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM itsm.tickets WHERE resolution_notes IS NULL")
        n_notes_null = cur.fetchone()[0]
        return {"short": n_short, "desc": n_desc,
                "notes": n_notes, "notes_null": n_notes_null}


def _sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


@pytest.fixture(scope="module", autouse=True)
def imported_database():
    compose("up", "-d", "--wait", "postgres")
    subprocess.run([sys.executable, os.path.join(REPO_ROOT, "scripts", "initialize_database.py")],
                   check=True, capture_output=True, text=True, cwd=REPO_ROOT)
    run_import()
    yield


# ---------------------------------------------------------------------------
# Positive path: columns populated, NULL rule, pinned columns unchanged
# ---------------------------------------------------------------------------

def test_generated_columns_populated_with_null_rule():
    state = texts_state()
    assert state["short"] == EXPECTED_COUNTS["tickets"]
    assert state["desc"] == EXPECTED_COUNTS["tickets"]
    assert state["notes"] == EXPECTED_CLOSED
    assert state["notes_null"] == EXPECTED_OPEN


def test_generated_columns_exist_in_schema():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='itsm' AND table_name='tickets'")
        cols = {r[0] for r in cur.fetchall()}
    assert {"short_description", "description", "resolution_notes"} <= cols


def test_pinned_columns_unchanged_spot_check():
    import csv
    with open(TICKETS_CSV, newline="", encoding="utf-8") as fh:
        rows = {int(r["ticket_id"]): r for r in csv.DictReader(fh)}
    sample_ids = list(rows)[:25] + list(rows)[-25:]
    with conn() as c, c.cursor() as cur:
        for tid in sample_ids:
            cur.execute(
                "SELECT category, sub_category, priority, is_legacy FROM itsm.tickets "
                "WHERE ticket_id = %s", (tid,))
            row = cur.fetchone()
            src = rows[tid]
            assert row[0] == src["category"]
            assert row[1] == src["sub_category"]
            assert row[2] == src["priority"]
            assert row[3] == (src["is_legacy"].lower() == "true")


def test_generated_text_matches_artifact_spot_check():
    artifact = {}
    with open(TEXTS_ARTIFACT, encoding="utf-8") as fh:
        for line in fh:
            obj = json.loads(line)
            artifact[obj["ticket_id"]] = obj
    sample_ids = list(artifact)[:10] + list(artifact)[-10:]
    with conn() as c, c.cursor() as cur:
        for tid in sample_ids:
            cur.execute(
                "SELECT short_description, description, resolution_notes "
                "FROM itsm.tickets WHERE ticket_id = %s", (tid,))
            row = cur.fetchone()
            a = artifact[tid]
            assert row[0] == a["short_description"]
            assert row[1] == a["description"]
            assert row[2] == a["resolution_notes"]


def test_reimport_is_idempotent():
    before = texts_state()
    run_import()
    after = texts_state()
    assert counts() == EXPECTED_COUNTS
    assert before == after


# ---------------------------------------------------------------------------
# Negative paths: unapproved manifest, tampered artifact -> zero DB changes
# ---------------------------------------------------------------------------

def _wipe_generated_columns():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "UPDATE itsm.tickets SET short_description=NULL, description=NULL, "
            "resolution_notes=NULL")


def test_import_refuses_unapproved_manifest(tmp_path):
    _wipe_generated_columns()
    # fixture copy of the manifest with approval removed; real manifest untouched
    with open(TEXTS_MANIFEST, encoding="utf-8") as fh:
        m = json.load(fh)
    m["human_review"] = {"approved": False, "reviewer": None,
                         "reviewed_at": None, "sample_notes": None}
    bad_manifest = tmp_path / "texts-manifest.json"
    bad_manifest.write_text(json.dumps(m, indent=2), encoding="utf-8")
    result = run_import(check=False, env_extra={"TEXTS_MANIFEST_PATH": str(bad_manifest)})
    assert result.returncode != 0
    assert "approved" in (result.stderr + result.stdout).lower() or \
           "human" in (result.stderr + result.stdout).lower()
    # zero database changes: generated columns stay NULL
    assert texts_state() == {"short": 0, "desc": 0, "notes": 0,
                             "notes_null": EXPECTED_COUNTS["tickets"]}
    run_import()  # restore approved state for subsequent tests


def test_import_refuses_tampered_artifact(tmp_path):
    _wipe_generated_columns()
    # fixture copy of the artifact with one entry modified -> checksum mismatch
    tampered = tmp_path / "tickets_texts.jsonl"
    with open(TEXTS_ARTIFACT, encoding="utf-8") as fh:
        lines = fh.readlines()
    obj = json.loads(lines[0])
    obj["short_description"] = "TAMPERED " + obj["short_description"]
    lines[0] = json.dumps(obj) + "\n"
    tampered.write_text("".join(lines), encoding="utf-8")
    result = run_import(check=False, env_extra={"TICKETS_TEXTS_PATH": str(tampered)})
    assert result.returncode != 0
    assert texts_state() == {"short": 0, "desc": 0, "notes": 0,
                             "notes_null": EXPECTED_COUNTS["tickets"]}
    run_import()  # restore approved state


# ---------------------------------------------------------------------------
# Manifest extension
# ---------------------------------------------------------------------------

def test_import_manifest_gains_generated_texts_key():
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    gt = manifest.get("generated_texts")
    assert gt is not None, "import manifest missing generated_texts key"
    assert gt["artifact_path"] == "data/raw/tickets_texts.jsonl"
    assert gt["artifact_sha256"] == _sha256(TEXTS_ARTIFACT)
    assert gt["texts_manifest_path"] == "data/raw/texts-manifest.json"
    assert gt["texts_manifest_sha256"] == _sha256(TEXTS_MANIFEST)
    assert gt["artifact_version"] == "1"
    assert gt["row_count"] == EXPECTED_COUNTS["tickets"]
    assert gt["human_review"]["approved"] is True
    assert gt["human_review"]["reviewer"]
    assert gt["imported_at"]
    # feature-001 compatibility: existing keys keep their shape
    assert manifest["dataset"]["pinned_commit_sha"] == (
        "cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b")
    assert manifest["import"]["row_counts"] == EXPECTED_COUNTS
    assert manifest["import"]["validation"]["passed"] is True
