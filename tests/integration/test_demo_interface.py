"""Demo interface tests (spec 004, T008, US4).

Written BEFORE app/web/. The FastAPI-served UI must show answer/refusal,
a sanitized trace, and observational latency for every completed request
(FR-010, SC-008). The UI must never expose the private LLM endpoint,
credentials, or canaries.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "app", "web")


def test_web_assets_exist():
    for name in ("index.html", "app.js", "styles.css"):
        assert os.path.exists(os.path.join(WEB_DIR, name)), name


def test_root_serves_ui():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Governed" in resp.text or "ITSM" in resp.text


def test_ui_static_assets_served():
    with TestClient(app) as client:
        for path in ("/static/app.js", "/static/styles.css"):
            resp = client.get(path)
            assert resp.status_code == 200, path


def test_ui_does_not_embed_private_endpoint():
    with TestClient(app) as client:
        html = client.get("/").text
        js = client.get("/static/app.js").text
    for blob in (html, js):
        assert "tailee6bc1" not in blob
        assert "8033" not in blob
        assert "CANARY" not in blob


def test_query_endpoint_returns_trace_and_latency_for_ui():
    """Every completed request exposes trace + latency for the UI (SC-008)."""
    with TestClient(app) as client:
        resp = client.post(
            "/query", json={"question": "How many tickets are there?"})
        assert resp.status_code == 200
        payload = resp.json()
        assert "status" in payload
        assert "trace" in payload and isinstance(payload["trace"], list)
        assert "latency_ms" in payload and payload["latency_ms"] >= 0
        # Trace is sanitized: no private endpoint.
        assert "tailee6bc1" not in resp.text


# ---------------------------------------------------------------------------
# spec 008 (T003): query-discovery UI contract. Written BEFORE the markup
# exists; these tests define the DOM hooks from contracts/ui-contract.md.
# ---------------------------------------------------------------------------


def test_examples_json_served():
    """GET /static/examples.json returns the curated gallery (FR-008)."""
    import json

    with TestClient(app) as client:
        resp = client.get("/static/examples.json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        body = json.loads(resp.text)
        assert isinstance(body["categories"], list) and body["categories"]
        assert isinstance(body["examples"], list) and body["examples"]


def test_overview_card_names_all_subjects():
    """#dataset-overview names tickets, merchants, agents (FR-004)."""
    with TestClient(app) as client:
        html = client.get("/").text
    assert 'id="dataset-overview"' in html
    overview = html.split('id="dataset-overview"', 1)[1]
    for subject in ("tickets", "merchants", "agents"):
        assert subject in overview, subject


def test_gallery_markup_hooks_present():
    """Gallery toggle/panel and suggestions container exist (contract)."""
    with TestClient(app) as client:
        html = client.get("/").text
    for hook in ('id="gallery-toggle"', 'id="gallery"', 'id="suggestions"'):
        assert hook in html, hook


def test_served_assets_do_not_leak_prohibited_strings():
    """FR-009: no-leak assertions extended to /static/examples.json."""
    with TestClient(app) as client:
        blobs = [
            client.get("/").text,
            client.get("/static/app.js").text,
            client.get("/static/styles.css").text,
            client.get("/static/examples.json").text,
        ]
    for blob in blobs:
        assert "tailee6bc1" not in blob
        assert "8033" not in blob
        assert "CANARY" not in blob
