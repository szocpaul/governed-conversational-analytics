---
type: C4 Component
title: Held-out evaluation runner
status: stable
groma:
  id: run
  parent: evaluation
  code:
    - scanner: python
      file: evaluation/run.py
  group: Evaluation commands
description: Held-out evaluation runner that writes the versioned current artifact.
---

`evaluation/run.py` is the held-out evaluation entry point. It runs every case in evaluation/cases.json through the live pipeline with the pinned model, temperature 0, and cache disabled, and writes a versioned artifact (artifacts/current.json) with the pinned metadata, the per-case results, and the deterministic metrics computed separately by the metrics module. It takes a PostgreSQL snapshot before and after each case so that any prohibited database effect is detected, and it records latency observationally. The same entry point produces the baseline artifact that the comparison gate reads.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [run](run.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Runs the live pipeline | DSPy (pinned local model) |
| [run](run.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Takes security snapshots | psycopg (itsm_owner role) |
| [evaluation/run.py](../../../../../../evaluation/run.py) | [app/api/routes.py](../../../../../../app/api/routes.py) | Drives the live pipeline for every case | Python (FastAPI test client) |
