#!/usr/bin/env python3
"""T005: Validated, atomic import of the pinned ITSM dataset.

Reads the immutable raw CSV files, verifies their SHA-256 checksums against
artifacts/import-manifest.json, validates rows, and imports merchants,
agents, and tickets in a single transaction (atomic: any validation or
database error rolls back all changes). Import is idempotent: existing rows
are replaced via upsert on business keys, never duplicated.

Updates artifacts/import-manifest.json with import results.
"""
import csv
import datetime
import hashlib
import json
import os
import sys

import psycopg

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(REPO_ROOT, "data", "raw")
MANIFEST_PATH = os.path.join(REPO_ROOT, "artifacts", "import-manifest.json")

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "itsm_owner")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "change-me-local-only")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")

EXPECTED_FILES = ("merchants.csv", "agents.csv", "tickets.csv")

TRUE_VALUES = {"true", "1", "yes", "t"}
FALSE_VALUES = {"false", "0", "no", "f"}


class ImportValidationError(Exception):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_bool(value, field, rownum):
    if value is None or value == "":
        return None
    v = value.strip().lower()
    if v in TRUE_VALUES:
        return True
    if v in FALSE_VALUES:
        return False
    raise ImportValidationError(f"row {rownum}: invalid boolean for {field}: {value!r}")


def parse_ts(value):
    """Parse timestamps like '2025-05-13 02:10:36.000000000' (nanoseconds).

    PostgreSQL timestamptz supports microseconds; truncate to 6 digits.
    """
    if value is None or value == "":
        return None
    v = value.strip()
    if "." in v:
        head, frac = v.split(".", 1)
        frac = (frac + "000000")[:6]
        v = f"{head}.{frac}"
        fmt = "%Y-%m-%d %H:%M:%S.%f"
    else:
        fmt = "%Y-%m-%d %H:%M:%S"
    return datetime.datetime.strptime(v, fmt).replace(tzinfo=datetime.timezone.utc)


def parse_float(value):
    if value is None or value == "":
        return None
    return float(value)


def parse_int(value):
    if value is None or value == "":
        return None
    return int(value)


def load_csv(name):
    path = os.path.join(RAW_DIR, name)
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def validate_unique(rows, key, table):
    seen = set()
    for i, r in enumerate(rows, start=2):  # header is row 1
        v = r[key]
        if v is None or v == "":
            raise ImportValidationError(f"{table} row {i}: missing business key {key}")
        if v in seen:
            raise ImportValidationError(f"{table} row {i}: duplicate business key {key}={v}")
        seen.add(v)
    return seen


def verify_checksums(manifest):
    recorded = manifest["dataset"]["files"]
    for name in EXPECTED_FILES:
        path = os.path.join(RAW_DIR, name)
        if not os.path.exists(path):
            raise ImportValidationError(f"missing raw file {name}")
        actual = sha256_file(path)
        expected = recorded[name]["sha256"]
        if actual != expected:
            raise ImportValidationError(
                f"checksum mismatch for {name}: expected {expected}, got {actual}. "
                "Raw files are immutable; refusing to import modified source.")


# ---------------------------------------------------------------------------
# Feature 009: generated ticket texts (additive columns, human-approved artifact)
# ---------------------------------------------------------------------------

TEXTS_ARTIFACT_PATH = os.environ.get(
    "TICKETS_TEXTS_PATH", os.path.join(RAW_DIR, "tickets_texts.jsonl"))
TEXTS_MANIFEST_PATH = os.environ.get(
    "TEXTS_MANIFEST_PATH", os.path.join(RAW_DIR, "texts-manifest.json"))

GENERATED_COLUMNS = ("short_description", "description", "resolution_notes")

# ---------------------------------------------------------------------------
# Feature 010: ticket embeddings (additive vector column, pinned artifact)
# ---------------------------------------------------------------------------

EMBEDDINGS_ARTIFACT_PATH = os.environ.get(
    "TICKETS_EMBEDDINGS_PATH", os.path.join(RAW_DIR, "tickets_embeddings.jsonl"))
EMBEDDINGS_MANIFEST_PATH = os.environ.get(
    "EMBEDDINGS_MANIFEST_PATH", os.path.join(RAW_DIR, "embeddings-manifest.json"))

EMBEDDING_DIMENSION = 768


def load_embeddings(tickets_raw):
    """Load and fully verify the pinned embedding artifact.

    Returns (vectors_by_id, embeddings_manifest) or None when the artifact is
    absent (pre-feature-010 checkout: embeddings import is skipped). Any
    verification failure raises ImportValidationError -> full rollback.
    """
    if not os.path.exists(EMBEDDINGS_ARTIFACT_PATH) or not os.path.exists(EMBEDDINGS_MANIFEST_PATH):
        return None
    with open(EMBEDDINGS_MANIFEST_PATH, encoding="utf-8") as fh:
        embeddings_manifest = json.load(fh)

    # (a) artifact SHA-256 must equal the manifest's recorded checksum.
    actual_sha = sha256_file(EMBEDDINGS_ARTIFACT_PATH)
    recorded_sha = embeddings_manifest.get("artifact_sha256")
    if actual_sha != recorded_sha:
        raise ImportValidationError(
            f"embedding artifact SHA-256 mismatch: manifest records "
            f"{recorded_sha}, file is {actual_sha}. Refusing to import a "
            f"modified or unverified artifact.")

    vectors = {}
    with open(EMBEDDINGS_ARTIFACT_PATH, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ImportValidationError(
                    f"embedding artifact line {lineno}: invalid JSON: {exc}")
            vec = obj.get("embedding")
            # (c) every vector dimension == 768.
            if not isinstance(vec, list) or len(vec) != EMBEDDING_DIMENSION:
                raise ImportValidationError(
                    f"embedding artifact line {lineno} (ticket "
                    f"{obj.get('ticket_id')}): dimension "
                    f"{len(vec) if isinstance(vec, list) else 'n/a'} != "
                    f"{EMBEDDING_DIMENSION}")
            vectors[int(obj["ticket_id"])] = vec

    # (b) ticket_id coverage must be exactly the pinned set.
    pinned_ids = {int(r["ticket_id"]) for r in tickets_raw}
    got_ids = set(vectors)
    if got_ids != pinned_ids:
        missing = sorted(pinned_ids - got_ids)[:5]
        extra = sorted(got_ids - pinned_ids)[:5]
        raise ImportValidationError(
            f"embedding coverage mismatch: missing={missing} extra={extra} "
            f"(expected exactly the pinned {len(pinned_ids)} ticket_ids)")
    return vectors, embeddings_manifest


def load_generated_texts(tickets_raw):
    """Load and fully verify the pinned, human-approved generated artifact.

    Returns (entries_by_id, texts_manifest) or None when the artifact is
    absent (feature-001-only checkout: texts import is skipped). Any
    verification failure raises ImportValidationError -> full rollback.
    """
    if not os.path.exists(TEXTS_ARTIFACT_PATH) or not os.path.exists(TEXTS_MANIFEST_PATH):
        return None
    with open(TEXTS_MANIFEST_PATH, encoding="utf-8") as fh:
        texts_manifest = json.load(fh)

    # (a) artifact SHA-256 must equal the manifest's recorded checksum.
    actual_sha = sha256_file(TEXTS_ARTIFACT_PATH)
    recorded_sha = texts_manifest.get("artifact_sha256")
    if actual_sha != recorded_sha:
        raise ImportValidationError(
            f"generated texts artifact SHA-256 mismatch: manifest records "
            f"{recorded_sha}, file is {actual_sha}. Refusing to import a "
            f"modified or unverified artifact.")

    # (d) human data-quality approval (MANUAL GATE) must be recorded.
    human_review = texts_manifest.get("human_review") or {}
    if human_review.get("approved") is not True:
        raise ImportValidationError(
            "generated texts artifact has no recorded human approval "
            "(human_review.approved != true). The MANUAL GATE is required "
            "before import; refusing to import an unreviewed artifact.")

    entries = {}
    with open(TEXTS_ARTIFACT_PATH, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ImportValidationError(
                    f"generated texts artifact line {lineno}: invalid JSON: {exc}")
            entries[obj["ticket_id"]] = obj

    # (b) ticket_id coverage must be exactly the pinned set.
    pinned_ids = {int(r["ticket_id"]) for r in tickets_raw}
    got_ids = set(entries)
    if got_ids != pinned_ids:
        missing = sorted(pinned_ids - got_ids)[:5]
        extra = sorted(got_ids - pinned_ids)[:5]
        raise ImportValidationError(
            f"generated texts coverage mismatch: missing={missing} extra={extra} "
            f"(expected exactly the pinned {len(pinned_ids)} ticket_ids)")

    # (c) NULL rule: resolution_notes null exactly for open tickets.
    open_by_id = {int(r["ticket_id"]): not r["closed_at"].strip() for r in tickets_raw}
    for tid, obj in entries.items():
        notes = obj.get("resolution_notes")
        if open_by_id[tid] and notes is not None:
            raise ImportValidationError(
                f"generated texts ticket {tid}: resolution_notes present for an "
                f"open ticket (must be null)")
        if not open_by_id[tid] and notes is None:
            raise ImportValidationError(
                f"generated texts ticket {tid}: resolution_notes null for a "
                f"closed ticket (must be present)")
    return entries, texts_manifest


def main():
    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        manifest = json.load(fh)

    verify_checksums(manifest)

    merchants_raw = load_csv("merchants.csv")
    agents_raw = load_csv("agents.csv")
    tickets_raw = load_csv("tickets.csv")

    merchant_ids = validate_unique(merchants_raw, "merchant_id", "merchants.csv")
    agent_ids = validate_unique(agents_raw, "agent_id", "agents.csv")
    validate_unique(tickets_raw, "ticket_id", "tickets.csv")

    merchants = [
        (int(r["merchant_id"]), r["merchant_name"], r["sector"], r["tier"], r["region"])
        for r in merchants_raw
    ]
    agents = [
        (int(r["agent_id"]), r["agent_name"], r["tier"], r["primary_category"],
         r["shift_region"], float(r["efficiency_multiplier"]))
        for r in agents_raw
    ]

    tickets = []
    for i, r in enumerate(tickets_raw, start=2):
        if r["merchant_id"] not in merchant_ids:
            raise ImportValidationError(
                f"tickets.csv row {i}: merchant_id {r['merchant_id']} has no merchant")
        agent = r["assigned_agent_id"]
        if agent and agent not in agent_ids:
            raise ImportValidationError(
                f"tickets.csv row {i}: assigned_agent_id {agent} has no agent")
        tickets.append((
            int(r["ticket_id"]), int(r["merchant_id"]), r["category"], r["sub_category"],
            r["priority"], parse_ts(r["created_at"]),
            parse_bool(r["is_legacy"], "is_legacy", i),
            parse_int(agent),
            parse_bool(r["category_mismatch"], "category_mismatch", i),
            parse_ts(r["first_response_at"]), parse_ts(r["closed_at"]),
            parse_float(r["ttfr_hours"]), parse_float(r["resolution_hours"]),
            parse_bool(r["response_breached"], "response_breached", i),
            parse_bool(r["resolution_breached"], "resolution_breached", i),
            parse_bool(r["is_reopened"], "is_reopened", i),
            parse_bool(r["is_reopen_child"], "is_reopen_child", i),
            parse_bool(r["is_incident_ticket"], "is_incident_ticket", i),
            parse_float(r["csat_score"]),
        ))

    # Feature 009: load + verify the generated texts BEFORE opening the
    # transaction so any failure aborts before any database write.
    generated = load_generated_texts(tickets_raw)
    # Feature 010: load + verify the pinned embedding artifact the same way.
    embeddings = load_embeddings(tickets_raw)

    conn = psycopg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT, user=POSTGRES_USER,
        password=POSTGRES_PASSWORD, dbname=POSTGRES_DB, connect_timeout=5)
    try:
        with conn:  # single transaction: commit on success, rollback on error
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO itsm.merchants (merchant_id, merchant_name, sector, tier, region) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (merchant_id) DO UPDATE SET merchant_name = EXCLUDED.merchant_name, "
                    "sector = EXCLUDED.sector, tier = EXCLUDED.tier, region = EXCLUDED.region",
                    merchants)
                cur.executemany(
                    "INSERT INTO itsm.agents (agent_id, agent_name, tier, primary_category, "
                    "shift_region, efficiency_multiplier) VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (agent_id) DO UPDATE SET agent_name = EXCLUDED.agent_name, "
                    "tier = EXCLUDED.tier, primary_category = EXCLUDED.primary_category, "
                    "shift_region = EXCLUDED.shift_region, "
                    "efficiency_multiplier = EXCLUDED.efficiency_multiplier",
                    agents)
                cur.executemany(
                    "INSERT INTO itsm.tickets (ticket_id, merchant_id, category, sub_category, "
                    "priority, created_at, is_legacy, assigned_agent_id, category_mismatch, "
                    "first_response_at, closed_at, ttfr_hours, resolution_hours, "
                    "response_breached, resolution_breached, is_reopened, is_reopen_child, "
                    "is_incident_ticket, csat_score) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (ticket_id) DO UPDATE SET merchant_id = EXCLUDED.merchant_id, "
                    "category = EXCLUDED.category, sub_category = EXCLUDED.sub_category, "
                    "priority = EXCLUDED.priority, created_at = EXCLUDED.created_at, "
                    "is_legacy = EXCLUDED.is_legacy, assigned_agent_id = EXCLUDED.assigned_agent_id, "
                    "category_mismatch = EXCLUDED.category_mismatch, "
                    "first_response_at = EXCLUDED.first_response_at, closed_at = EXCLUDED.closed_at, "
                    "ttfr_hours = EXCLUDED.ttfr_hours, resolution_hours = EXCLUDED.resolution_hours, "
                    "response_breached = EXCLUDED.response_breached, "
                    "resolution_breached = EXCLUDED.resolution_breached, "
                    "is_reopened = EXCLUDED.is_reopened, is_reopen_child = EXCLUDED.is_reopen_child, "
                    "is_incident_ticket = EXCLUDED.is_incident_ticket, "
                    "csat_score = EXCLUDED.csat_score",
                    tickets)

                # Feature 009: upsert the three generated columns per ticket in
                # the SAME single transaction (generated columns only). The
                # tickets were upserted above, so every ticket_id is present;
                # a plain UPDATE of the generated columns is the correct upsert.
                if generated is not None:
                    entries, _texts_manifest = generated
                    text_rows = [
                        (e["short_description"], e["description"], e["resolution_notes"], tid)
                        for tid, e in entries.items()
                    ]
                    cur.executemany(
                        "UPDATE itsm.tickets SET short_description = %s, "
                        "description = %s, resolution_notes = %s "
                        "WHERE ticket_id = %s",
                        text_rows)

                # Feature 010: upsert the embedding column per ticket in the
                # SAME single transaction (the embedding column only). The
                # tickets were upserted above, so every ticket_id is present.
                if embeddings is not None:
                    vectors, _emb_manifest = embeddings
                    emb_rows = [
                        ("[" + ",".join(repr(float(v)) for v in vec) + "]", tid)
                        for tid, vec in vectors.items()
                    ]
                    cur.executemany(
                        "UPDATE itsm.tickets SET embedding = %s::vector "
                        "WHERE ticket_id = %s",
                        emb_rows)

                # Post-import validation inside the transaction.
                cur.execute("SELECT count(*) FROM itsm.merchants")
                n_merchants = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM itsm.agents")
                n_agents = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM itsm.tickets")
                n_tickets = cur.fetchone()[0]
                if (n_merchants, n_agents, n_tickets) != (
                        len(merchants), len(agents), len(tickets)):
                    raise ImportValidationError(
                        f"post-import row counts differ from source: "
                        f"merchants {n_merchants}/{len(merchants)}, "
                        f"agents {n_agents}/{len(agents)}, tickets {n_tickets}/{len(tickets)}")
                cur.execute(
                    "SELECT count(*) FROM itsm.tickets t LEFT JOIN itsm.merchants m "
                    "ON m.merchant_id = t.merchant_id WHERE m.merchant_id IS NULL")
                if cur.fetchone()[0]:
                    raise ImportValidationError("unresolved merchant foreign keys after import")
                cur.execute(
                    "SELECT count(*) FROM itsm.tickets t LEFT JOIN itsm.agents a "
                    "ON a.agent_id = t.assigned_agent_id "
                    "WHERE t.assigned_agent_id IS NOT NULL AND a.agent_id IS NULL")
                if cur.fetchone()[0]:
                    raise ImportValidationError("unresolved agent foreign keys after import")
                # Feature 009: post-import generated-columns checks inside the
                # transaction (counts + NULL rule against tickets.csv).
                if generated is not None:
                    entries, _tm = generated
                    cur.execute(
                        "SELECT count(*) FROM itsm.tickets WHERE "
                        "short_description IS NULL OR description IS NULL")
                    if cur.fetchone()[0]:
                        raise ImportValidationError(
                            "generated columns short_description/description "
                            "incomplete after import")
                    open_ids = {tid for tid, r in ((int(x["ticket_id"]), x) for x in tickets_raw)
                                if not r["closed_at"].strip()}
                    cur.execute(
                        "SELECT count(*) FROM itsm.tickets WHERE resolution_notes IS NULL")
                    n_null = cur.fetchone()[0]
                    if n_null != len(open_ids):
                        raise ImportValidationError(
                            f"resolution_notes NULL count {n_null} != open ticket "
                            f"count {len(open_ids)} after import")
                # Feature 010: post-import embedding checks inside the
                # transaction (count + dimension).
                if embeddings is not None:
                    cur.execute(
                        "SELECT count(*) FROM itsm.tickets WHERE embedding IS NULL")
                    if cur.fetchone()[0]:
                        raise ImportValidationError(
                            "embedding column incomplete after import")
                    cur.execute(
                        "SELECT count(*) FROM itsm.tickets WHERE "
                        "vector_dims(embedding) != %s", (EMBEDDING_DIMENSION,))
                    if cur.fetchone()[0]:
                        raise ImportValidationError(
                            f"embedding dimension != {EMBEDDING_DIMENSION} "
                            "after import")
    except Exception:
        conn.close()
        raise
    else:
        conn.close()

    manifest["import"] = {
        "imported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "row_counts": {"merchants": len(merchants), "agents": len(agents),
                       "tickets": len(tickets)},
        "validation": {
            "passed": True,
            "checks": [
                "sha256 checksums of raw files match manifest",
                "unique non-null business keys",
                "required fields present",
                "timestamp and boolean conversion",
                "foreign-key integrity",
                "post-import row counts match source",
                "atomic single-transaction import",
            ],
        },
    }
    # Feature 009: additive generated_texts provenance key; existing keys untouched.
    if generated is not None:
        entries, texts_manifest = generated
        manifest["generated_texts"] = {
            "artifact_path": os.path.relpath(TEXTS_ARTIFACT_PATH, REPO_ROOT),
            "artifact_sha256": sha256_file(TEXTS_ARTIFACT_PATH),
            "texts_manifest_path": os.path.relpath(TEXTS_MANIFEST_PATH, REPO_ROOT),
            "texts_manifest_sha256": sha256_file(TEXTS_MANIFEST_PATH),
            "artifact_version": str(texts_manifest.get("artifact_version", "1")),
            "row_count": len(entries),
            "human_review": texts_manifest.get("human_review"),
            "imported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    # Feature 010: additive ticket_embeddings provenance key; existing keys untouched.
    if embeddings is not None:
        vectors, embeddings_manifest = embeddings
        manifest["ticket_embeddings"] = {
            "artifact_path": os.path.relpath(EMBEDDINGS_ARTIFACT_PATH, REPO_ROOT),
            "artifact_sha256": sha256_file(EMBEDDINGS_ARTIFACT_PATH),
            "embeddings_manifest_path": os.path.relpath(EMBEDDINGS_MANIFEST_PATH, REPO_ROOT),
            "embeddings_manifest_sha256": sha256_file(EMBEDDINGS_MANIFEST_PATH),
            "artifact_version": str(embeddings_manifest.get("artifact_version", "1")),
            "row_count": len(vectors),
            "embedding_dimension": EMBEDDING_DIMENSION,
            "imported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"imported {len(merchants)} merchants, {len(agents)} agents, "
          f"{len(tickets)} tickets (atomic, validated)")
    if generated is not None:
        entries, _tm = generated
        print(f"imported generated texts for {len(entries)} tickets "
              f"(3 columns, human-approved artifact)")
    if embeddings is not None:
        vectors, _em = embeddings
        print(f"imported embeddings for {len(vectors)} tickets "
              f"(vector({EMBEDDING_DIMENSION}), pinned artifact)")


if __name__ == "__main__":
    try:
        main()
    except ImportValidationError as exc:
        print(f"IMPORT FAILED (no changes applied): {exc}", file=sys.stderr)
        sys.exit(1)
