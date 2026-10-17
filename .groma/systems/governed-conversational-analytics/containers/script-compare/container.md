---
type: C4 Container
title: Regression comparison gate
status: stable
groma:
  id: script-compare
  parent: governed-conversational-analytics
description: Compares a baseline artifact against a current artifact and returns an exit code.
---

Returns non-zero for: failed P1 quality thresholds (structural validity < 0.90, execution accuracy < 0.80), execution-accuracy degradation > 5 percentage points, any prohibited database effect, any unauthorized disclosure, or incompatible pinned metadata. Routing and count gates use calibrated thresholds that clear the observed noise band. Latency is observational only and NEVER fails the gate.
