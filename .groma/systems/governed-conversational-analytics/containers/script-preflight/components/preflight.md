---
type: C4 Component
title: Preflight (component)
status: stable
groma:
  id: preflight
  parent: script-preflight
  code:
    - scanner: python
      file: app/ai/preflight.py
  group: Evaluation & tuning
description: Model preflight for the pinned local LLM endpoint.
---

app/ai/preflight.py. See the container description. Verifies the endpoint, model, chat completion, and typed DSPy prediction. Saves non-secret metadata to artifacts/llm-preflight.json.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [preflight](preflight.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Verifies endpoint and model | OpenAI-compatible HTTP |
