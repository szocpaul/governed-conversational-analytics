---
type: C4 Component
title: Count threshold calibration
status: stable
groma:
  id: count-calibration
  parent: script-count-calibration
  code:
    - scanner: python
      file: app/ai/count_calibration.py
description: Offline calibration of the semantic-match threshold used by the governed count over content.
---

app/ai/count_calibration.py is the offline calibration of the count-over-content threshold, and it is not part of the request path. calibrate_threshold() runs a deterministic distance sweep over the development count cases only: for each candidate cosine-distance threshold in the governed grid, every development count topic is embedded and the governed hybrid count is computed, and the threshold with the best development exact-count accuracy wins (ties break toward the larger, more inclusive threshold). The result is written to the versioned count-threshold.json artifact with the calibration method, the development case IDs used, and the SHA-256 of the canonical form; a development ID that also appears in the held-out set raises instead of being used.

At runtime the calibrated value is read from that artifact by the governed retrieval channel (load_count_threshold), which is why the web application never runs a sweep and never touches the held-out cases.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [count-calibration](count-calibration.md) | [embedding-endpoint](../../../../../externals/embedding-endpoint.md) | Embeds dev count topics | OpenAI-compatible HTTP |
| [count-calibration](count-calibration.md) | [postgresql-database](../../../../../externals/postgresql-database.md) | Runs governed hybrid count | psycopg (itsm_readonly role) |
| [app/ai/count_calibration.py](../../../../../../app/ai/count_calibration.py) | [evaluation/schemas.py](../../../../../../evaluation/schemas.py) | Reads the development count cases | Python (case library) |
