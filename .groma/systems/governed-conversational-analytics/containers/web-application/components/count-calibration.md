---
type: C4 Component
title: Count calibration (component)
status: stable
groma:
  id: count-calibration
  parent: web-application
  code:
    - scanner: python
      file: app/ai/count_calibration.py
  group: Evaluation & tuning
description: Deterministic semantic-threshold calibration for count over content.
---

app/ai/count_calibration.py. See the container description. Runs calibrate_threshold() over dev count cases only and writes the versioned count-threshold.json artifact.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [count-calibration](count-calibration.md) | [embedding-endpoint](../../../../../externals/embedding-endpoint.md) | Embeds dev count topics | OpenAI-compatible HTTP |
| [count-calibration](count-calibration.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Runs governed hybrid count | psycopg (itsm_readonly role) |
