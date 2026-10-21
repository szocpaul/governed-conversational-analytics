---
type: C4 Container
title: Web application
status: draft
groma:
  id: web-application
  parent: governed-conversational-analytics
description: 'FastAPI service that orchestrates the conversational query pipeline: classification, typed planning, deterministic validation, governed execution, and grounded answering.'
---

The FastAPI web app (app/main.py) serves the demo UI and the POST /query endpoint. On startup it configures the pinned local LLM (no fallback); if the endpoint or the model cannot be verified the app still starts so that /health works, but the query path reports a stable dependency error.

The /query route runs the whole pipeline inside an overall request safety timeout: injection telemetry, DSPy classification and typed planning, a deterministic validator, the read-only GraphJin GraphQL client for structured questions, result normalization, the grounded answer program, and deterministic redaction of everything the analyst sees. Content questions (content_about, content_similar, content_count) route to the governed hybrid retrieval channel, which runs parameterized SQL directly as the itsm_readonly role over the generated ticket text fields instead of going through GraphJin; the count path uses the calibrated semantic threshold that the offline calibration wrote to count-threshold.json. The shared embedding client embeds the retrieval and count topic text.

The demo UI is static: app/web/index.html and app/web/styles.css are served at /, app/web/app.js posts the question to /query and renders the answer, the sanitized trace, and the observational latency, and app/web/examples.json holds the curated example gallery.

The components are grouped by domain: Query pipeline, Security controls, Data access, Model and endpoints, and API and UI.
