"""Governed hybrid retrieval channel (feature 010, research R1/R7/R8).

A separate governed read-only channel in the application layer (human
decision 1) — NOT through GraphJin, whose semantic search is catalog-level,
not row-level. Connects as the itsm_readonly role and issues a small, fixed
set of PARAMETERIZED SQL statements (lexical ts_rank, semantic pgvector
cosine, deterministic RRF k=60 fusion) built by code — never by the model —
over an explicit allowlist of the three generated text fields.

Governance guarantees (contracts/retrieval-api.md): fixed field allowlist,
enforced result limit, read-only role, no arbitrary SQL (query text and the
reference embedding are bound parameters only), deterministic RRF fusion,
and a sanitized retrieval trace listing exactly the ticket_ids that entered
the model's context.
"""
from __future__ import annotations

import os

import psycopg
import pydantic

# ---------------------------------------------------------------------------
# Governed constants
# ---------------------------------------------------------------------------

# Fixed allowlist of searchable fields (the three generated text fields).
# Fixed in code; never model-controllable.
SEARCHABLE_FIELDS = ("short_description", "description", "resolution_notes")

# Deterministic Reciprocal Rank Fusion constant (human decision 4).
RRF_K = 60

# Result limit: default and hard governed maximum (never exceeded).
DEFAULT_RETRIEVAL_LIMIT = 10
MAX_RETRIEVAL_LIMIT = 25

# Read-only role (SELECT only, statement_timeout 5s) — the ONLY role this
# channel uses (contracts/database-schema.md §3).
READONLY_USER = os.environ.get("GRAPHJIN_DB_USER", "itsm_readonly")
READONLY_PASSWORD = os.environ.get(
    "GRAPHJIN_DB_PASSWORD", "change-me-readonly-local-only")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "itsm")


class RetrievalError(RuntimeError):
    """Raised when governed retrieval cannot complete (dependency failure)."""


# ---------------------------------------------------------------------------
# Typed request (pydantic-validated; contracts/retrieval-api.md)
# ---------------------------------------------------------------------------


class RetrievalRequest(pydantic.BaseModel):
    """A typed, governed retrieval request. No field selection is exposed."""

    model_config = pydantic.ConfigDict(strict=True)

    mode: str  # "about" | "similar"
    query_text: str | None = None   # mode=about
    ticket_id: int | None = None    # mode=similar
    limit: int = DEFAULT_RETRIEVAL_LIMIT

    @pydantic.model_validator(mode="after")
    def _check(self) -> "RetrievalRequest":
        if self.mode not in ("about", "similar"):
            raise ValueError(f"unsupported retrieval mode: {self.mode!r}")
        if self.mode == "about" and not (self.query_text and self.query_text.strip()):
            raise ValueError("mode 'about' requires a non-empty query_text")
        if self.mode == "similar" and self.ticket_id is None:
            raise ValueError("mode 'similar' requires a ticket_id")
        if isinstance(self.ticket_id, bool):
            raise ValueError("ticket_id must be an integer")
        if self.limit < 1:
            raise ValueError("limit must be >= 1")
        # Clamp to the governed maximum (never exceeded).
        object.__setattr__(self, "limit", min(self.limit, MAX_RETRIEVAL_LIMIT))
        return self


def validate_retrieval_request(data: dict) -> RetrievalRequest:
    """Validate a raw retrieval request against the governed policy.

    The searchable fields are fixed to the allowlist; any attempt to target a
    non-allowlisted field is rejected. The limit is clamped to the governed
    maximum. Deterministic: no model, no I/O.
    """
    if not isinstance(data, dict):
        raise ValueError("retrieval request is not an object")
    # A "fields" key, if present, may only name allowlisted fields.
    fields = data.get("fields")
    if fields is not None:
        if not isinstance(fields, (list, tuple)):
            raise ValueError("fields must be a list")
        bad = [f for f in fields if f not in SEARCHABLE_FIELDS]
        if bad:
            raise ValueError(
                f"fields not in the searchable allowlist: {bad!r}; "
                f"searchable fields are fixed to {list(SEARCHABLE_FIELDS)!r}")
    allowed_keys = {"mode", "query_text", "ticket_id", "limit", "fields"}
    unknown = set(data) - allowed_keys
    if unknown:
        raise ValueError(f"unsupported retrieval request keys: {sorted(unknown)!r}")
    return RetrievalRequest.model_validate(data)


# ---------------------------------------------------------------------------
# Fixed parameterized SQL (built by code; query text/vector are bound params)
# ---------------------------------------------------------------------------


def build_lexical_query(query_text: str, *, limit: int) -> tuple[str, list]:
    """Lexical full-text ranking: ts_rank over the generated fts column.

    plainto_tsquery treats the input as plain text (safe for natural-language
    questions); the query text is a BOUND parameter — never interpolated.
    """
    sql = (
        "SELECT ticket_id, "
        "ts_rank(fts, plainto_tsquery('english', %s)) AS rank "
        "FROM itsm.tickets "
        "WHERE fts @@ plainto_tsquery('english', %s) "
        "ORDER BY rank DESC, ticket_id ASC "
        "LIMIT %s"
    )
    return sql, [query_text, query_text, limit]


def build_semantic_query(query_vector: list[float], *, limit: int) -> tuple[str, list]:
    """Semantic vector ranking: pgvector cosine distance over embedding.

    The query vector is a BOUND parameter (rendered as a vector literal by
    psycopg); never interpolated into the SQL string.
    """
    sql = (
        "SELECT ticket_id, embedding <=> %s::vector AS distance "
        "FROM itsm.tickets "
        "WHERE embedding IS NOT NULL "
        "ORDER BY distance ASC, ticket_id ASC "
        "LIMIT %s"
    )
    return sql, [_vector_literal(query_vector), limit]


def _vector_literal(vector: list[float]) -> str:
    """Render a validated float list as a pgvector text literal for binding."""
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


# ---------------------------------------------------------------------------
# Deterministic RRF fusion (research R8, k=60)
# ---------------------------------------------------------------------------


def rrf_fuse(lexical: list[tuple[int, float]],
             semantic: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Fuse two ranked sides with Reciprocal Rank Fusion (k=60).

    Each side is a list of (ticket_id, score) ordered best-first. A ticket's
    fused score is sum over sides of 1/(60 + rank), with rank assigned 1-based
    by position (best-first); a missing side contributes 0. The final ordering
    is fused score DESC with a deterministic tie-break on ticket_id ASC.
    Identical inputs produce identical rankings.
    """
    scores: dict[int, float] = {}
    for side in (lexical, semantic):
        for rank, (ticket_id, _score) in enumerate(side, start=1):
            scores[ticket_id] = scores.get(ticket_id, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------------------
# Governed retrieval execution (read-only role)
# ---------------------------------------------------------------------------


def _connect():
    return psycopg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT, user=READONLY_USER,
        password=READONLY_PASSWORD, dbname=POSTGRES_DB, connect_timeout=5)


def _rows(cur, sql: str, params: list) -> list[tuple[int, float]]:
    cur.execute(sql, params)
    return [(int(r[0]), float(r[1])) for r in cur.fetchall()]


def retrieve(request: RetrievalRequest, *,
             embed_query=None) -> dict:
    """Execute one governed hybrid retrieval and return the ranked result.

    `embed_query` is a callable text -> 768-dim vector used ONLY for
    mode="about" (the query text must be embedded by the pinned model). For
    mode="similar" the reference ticket's stored embedding is the semantic
    query vector and its text is the lexical query — no embedding call.

    Returns {"ticket_ids": [...], "scores": [...], "trace": [...]} with the
    sanitized retrieval trace listing exactly the ticket_ids that entered the
    model's context.
    """
    limit = request.limit
    with _connect() as conn, conn.cursor() as cur:
        if request.mode == "about":
            query_text = request.query_text
            if embed_query is None:
                raise RetrievalError(
                    "mode 'about' requires an embedding callable for the query text")
            qvec = embed_query(query_text)
        else:  # similar
            cur.execute(
                "SELECT embedding, "
                "concat_ws(' ', short_description, description, resolution_notes) "
                "FROM itsm.tickets WHERE ticket_id = %s",
                (request.ticket_id,))
            row = cur.fetchone()
            if row is None or row[0] is None:
                raise RetrievalError(
                    f"reference ticket {request.ticket_id} not found or has no embedding")
            stored, ref_text = row[0], row[1]
            qvec = _parse_stored_vector(stored)
            query_text = ref_text or ""

        lexical_sql, lexical_params = build_lexical_query(query_text, limit=limit)
        semantic_sql, semantic_params = build_semantic_query(qvec, limit=limit)
        lexical = _rows(cur, lexical_sql, lexical_params)
        semantic = _rows(cur, semantic_sql, semantic_params)

    fused = rrf_fuse(lexical, semantic)[:limit]
    ticket_ids = [tid for tid, _ in fused]
    scores = [score for _, score in fused]
    trace = [{"event": "retrieval", "ticket_ids": ticket_ids,
              "mode": request.mode}]
    return {"ticket_ids": ticket_ids, "scores": scores, "trace": trace}


def _parse_stored_vector(stored: object) -> list[float]:
    """Parse a pgvector value (text '[...]' or sequence) into floats."""
    if isinstance(stored, str):
        text = stored.strip().strip("[]")
        return [float(x) for x in text.split(",") if x.strip()]
    return [float(x) for x in stored]
