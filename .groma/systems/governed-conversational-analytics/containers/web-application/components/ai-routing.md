---
type: C4 Component
title: Routing helpers
status: stable
groma:
  id: ai-routing
  parent: web-application
  code:
    - scanner: python
      file: app/ai/routing.py
  group: Query pipeline
description: Deterministic, model-free functions for category normalization and ticket_id/topic extraction.
---

Pure functions, no LLM, no I/O. normalize_category maps a raw classifier category to a known category with the conservative fallback (unknown -> supported). extract_ticket_id pulls a 5-6 digit reference ticket_id from a content_similar question (anchored to avoid P1-P4, counts, years). extract_count_topic strips count boilerplate from a count-over-content question to yield the topic phrase. CONTENT_CATEGORIES and COUNT_CATEGORIES define which categories route to retrieval and count paths.
