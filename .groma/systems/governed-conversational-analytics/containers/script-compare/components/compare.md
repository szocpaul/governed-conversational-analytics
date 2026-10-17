---
type: C4 Component
title: Comparison gate (component)
status: stable
groma:
  id: compare
  parent: script-compare
  code:
    - scanner: python
      file: evaluation/compare.py
  group: Evaluation & tuning
description: Regression comparison gate.
---

evaluation/compare.py. See the container description. Compares baseline and current artifacts and returns an exit code.
