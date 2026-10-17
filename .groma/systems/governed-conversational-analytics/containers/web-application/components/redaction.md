---
type: C4 Component
title: Deterministic redaction
status: stable
groma:
  id: redaction
  parent: web-application
  code:
    - scanner: python
      file: app/security/redaction.py
      symbol: redact
  group: Security controls
description: Replaces secrets, canaries, and private endpoint values in all user-facing strings.
---

Every user-facing string (response text, trace detail, error message) passes through redact(). Replaces test-only canary literals, bearer tokens, API keys, passwords, secrets, private Tailscale endpoint URLs, bare IP:port literals, and port suffixes with [redacted]. Deterministic and total: the same input always produces the same output, and no canary, credential, or endpoint detail survives.
