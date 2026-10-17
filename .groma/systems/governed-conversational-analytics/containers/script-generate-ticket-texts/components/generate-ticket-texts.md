---
type: C4 Component
title: Generate ticket texts (script)
status: stable
groma:
  id: generate-ticket-texts
  parent: script-generate-ticket-texts
  code:
    - scanner: python
      file: scripts/generate_ticket_texts.py
  group: Content pipeline
description: Entry point for the offline ticket-text generation pipeline.
---

scripts/generate_ticket_texts.py. Loads the pinned dataset, splits it into batches, and runs the TicketTextProgram over each batch with checkpoint/resume. Writes the generated texts to data/raw/tickets_texts.jsonl and a provenance manifest (data/raw/texts-manifest.json). Uses the pinned local model (temp 0, recorded seed, batch 5).

## Relationships

| Source | Target | Description | Technology |
| --- | --- | --- | --- |
| [generate-ticket-texts](generate-ticket-texts.md) | [local-llm-endpoint](../../../../../externals/local-llm-endpoint.md) | Generates synthetic ticket texts | DSPy (pinned local model) |
