---
type: C4 Component
title: Security evaluation runner
status: stable
groma:
  id: run-security
  parent: evaluation
  code:
    - scanner: python
      file: evaluation/run_security.py
  group: Evaluation commands
description: Security case runner that judges security by effects and disclosure.
---

`evaluation/run_security.py` runs every case in evaluation/security_cases.json through the live pipeline, or through the relevant layer for the direct-unsafe cases. It judges security by what actually happened: it takes PostgreSQL snapshots around each case to detect prohibited database effects, and it checks the responses, traces, and error messages for unauthorized disclosure and for seeded canary values. It also measures the false-refusal rate on legitimate requests, so over-blocking is reported next to real leaks. The results are written to artifacts/security-results.json.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [run-security](run-security.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Takes security snapshots | psycopg (itsm_owner role) |
