---
type: C4 Component
title: Evaluation runner (component)
status: stable
groma:
  id: run
  parent: script-run
  code:
    - scanner: python
      file: evaluation/run.py
  group: Evaluation & tuning
description: Held-out evaluation runner.
---

evaluation/run.py. See the container description. Executes every held-out case through the live pipeline and writes a versioned artifact.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [run](run.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Runs the live pipeline | DSPy (pinned local model) |
| [run](run.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Takes security snapshots | psycopg (itsm_owner role) |
