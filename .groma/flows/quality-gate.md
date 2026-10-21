---
type: Groma Flow
title: Quality and security gate
groma:
  id: quality-gate
---

The operator measures the live pipeline and gates a change. The evaluation toolkit runs the held-out cases through the running application with the pinned model, snapshots the database around every case to detect prohibited effects, computes the deterministic metrics, and compares the resulting artifact with the baseline.

## Steps

| From | To | Action |
| --- | --- | --- |
| [Operator](../actors/operator.md) | [Evaluation toolkit](../systems/governed-conversational-analytics/containers/evaluation/container.md) | Run the held-out evaluation |
| [Evaluation toolkit](../systems/governed-conversational-analytics/containers/evaluation/container.md) | [Local LLM endpoint](../externals/local-llm-endpoint.md) | Call the pinned model for every case |
| [Evaluation toolkit](../systems/governed-conversational-analytics/containers/evaluation/container.md) | [PostgreSQL](../externals/postgresql-database.md) | Snapshot the database around every case |
| [Evaluation toolkit](../systems/governed-conversational-analytics/containers/evaluation/container.md) | [Operator](../actors/operator.md) | Report the metrics and the gate result |
