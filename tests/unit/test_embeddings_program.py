"""T004: Unit tests for the embedding program (stubbed embedding endpoint).

The embedding endpoint is stubbed with scripted HTTP responses (httpx
MockTransport); the per-ticket text assembly, strict vector acceptance
(dimension exactly 768, all-finite), and bounded-retry logic under test are
real. The shipped artifact only ever comes from a real recorded run
(research R12).
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys

import httpx
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MODULE_PATH = os.path.join(REPO_ROOT, "app", "ai", "embeddings.py")

PINNED_MODEL = "models\\embeddinggemma-2-Q8_0.gguf"
DIM = 768


def _load_module():
    spec = importlib.util.spec_from_file_location("app.ai.embeddings", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def emb():
    return _load_module()


def _vec(dim=DIM, fill=0.01):
    return [fill] * dim


def _embedding_response(vec, model=PINNED_MODEL):
    return {"object": "list", "data": [{"object": "embedding", "index": 0,
                                        "embedding": vec}],
            "model": model, "usage": {"prompt_tokens": 3, "total_tokens": 3}}


def _client(handler):
    """An httpx.Client bound to a scripted MockTransport handler."""
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# Per-ticket input text assembly (research R3)
# ---------------------------------------------------------------------------

def test_build_ticket_text_all_fields(emb):
    ticket = {"ticket_id": 1,
              "short_description": "The VPN drops.",
              "description": "Users cannot connect.",
              "resolution_notes": "The gateway was restarted."}
    text = emb.build_ticket_text(ticket)
    assert text == ("The VPN drops." + emb.TEXT_SEPARATOR
                    + "Users cannot connect." + emb.TEXT_SEPARATOR
                    + "The gateway was restarted.")


def test_build_ticket_text_open_ticket_omits_null_notes(emb):
    """Open ticket (resolution_notes None): only available fields, no placeholder."""
    ticket = {"ticket_id": 2,
              "short_description": "The VPN drops.",
              "description": "Users cannot connect.",
              "resolution_notes": None}
    text = emb.build_ticket_text(ticket)
    assert text == "The VPN drops." + emb.TEXT_SEPARATOR + "Users cannot connect."
    assert "None" not in text and "null" not in text.lower()


def test_separator_is_recorded_constant(emb):
    assert isinstance(emb.TEXT_SEPARATOR, str) and emb.TEXT_SEPARATOR


# ---------------------------------------------------------------------------
# Vector acceptance (research R5): dimension exactly 768, all finite
# ---------------------------------------------------------------------------

def test_valid_vector_accepted(emb):
    emb.accept_vector(_vec())  # does not raise


def test_wrong_dimension_rejected(emb):
    with pytest.raises(Exception):
        emb.accept_vector(_vec(dim=767))
    with pytest.raises(Exception):
        emb.accept_vector(_vec(dim=769))


def test_non_finite_vector_rejected(emb):
    v = _vec()
    v[10] = float("nan")
    with pytest.raises(Exception):
        emb.accept_vector(v)
    v = _vec()
    v[10] = float("inf")
    with pytest.raises(Exception):
        emb.accept_vector(v)


# ---------------------------------------------------------------------------
# Embedding call against the stubbed endpoint
# ---------------------------------------------------------------------------

def test_embed_ticket_happy_path(emb):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_embedding_response(_vec()))

    client = _client(handler)
    program = emb.EmbeddingProgram(model=PINNED_MODEL, client=client)
    ticket = {"ticket_id": 7, "short_description": "A", "description": "B",
              "resolution_notes": None}
    vec = program.embed_ticket(ticket)
    assert len(vec) == DIM
    # The request sent the exact pinned model and the concatenated text.
    assert seen["body"]["model"] == PINNED_MODEL
    assert seen["body"]["input"] == emb.build_ticket_text(ticket)


def test_malformed_http_response_rejected(emb):
    def handler(request):
        return httpx.Response(200, json={"data": [{"no_embedding": []}]})

    program = emb.EmbeddingProgram(model=PINNED_MODEL,
                                   client=_client(handler), max_retries=1)
    with pytest.raises(Exception):
        program.embed_ticket({"ticket_id": 1, "short_description": "A",
                              "description": "B", "resolution_notes": None})


def test_http_error_status_rejected(emb):
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    program = emb.EmbeddingProgram(model=PINNED_MODEL,
                                   client=_client(handler), max_retries=1)
    with pytest.raises(Exception):
        program.embed_ticket({"ticket_id": 1, "short_description": "A",
                              "description": "B", "resolution_notes": None})


def test_wrong_dimension_response_rejected(emb):
    def handler(request):
        return httpx.Response(200, json=_embedding_response(_vec(dim=100)))

    program = emb.EmbeddingProgram(model=PINNED_MODEL,
                                   client=_client(handler), max_retries=1)
    with pytest.raises(Exception):
        program.embed_ticket({"ticket_id": 1, "short_description": "A",
                              "description": "B", "resolution_notes": None})


# ---------------------------------------------------------------------------
# Bounded identical-request retries, then a loud exception
# ---------------------------------------------------------------------------

def test_retries_then_succeeds(emb):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, json={"error": "transient"})
        return httpx.Response(200, json=_embedding_response(_vec()))

    program = emb.EmbeddingProgram(model=PINNED_MODEL,
                                   client=_client(handler), max_retries=2)
    vec = program.embed_ticket({"ticket_id": 1, "short_description": "A",
                                "description": "B", "resolution_notes": None})
    assert len(vec) == DIM
    assert calls["n"] == 3  # 1 initial + 2 retries


def test_retries_exhausted_raises(emb):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500, json={"error": "always"})

    program = emb.EmbeddingProgram(model=PINNED_MODEL,
                                   client=_client(handler), max_retries=2)
    with pytest.raises(emb.EmbeddingError):
        program.embed_ticket({"ticket_id": 1, "short_description": "A",
                              "description": "B", "resolution_notes": None})
    assert calls["n"] == 3  # 1 + max_retries


def test_no_fallback_model_sent(emb):
    """The request always names the exact pinned model; never a substitute."""
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_embedding_response(_vec()))

    program = emb.EmbeddingProgram(model=PINNED_MODEL, client=_client(handler))
    program.embed_ticket({"ticket_id": 1, "short_description": "A",
                          "description": "B", "resolution_notes": None})
    assert seen["body"]["model"] == PINNED_MODEL
