---
type: C4 System
title: Governed Conversational Analytics
status: stable
groma:
  id: governed-conversational-analytics
description: A FastAPI web app that turns natural-language ITSM questions into grounded, governed queries over PostgreSQL via a read-only GraphJin GraphQL boundary, backed by a pinned local LLM.
---

The product is a conversational analytics surface over a governed ITSM dataset. One runtime container, the web application (FastAPI), orchestrates the query pipeline: a DSPy classifier routes the question, a planner emits a typed governed request, a deterministic validator re-checks it, a read-only GraphJin client executes it, and a grounded answer is produced from the evidence. Content questions route to a governed hybrid retrieval channel (lexical plus semantic) over the generated ticket texts, and a count over a topic is answered by a governed hybrid count.

A second container, the evaluation toolkit, drives the live pipeline over held-out cases with deterministic metrics and a regression gate.

Nine offline command-line containers prepare and maintain the data: database initialization and reset, the atomic dataset import, the synthetic ticket-text generation and its validation suite, the embedding generation, the count-threshold calibration, the model preflight, and the bounded BootstrapFewShot optimization.
