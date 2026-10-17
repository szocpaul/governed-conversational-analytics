---
type: C4 Component
title: Text generation program
status: stable
groma:
  id: text-generation
  parent: script-generate-ticket-texts
  code:
    - scanner: python
      file: app/ai/text_generation.py
  group: Content pipeline
description: DSPy module for governed synthetic ticket-text generation with zero-tolerance acceptance.
---

app/ai/text_generation.py. The TicketTextProgram runs dspy.Predict(GenerateTicketTexts) under an explicit JSONAdapter. Per batch: the parse must succeed, the ticket_id set must match the input exactly, and per-entry rules must hold (length limits, non-empty, resolution_notes null iff open). Bounded identical-request retries, then BatchGenerationError. Offline build-time module — never imported by the runtime query path.
