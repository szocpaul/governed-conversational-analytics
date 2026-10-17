---
type: C4 Component
title: Embedding program
status: stable
groma:
  id: embeddings
  parent: script-generate-embeddings
  code:
    - scanner: python
      file: app/ai/embeddings.py
  group: Content pipeline
description: Per-ticket embedding client with strict acceptance and bounded retries.
---

app/ai/embeddings.py. The EmbeddingProgram embeds one ticket text (short_description + description + resolution_notes, joined by a recorded separator; NULL fields never replaced) with the pinned EmbeddingGemma-2 endpoint. Strict acceptance: dimension exactly 768, all values finite. Bounded identical-request retries, then EmbeddingError. Offline build-time module — never imported by the runtime query path.
