---
type: C4 Component
title: Trace & latency recorder
status: stable
groma:
  id: trace
  parent: web-application
  code:
    - scanner: python
      file: app/observability/trace.py
    - scanner: python
      file: app/observability/__init__.py
  group: API & UI
description: Records ordered trace events and measures request latency for the sanitized execution trace.
---

The Trace class records ordered (event, detail) pairs and measures wall-clock latency. The trace is included in every QueryResponse so the analyst can see the pipeline stages and the observed latency. Latency is observational only — it never fails a gate.
