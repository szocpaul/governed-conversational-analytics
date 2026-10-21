---
type: C4 System
title: Local LLM endpoint
status: stable
groma:
  id: local-llm-endpoint
  technology: llama.cpp (OpenAI-compatible), approved artifact openai/models/Qwen3.8-27B-UD-Q4_K_M.gguf
---

The pinned local chat-completion endpoint. Serves the exact requested model via GET /v1/models; the DSPy planner, classifier, and answer program call it with temperature 0 and cache disabled. No fallback model or provider is permitted; a missing endpoint or model yields a stable dependency error.
