---
type: C4 Component
title: Validate ticket texts (script)
status: stable
groma:
  id: validate-ticket-texts
  parent: script-validate-ticket-texts
  code:
    - scanner: python
      file: scripts/validate_ticket_texts.py
  group: Content pipeline
description: Entry point for the deterministic offline validation suite.
---

scripts/validate_ticket_texts.py. Validates the pinned ticket-texts artifact: schema, coverage, length limits, language, category consistency, and the NULL rule. Prints a validation report. Used before human data-quality review and import.
