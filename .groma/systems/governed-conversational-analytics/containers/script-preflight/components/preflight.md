---
type: C4 Component
title: Model preflight
status: stable
groma:
  id: preflight
  parent: script-preflight
  code:
    - scanner: python
      file: app/ai/preflight.py
description: Model preflight for the pinned local LLM endpoint.
---

app/ai/preflight.py verifies the pinned local LLM before any model-dependent work, with no fallback at any step: GET /v1/models must return the exact requested model ID, one deterministic chat completion must succeed, and one typed DSPy prediction must succeed. It saves the non-secret metadata to artifacts/llm-preflight.json and records the private endpoint only as a host-redacted presence flag. The entry point returns exit code 0 on success and 1 on any verification failure, which is a stop-and-report condition.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [preflight](preflight.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Verifies endpoint and model | OpenAI-compatible HTTP |
