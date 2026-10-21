---
type: C4 Component
title: Example verification
status: stable
groma:
  id: verify-examples
  parent: evaluation
  code:
    - scanner: python
      file: evaluation/verify_examples.py
  group: Evaluation commands
description: Verification of the curated demo UI example questions against the live pipeline.
---

`evaluation/verify_examples.py` runs the curated example questions from app/web/examples.json through the live pipeline and checks that each answer is correct and grounded in the executed result. It covers the plain-language examples, the labeled refusal example, and the content-search examples added with the hybrid-search features. It writes artifacts/examples-verification.json and is the gate for the query discovery UI feature.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [verify-examples](verify-examples.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Runs example questions through pipeline | DSPy (pinned local model) |
