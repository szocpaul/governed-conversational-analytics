---
type: C4 Container
title: Evaluation toolkit
status: stable
groma:
  id: evaluation
  parent: governed-conversational-analytics
description: Command-line toolkit that measures the live governed pipeline over held-out cases and gates regressions.
---

One command-line toolkit (evaluation/) that measures the live governed pipeline over held-out cases. Its entry points share one case library and one set of deterministic metrics:

- `evaluation/run.py` executes every held-out case through the live pipeline with temperature 0 and cache disabled, snapshots PostgreSQL before and after each case to detect prohibited effects, and writes a versioned artifact with per-case results and separately computed metrics.
- `evaluation/metrics.py` computes the deterministic, model-free metrics: structural validity, execution accuracy, routing accuracy, count accuracy, and the security effect and disclosure checks. Latency is observational only.
- `evaluation/compare.py` is the regression gate. It returns a non-zero exit code for a failed quality threshold, an execution-accuracy degradation greater than 5 percentage points, any prohibited database effect, or any unauthorized disclosure.
- `evaluation/run_security.py` runs the security cases and judges them by backend effects and disclosure, never by refusal wording.
- `evaluation/verify_examples.py` runs the curated demo-UI example questions through the live pipeline and checks that every answer is correct and grounded.
- `evaluation/cross_version_report.py` compares the pre-upgrade and post-upgrade evaluation artifacts for the DSPy upgrade gate.

The toolkit drives the running application in-process through the FastAPI test client, so every measurement exercises the same pipeline the analyst uses.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [evaluation](container.md) | [local-llm-endpoint](../../../../externals/local-llm-endpoint.md) | Runs the live pipeline for every case | DSPy (pinned local model) |
| [evaluation](container.md) | [postgresql-database](../../../../externals/postgresql-database.md) | Snapshots the database around every case | psycopg (itsm_owner role) |
| [evaluation](container.md) | [operator](../../../../actors/operator.md) | Reports the metrics and the gate result | Python (CLI output) |
