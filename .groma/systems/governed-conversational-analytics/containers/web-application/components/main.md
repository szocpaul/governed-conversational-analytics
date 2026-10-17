---
type: C4 Component
title: FastAPI application entrypoint
status: stable
groma:
  id: main
  parent: web-application
  code:
    - scanner: python
      file: app/main.py
    - scanner: python
      file: app/__init__.py
  group: API & UI
description: Creates the FastAPI app, configures the pinned LLM at startup, and serves the demo UI.
---

Loads .env, configures the pinned local LLM at startup (no fallback). If the endpoint or model cannot be verified, the app still starts so /health works, but the query path reports a stable dependency_error. Serves the demo UI (index.html) at / and static assets at /static. The query path is unchanged by the UI wiring.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [app/main.py](../../../../../../app/main.py) | [app/ai/llm.py](../../../../../../app/ai/llm.py) | Configures pinned LLM | Python (DSPy) |
| [app/main.py](../../../../../../app/main.py) | [app/api/routes.py](../../../../../../app/api/routes.py) | Includes query router | Python (FastAPI) |
