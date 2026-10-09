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
