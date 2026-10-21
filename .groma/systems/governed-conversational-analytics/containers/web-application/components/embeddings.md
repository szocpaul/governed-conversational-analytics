---
type: C4 Component
title: Embedding client
status: stable
groma:
  id: embeddings
  parent: web-application
  code:
    - scanner: python
      file: app/ai/embeddings.py
  group: Model & endpoints
description: Shared embedding client for ticket texts and query text, used offline and at runtime.
---

app/ai/embeddings.py owns the one embedding client of the project. The EmbeddingProgram embeds a single text with the pinned EmbeddingGemma-2 endpoint and accepts the result only when the vector has exactly 768 dimensions and all values are finite; a rejected result is retried a bounded number of times and then raises EmbeddingError. There is no fallback model.

The same client serves two callers, which is why it lives in the application package: the offline embedding pipeline embeds each ticket text (short_description + description + resolution_notes, joined by a recorded separator, NULL fields never replaced), and the runtime query path embeds the retrieval and count topic text before the governed retrieval channel runs. build_ticket_text() joins the three ticket text fields for the offline builder.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [embeddings](embeddings.md) | [embedding-endpoint](../../../../../externals/embedding-endpoint.md) | Embeds ticket texts and query text | OpenAI-compatible HTTP |
