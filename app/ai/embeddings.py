"""Embedding client + per-ticket vector assembly (feature 010, research R2/R3/R5).

Offline build-time module ONLY — never imported by the runtime query path hot
loop. One 768-dimensional vector per ticket is produced by the pinned local
EmbeddingGemma-2 model (exact pinned API model ID, Q8_0, Apache-2.0) served by
a SEPARATE pinned llama.cpp instance started with --embeddings. No fallback
model, no hosted API.

Per-ticket input text (research R3): the concatenation of short_description +
description + resolution_notes, joined by the recorded TEXT_SEPARATOR constant.
For open tickets (resolution_notes None) only the available fields are used —
never a placeholder. Every accepted vector passes strict validation: dimension
exactly 768 and all values finite (research R5). Bounded identical-request
retries, then a loud EmbeddingError.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import httpx

# Recorded separator joining the text fields (research R3): a single newline.
TEXT_SEPARATOR = "\n"

# Governed constants (spec FR-003, contracts/artifact-schemas.md).
EMBEDDING_DIMENSION = 768
DEFAULT_MAX_RETRIES = 2

# Exact pinned API model ID (verified via GET /v1/models at preflight; see
# artifacts/embedding-preflight.json). No fallback.
PINNED_MODEL_ID = "models\\embeddinggemma-2-Q8_0.gguf"


class EmbeddingError(RuntimeError):
    """Raised when embedding fails after all bounded retries or validation."""


@dataclass(frozen=True)
class EmbeddingConfig:
    """Immutable embedding-endpoint configuration loaded from the environment."""

    provider: str
    base_url: str
    model: str
    api_key: str

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        return cls(
            provider=os.environ.get("EMBED_PROVIDER", "openai-compatible"),
            base_url=os.environ.get("EMBED_BASE_URL", "").rstrip("/"),
            model=os.environ.get("EMBED_MODEL", ""),
            api_key=os.environ.get("EMBED_API_KEY", "local-not-required"),
        )


def build_ticket_text(ticket: dict) -> str:
    """Return the embedding input text for one ticket (research R3).

    Concatenates short_description + description + resolution_notes with the
    recorded separator. For open tickets (resolution_notes None) only the
    available fields are joined; a NULL field is never replaced with a
    placeholder.
    """
    parts = [ticket["short_description"], ticket["description"]]
    notes = ticket.get("resolution_notes")
    if notes is not None:
        parts.append(notes)
    return TEXT_SEPARATOR.join(parts)


def accept_vector(vector: object) -> list[float]:
    """Strictly validate one embedding vector (research R5).

    Requires dimension exactly EMBEDDING_DIMENSION and all-finite numeric
    values. Returns the vector as a list of floats; raises ValueError
    otherwise. Never patches, fabricates, or skips.
    """
    if not isinstance(vector, (list, tuple)):
        raise ValueError("embedding is not a list of numbers")
    if len(vector) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"embedding dimension {len(vector)} != {EMBEDDING_DIMENSION}")
    out: list[float] = []
    for v in vector:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"embedding value {v!r} is not numeric")
        fv = float(v)
        if not math.isfinite(fv):
            raise ValueError("embedding contains a non-finite value")
        out.append(fv)
    return out


class EmbeddingProgram:
    """Per-ticket embedding with strict acceptance and bounded retries.

    An httpx.Client may be injected (tests use a scripted MockTransport);
    otherwise one is built from the configured endpoint. The request always
    names the exact pinned model ID — never a substitute.
    """

    def __init__(self, model: str = PINNED_MODEL_ID, *,
                 config: EmbeddingConfig | None = None,
                 client: httpx.Client | None = None,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 timeout: float = 120.0):
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self._config = config
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        config = self._config or EmbeddingConfig.from_env()
        if not config.base_url:
            raise EmbeddingError("EMBED_BASE_URL is not configured")
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.api_key}",
                     "Content-Type": "application/json"},
            timeout=self.timeout)
        return self._client

    def _embed_once(self, text: str) -> list[float]:
        client = self._get_client()
        # A configured client carries the endpoint base_url, so the relative
        # path resolves against it. An injected test client (MockTransport)
        # has no base_url, so use an absolute placeholder URL there.
        url = ("/embeddings" if str(client.base_url)
               else "http://embeddings.local/v1/embeddings")
        resp = client.post(url, json={"model": self.model, "input": text})
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data")
        if not isinstance(items, list) or not items:
            raise EmbeddingError("embedding response has no data")
        vector = items[0].get("embedding")
        return accept_vector(vector)

    def embed_ticket(self, ticket: dict) -> list[float]:
        """Embed one ticket with bounded identical-request retries.

        Retries the identical request up to max_retries times on any
        failure, then raises EmbeddingError naming the ticket.
        """
        text = build_ticket_text(ticket)
        last_error: Exception | None = None
        for _attempt in range(1 + self.max_retries):
            try:
                return self._embed_once(text)
            except Exception as exc:  # noqa: BLE001 - normalized below
                last_error = exc
        raise EmbeddingError(
            f"ticket {ticket.get('ticket_id')}: embedding failed after "
            f"{1 + self.max_retries} attempts: "
            f"{type(last_error).__name__}: {last_error}") from last_error
