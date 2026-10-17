---
type: C4 Component
title: Injection telemetry classifier
status: stable
groma:
  id: classifier
  parent: web-application
  code:
    - scanner: python
      file: app/security/classifier.py
  group: Security controls
description: Telemetry-only prompt-injection signal; never an authorization boundary.
---

Produces an InjectionSignal (flagged, category, matched_patterns) for observability only. Heuristic regex patterns detect ignore-instructions, admin-mode, SQL-write-intent, credential-request, prompt-extraction, multilingual-ignore, and encoding-evasion. The signal is recorded in the trace but never used to grant or block access — deterministic backend controls (validator, GraphJin policy, PostgreSQL read-only role) are the actual security boundaries.
