---
type: C4 Actor
title: Operator
status: stable
groma:
  id: operator
---

A maintainer or operator who configures the pinned local LLM and embedding endpoints, runs the offline data/text/embedding pipelines, performs model preflight, and executes the evaluation and optimization toolkit to verify quality and security.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [operator](operator.md) | [script-initialize-database](../systems/governed-conversational-analytics/containers/script-initialize-database/container.md) | Runs database setup | Python (psycopg) |
| [operator](operator.md) | [script-import-dataset](../systems/governed-conversational-analytics/containers/script-import-dataset/container.md) | Imports the dataset | Python (psycopg) |
| [operator](operator.md) | [evaluation](../systems/governed-conversational-analytics/containers/evaluation/container.md) | Runs the evaluation | Python (DSPy) |
| [operator](operator.md) | [script-optimization](../systems/governed-conversational-analytics/containers/script-optimization/container.md) | Runs optimization | Python (DSPy) |
| [operator](operator.md) | [script-preflight](../systems/governed-conversational-analytics/containers/script-preflight/container.md) | Runs model preflight | Python (httpx) |
| [operator](operator.md) | [llm](../systems/governed-conversational-analytics/containers/web-application/components/llm.md) | Configures the LLM endpoint | Environment variables |
| [operator](operator.md) | [embedding-endpoint](../externals/embedding-endpoint.md) | Configures the embedding endpoint | Environment variables |
| [operator](operator.md) | [script-generate-ticket-texts](../systems/governed-conversational-analytics/containers/script-generate-ticket-texts/container.md) | Runs the ticket-text generation | Python (DSPy) |
| [operator](operator.md) | [script-generate-embeddings](../systems/governed-conversational-analytics/containers/script-generate-embeddings/container.md) | Runs the embedding generation | Python (httpx) |
| [operator](operator.md) | [script-validate-ticket-texts](../systems/governed-conversational-analytics/containers/script-validate-ticket-texts/container.md) | Runs the ticket-text validation suite | Python |
| [operator](operator.md) | [script-count-calibration](../systems/governed-conversational-analytics/containers/script-count-calibration/container.md) | Runs the count-threshold calibration | Python (DSPy) |
| [operator](operator.md) | [script-reset-database](../systems/governed-conversational-analytics/containers/script-reset-database/container.md) | Resets the local database | Python (psycopg) |
