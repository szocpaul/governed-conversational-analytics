---
type: C4 System
title: Governed Conversational Analytics
status: stable
groma:
  id: governed-conversational-analytics
description: A FastAPI web app that turns natural-language ITSM questions into grounded, governed queries over PostgreSQL via a read-only GraphJin GraphQL boundary, backed by a pinned local LLM.
---

The product is a conversational analytics surface over a governed ITSM dataset. It has one runtime container — the web application (FastAPI) — that orchestrates the query pipeline: a DSPy classifier routes the question, a planner emits a typed governed request, a deterministic validator re-checks it, a read-only GraphJin client executes it, and a grounded answer is produced from the evidence. Content questions route to a governed hybrid retrieval channel (lexical + semantic) over generated ticket texts. A second container, the evaluation toolkit, drives the live pipeline over held-out cases with deterministic metrics and a regression gate. Eight offline script containers handle dataset import, database setup, synthetic text generation, embedding generation, threshold calibration, model preflight, and the evaluation/optimization runners.
