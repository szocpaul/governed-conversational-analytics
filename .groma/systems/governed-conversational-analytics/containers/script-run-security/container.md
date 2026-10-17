---
type: C4 Container
title: Security evaluation runner
status: stable
groma:
  id: script-run-security
  parent: governed-conversational-analytics
description: Executes security cases and verifies backend effects and disclosure.
---

Runs every case from evaluation/security_cases.json through the live pipeline (or the appropriate layer for direct-unsafe cases). Verifies backend effects (database snapshots) and disclosure (redaction, canary values). Security is judged by effects and disclosure, never refusal wording. Measures false-refusal on legitimate requests. Writes machine-readable results to artifacts/security-results.json.
