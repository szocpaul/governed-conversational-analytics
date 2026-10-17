---
type: C4 Component
title: LLM configuration & client
status: stable
groma:
  id: llm
  parent: web-application
  code:
    - scanner: python
      file: app/ai/llm.py
  group: Model & endpoints
description: Configures the pinned local LLM and provides the OpenAI-compatible chat-completion client.
---

Loads LLMConfig from the environment (provider, base_url, model, api_key, temperature, cache). list_models() and verify_model() call GET /v1/models to verify the exact model is loaded (no fallback). chat_completion() runs one deterministic completion. configure_dspy() sets up the DSPy LM with the native lm15 engine pin. REQUESTED_MODEL_ARTIFACT records the approved Qwen3.8-27B-UD-Q4_K_M.gguf. Any endpoint or model failure raises LLMEndpointError, which stops processing (no fallback).

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [llm](llm.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Verifies model and runs completions | OpenAI-compatible HTTP |
