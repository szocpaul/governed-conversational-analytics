---
type: C4 Container
title: Generate embeddings
status: stable
groma:
  id: script-generate-embeddings
  parent: governed-conversational-analytics
description: Offline pipeline that embeds each ticket text into a 768-dimensional vector.
---

Runs the EmbeddingProgram (app/ai/embeddings.py) over the pinned ticket texts. For each ticket, the concatenated text (short_description + description + resolution_notes, joined by a recorded separator; NULL fields never replaced with a placeholder) is embedded by the pinned EmbeddingGemma-2 model into one 768-dimensional vector. Strict acceptance: dimension exactly 768, all values finite. Bounded retries, then a loud error. Checkpointed and resumable. Writes the embeddings to a pinned JSONL artifact with a provenance manifest (including source_gguf_sha256).

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [script-generate-embeddings](container.md) | [embedding-endpoint](../../../../externals/embedding-endpoint.md) | Embeds the ticket texts | OpenAI-compatible HTTP |
