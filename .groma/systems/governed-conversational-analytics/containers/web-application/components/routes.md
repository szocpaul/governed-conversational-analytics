---
type: C4 Component
title: Query routes & pipeline orchestration
status: stable
groma:
  id: routes
  parent: web-application
  code:
    - scanner: python
      file: app/api/routes.py
  group: API & UI
description: FastAPI routes that orchestrate the full conversational query flow with a request safety timeout.
---

The POST /query endpoint submits the request to a bounded thread pool with an overall request safety timeout (default 120s). The pipeline: injection telemetry -> DSPy classify+plan -> route by category (content_about/content_similar -> governed retrieval; content_count -> governed hybrid count; ambiguous/unsupported -> stable category; supported -> validate -> GraphJin execute -> normalize -> apply_having -> null-ratio check -> grounded answer -> redact). Every stage failure yields a stable dependency_error or clarification, never a fabricated answer. The optimized program (app/ai/optimized_program.json) is loaded when present, with best-effort fallback to the base program.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [routes](routes.md) | [graphjin](../../../../../externals/graphjin.md) | Executes governed GraphQL queries | HTTP GraphQL |
| [routes](routes.md) | [embedding-endpoint](../../../../../externals/embedding-endpoint.md) | Embeds retrieval query text | OpenAI-compatible HTTP |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/ai/query_program.py](../../../../../../app/ai/query_program.py) | Classifies and plans the question | Python (DSPy) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/ai/retrieval.py](../../../../../../app/ai/retrieval.py) | Runs governed retrieval | Python (psycopg) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/ai/routing.py](../../../../../../app/ai/routing.py) | Extracts ticket_id | Python (pure function) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/ai/count_calibration.py](../../../../../../app/ai/count_calibration.py) | Loads count threshold | Python (file read) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/security/validator.py](../../../../../../app/security/validator.py) | Validates the request | Python (pure function) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/data/graphjin_client.py](../../../../../../app/data/graphjin_client.py) | Executes governed query | Python (httpx) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/data/result_normalizer.py](../../../../../../app/data/result_normalizer.py) | Normalizes evidence | Python (pure function) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/ai/answer_program.py](../../../../../../app/ai/answer_program.py) | Generates grounded answer | Python (DSPy) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/security/classifier.py](../../../../../../app/security/classifier.py) | Records injection telemetry | Python (regex) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/security/redaction.py](../../../../../../app/security/redaction.py) | Redacts user-facing output | Python (regex) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/observability/trace.py](../../../../../../app/observability/trace.py) | Records trace events | Python (in-memory) |
| [routes](routes.md) | [analyst](../../../../../actors/analyst.md) | Returns the grounded answer | HTTP JSON (FastAPI) |
| [app/api/routes.py](../../../../../../app/api/routes.py) | [app/ai/embeddings.py](../../../../../../app/ai/embeddings.py) | Embeds the retrieval and count topic text | Python (httpx) |
