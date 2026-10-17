---
type: C4 Component
title: Pipeline error categories
status: stable
groma:
  id: errors
  parent: web-application
  code:
    - scanner: python
      file: app/security/errors.py
  group: Security controls
description: Stable, machine-readable error types with sanitized user-facing messages.
---

Each PipelineError carries a stable code (ambiguous, unsupported, malformed_plan, validation_error, dependency_error) and a sanitized message safe to show to users. Sanitization goes through redact() so no private endpoint, credential, full prompt, or internal host detail is ever disclosed.
