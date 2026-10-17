---
type: Groma Project
title: Governed Conversational Analytics
groma:
  profile: architecture
description: 'Safe, governed AI analytics over an ITSM PostgreSQL database: a local LLM turns natural-language questions into typed, validated queries that run through a read-only, policy-controlled GraphQL boundary, with every answer grounded in real database results.'
---

The system lets an analyst ask plain-English questions about a governed ITSM helpdesk dataset (tickets, merchants, agents) and receive answers that are provably grounded in database results, never fabricated. A pinned local LLM (Qwen3 27B on llama.cpp) classifies and plans each question into a typed, allowlisted query; a deterministic validator re-checks it; a read-only GraphJin GraphQL boundary executes it; and a grounded answer is produced from the evidence. Content questions route to a governed hybrid retrieval channel (lexical + semantic) over the generated ticket texts. Security is enforced by deterministic controls below the model — the model is never the authorization layer. An offline pipeline generates synthetic ticket texts and embeddings; an evaluation toolkit measures quality and security with a regression gate.
