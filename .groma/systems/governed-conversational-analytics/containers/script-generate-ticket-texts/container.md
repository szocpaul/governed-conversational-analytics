---
type: C4 Container
title: Generate ticket texts
status: stable
groma:
  id: script-generate-ticket-texts
  parent: governed-conversational-analytics
description: Offline pipeline that generates synthetic ticket text fields from structured columns.
---

Runs the TicketTextProgram (app/ai/text_generation.py) in batches over the pinned dataset. For each batch, the pinned local model generates short_description, description, and resolution_notes (null for open tickets) as strict JSON validated by pydantic. Zero-tolerance acceptance: the ticket_id set must match exactly, per-entry rules must hold (length limits, non-empty, resolution_notes null iff open). Checkpointed and resumable. Writes the generated texts to a pinned JSONL artifact with a provenance manifest.
