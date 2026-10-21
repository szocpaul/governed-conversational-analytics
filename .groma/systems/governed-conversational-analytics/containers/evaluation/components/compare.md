---
type: C4 Component
title: Regression comparison gate
status: stable
groma:
  id: compare
  parent: evaluation
  code:
    - scanner: python
      file: evaluation/compare.py
  group: Evaluation commands
description: Regression comparison gate between the baseline and the current artifact.
---

`evaluation/compare.py` compares the baseline artifact with the current artifact and returns the exit code of the quality gate. It fails for a failed P1 quality threshold (structural validity below 0.90, execution accuracy below 0.80), an execution-accuracy degradation greater than 5 percentage points, any prohibited database effect, or any unauthorized disclosure. The routing and count gates use calibrated thresholds that clear the observed noise band. Latency is observational only and never fails the gate.
