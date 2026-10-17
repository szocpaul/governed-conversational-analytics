---
type: C4 Container
title: Held-out evaluation runner
status: stable
groma:
  id: script-run
  parent: governed-conversational-analytics
description: Executes every held-out case through the live governed pipeline and writes a versioned artifact.
---

Runs every held-out case with the pinned model, temperature zero, and cache disabled. Takes a PostgreSQL snapshot before and after each case to detect any prohibited effect. Security cases are judged by backend effects and disclosure, never refusal wording. Writes a versioned artifact with pinned metadata (no secrets), per-case results, and separately computed deterministic metrics. Latency is recorded observationally.
