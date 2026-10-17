---
type: C4 Component
title: Security runner (component)
status: stable
groma:
  id: run-security
  parent: script-run-security
  code:
    - scanner: python
      file: evaluation/run_security.py
  group: Evaluation & tuning
description: Security evaluation runner.
---

evaluation/run_security.py. See the container description. Executes security cases and verifies backend effects and disclosure.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [run-security](run-security.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Takes security snapshots | psycopg (itsm_owner role) |
