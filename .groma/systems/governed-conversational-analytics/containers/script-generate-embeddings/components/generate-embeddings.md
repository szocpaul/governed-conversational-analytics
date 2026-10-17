---
type: C4 Component
title: Generate embeddings (script)
status: stable
groma:
  id: generate-embeddings
  parent: script-generate-embeddings
  code:
    - scanner: python
      file: scripts/generate_embeddings.py
  group: Content pipeline
description: Entry point for the offline embedding generation pipeline.
---

scripts/generate_embeddings.py. Loads the pinned ticket texts, embeds each with the EmbeddingProgram (pinned EmbeddingGemma-2 endpoint), and writes the embeddings to data/raw/tickets_embeddings.jsonl and a provenance manifest (data/raw/embeddings-manifest.json). Checkpointed and resumable. Records source_gguf_sha256 in the manifest.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [generate-embeddings](generate-embeddings.md) | [embedding-endpoint](../../../../../externals/embedding-endpoint.md) | Embeds ticket texts | OpenAI-compatible HTTP |
