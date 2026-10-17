---
type: C4 Container
title: Model preflight
status: stable
groma:
  id: script-preflight
  parent: governed-conversational-analytics
description: Verifies the pinned local LLM endpoint and model before any model-dependent work.
---

In order, with NO fallback: (1) GET /v1/models returns the exact requested model ID, (2) one deterministic chat completion succeeds, (3) one typed DSPy prediction succeeds. Saves non-secret metadata to artifacts/llm-preflight.json. The private endpoint URL is recorded only as a host-redacted presence flag. Exit code 0 on success, 1 on any verification failure (stop-and-report).
