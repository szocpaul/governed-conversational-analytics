---
type: C4 Component
title: Example verification (component)
status: stable
groma:
  id: verify-examples
  parent: script-verify-examples
  code:
    - scanner: python
      file: evaluation/verify_examples.py
  group: Evaluation & tuning
description: Verification of the curated demo UI example questions.
---

evaluation/verify_examples.py. Runs each curated example question through the live pipeline and checks correctness. Used for the feature 008 gate.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [verify-examples](verify-examples.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Runs example questions through pipeline | DSPy (pinned local model) |
