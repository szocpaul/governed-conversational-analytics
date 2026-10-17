---
type: C4 System
title: Embedding endpoint
status: stable
groma:
  id: embedding-endpoint
  technology: llama.cpp (OpenAI-compatible), EmbeddingGemma-2 Q8_0 GGUF
---

A separate pinned llama.cpp instance started with --embeddings. Produces 768-dimensional vectors for ticket texts (offline pipeline) and for retrieval query text (runtime). Strict acceptance: dimension exactly 768, all values finite. No fallback model.
