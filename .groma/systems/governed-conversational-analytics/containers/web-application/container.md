---
type: C4 Container
title: Web application
status: draft
groma:
  id: web-application
  parent: governed-conversational-analytics
description: 'FastAPI service that orchestrates the conversational query pipeline: classification, typed planning, deterministic validation, governed execution, and grounded answering.'
---

The FastAPI web app (app/main.py) serves the demo UI and the POST /query endpoint. On startup it configures the pinned local LLM (no fallback). The /query route runs the full pipeline: an injection-telemetry classifier, a DSPy classifier + planner, a deterministic validator, a read-only GraphJin GraphQL client, result normalization, and a grounded answer generator. Content questions (content_about, content_similar, content_count) route to a governed hybrid retrieval channel that runs parameterized SQL directly as the itsm_readonly role (not through GraphJin) over the generated text fields. An overall request safety timeout bounds the whole request. Every user-facing string passes through deterministic redaction. Components are grouped by domain: Query pipeline, Security controls, Data access, Model & endpoints, and API & UI.
