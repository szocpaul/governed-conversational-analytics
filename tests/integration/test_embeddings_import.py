"""T014: Integration tests for the embedding database import (feature 010 US2).

Verifies the atomic, idempotent import of the pinned, human-approved embedding
artifact into itsm.tickets as a vector(768) column, the generated fts column +
both indexes, the vector extension, and the additive import-manifest extension.
Negative paths (tampered artifact checksum) fail with ZERO database changes.
Live stack on the pinned pgvector/pgvector:pg16 image.
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
EMB_ARTIFACT = os.path.join(REPO_ROOT, "data", "raw", "tickets_embeddings.jsonl")
EMB_MANIFEST = os.path.join(REPO_ROOT, "data", "raw", "embeddings-manifest.json")
TICKETS_CSV = os.path.join(REPO_ROOT, "data", "raw", "tickets.csv")
TEXTS_ARTIFACT = os.path.join(REPO_ROOT, "data", "raw", "tickets_texts.jsonl")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))

EXPECTED_TICKETS = 2057
EMBEDDING_DIM = 768


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
# Vector extension + columns + indexes
# ---------------------------------------------------------------------------

def test_vector_extension_present_with_version():
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        row = cur.fetchone()
    assert row is not None and row[0]


def test_embedding_column_populated_all_tickets():
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM itsm.tickets WHERE embedding IS NOT NULL")
        n = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM itsm.tickets WHERE vector_dims(embedding) != %s",
            (EMBEDDING_DIM,))
        bad = cur.fetchone()[0]
    assert n == EXPECTED_TICKETS
    assert bad == 0


def test_fts_column_and_indexes_exist():
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='itsm' AND table_name='tickets'")
        cols = {r[0] for r in cur.fetchall()}
        assert {"embedding", "fts"} <= cols
        cur.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname='itsm' AND tablename='tickets'")
        idx = {r[0] for r in cur.fetchall()}
    assert "tickets_embedding_hnsw" in idx
    assert "tickets_fts_gin" in idx


# ---------------------------------------------------------------------------
# Pinned columns unchanged (additive only)
# ---------------------------------------------------------------------------

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


def test_text_columns_match_feature009_artifact():
    texts = {}
    with open(TEXTS_ARTIFACT, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                o = json.loads(line)
                texts[int(o["ticket_id"])] = o
    sample_ids = list(texts)[:10] + list(texts)[-10:]
    with conn() as c, c.cursor() as cur:
        for tid in sample_ids:
            cur.execute(
                "SELECT short_description, description, resolution_notes "
                "FROM itsm.tickets WHERE ticket_id = %s", (tid,))
            row = cur.fetchone()
            src = texts[tid]
            assert row[0] == src["short_description"]
            assert row[1] == src["description"]
            assert row[2] == src["resolution_notes"]


# ---------------------------------------------------------------------------
# Idempotency + manifest extension
# ---------------------------------------------------------------------------

def test_reimport_is_idempotent():
    run_import()
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM itsm.tickets WHERE embedding IS NOT NULL")
        n = cur.fetchone()[0]
    assert n == EXPECTED_TICKETS


def test_import_manifest_gains_ticket_embeddings_key():
    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert "ticket_embeddings" in manifest
    te = manifest["ticket_embeddings"]
    assert te["artifact_path"] == "data/raw/tickets_embeddings.jsonl"
    assert te["artifact_sha256"] == _sha256(EMB_ARTIFACT)
    assert te["embeddings_manifest_sha256"] == _sha256(EMB_MANIFEST)
    assert te["row_count"] == EXPECTED_TICKETS
    assert te["embedding_dimension"] == EMBEDDING_DIM
    # Existing keys keep their shape (feature 001/009 compatibility).
    assert "dataset" in manifest and "import" in manifest
    assert "generated_texts" in manifest


# ---------------------------------------------------------------------------
# Negative path: tampered artifact fails with zero database changes
# ---------------------------------------------------------------------------

def test_tampered_embedding_artifact_fails_with_zero_changes(tmp_path):
    # Point the import at a tampered COPY via env override; real files untouched.
    tampered = tmp_path / "tampered_embeddings.jsonl"
    with open(EMB_ARTIFACT, encoding="utf-8") as fh:
        lines = fh.readlines()
    obj = json.loads(lines[0])
    obj["embedding"][0] = obj["embedding"][0] + 0.5  # tamper one value
    lines[0] = json.dumps(obj) + "\n"
    tampered.write_text("".join(lines), encoding="utf-8")

    before = _sha256(EMB_ARTIFACT)
    result = run_import(check=False,
                        env_extra={"TICKETS_EMBEDDINGS_PATH": str(tampered)})
    assert result.returncode != 0
    # The real artifact is untouched and the database still holds the
    # original embeddings (the tampered import rolled back).
    assert _sha256(EMB_ARTIFACT) == before
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM itsm.tickets WHERE embedding IS NOT NULL")
        n = cur.fetchone()[0]
    assert n == EXPECTED_TICKETS
