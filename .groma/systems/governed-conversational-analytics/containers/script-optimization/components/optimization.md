---
type: C4 Component
title: Optimization (component)
status: stable
groma:
  id: optimization
  parent: script-optimization
  code:
    - scanner: python
      file: app/ai/optimization.py
  group: Evaluation & tuning
description: Bounded BootstrapFewShot optimization on development cases only.
---

app/ai/optimization.py. See the container description. Runs the approved dspy.BootstrapFewShot optimizer with the bounded configuration. Saves the optimized program and a run artifact with provenance.

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [optimization](optimization.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Runs BootstrapFewShot optimization | DSPy (pinned local model) |
