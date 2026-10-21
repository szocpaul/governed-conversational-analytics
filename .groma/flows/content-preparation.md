---
type: Groma Flow
title: Content preparation
groma:
  id: content-preparation
---

The operator prepares the governed content data before the import: the synthetic ticket texts are generated with the pinned local model, validated by the deterministic offline suite, turned into one embedding vector per ticket, and finally imported atomically together with the pinned CSV rows.

## Steps

| From | To | Action |
| --- | --- | --- |
| [Operator](../actors/operator.md) | [Generate ticket texts](../systems/governed-conversational-analytics/containers/script-generate-ticket-texts/container.md) | Generate the synthetic ticket texts |
| [Generate ticket texts](../systems/governed-conversational-analytics/containers/script-generate-ticket-texts/container.md) | [Local LLM endpoint](../externals/local-llm-endpoint.md) | Generate the short description, description, and resolution notes |
| [Operator](../actors/operator.md) | [Validate ticket texts](../systems/governed-conversational-analytics/containers/script-validate-ticket-texts/container.md) | Check schema, coverage, length, language, category, and the null rule |
| [Operator](../actors/operator.md) | [Generate embeddings](../systems/governed-conversational-analytics/containers/script-generate-embeddings/container.md) | Embed each ticket text |
| [Generate embeddings](../systems/governed-conversational-analytics/containers/script-generate-embeddings/container.md) | [Embedding endpoint](../externals/embedding-endpoint.md) | Produce one 768-dimensional vector per ticket |
| [Operator](../actors/operator.md) | [Import dataset](../systems/governed-conversational-analytics/containers/script-import-dataset/container.md) | Import the rows, the texts, and the embeddings atomically |
| [Import dataset](../systems/governed-conversational-analytics/containers/script-import-dataset/container.md) | [PostgreSQL](../externals/postgresql-database.md) | Store the rows in the itsm schema |
