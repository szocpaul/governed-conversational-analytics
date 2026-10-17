---
type: Groma Flow
title: Content search
groma:
  id: content-search
---

The analyst asks a question about ticket content (e.g. tickets about login problems, or similar to a reference ticket). The classifier routes it to the governed hybrid retrieval channel, which runs lexical ts_rank and semantic pgvector cosine ranking over the generated text fields as the itsm_readonly role, fuses them with RRF, and grounds the answer on the retrieved tickets.

## Steps

| From | To | Action |
| --- | --- | --- |
| [Analyst](../actors/analyst.md) | [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | Ask a content question |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Query program](../systems/governed-conversational-analytics/containers/web-application/components/query-program.md) | Classify as content_about |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Routing helpers](../systems/governed-conversational-analytics/containers/web-application/components/ai-routing.md) | Extract ticket_id (similar mode) |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Governed retrieval](../systems/governed-conversational-analytics/containers/web-application/components/ai-retrieval.md) | Run hybrid retrieval |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Embedding endpoint](../externals/embedding-endpoint.md) | Embed query text |
| [Governed retrieval](../systems/governed-conversational-analytics/containers/web-application/components/ai-retrieval.md) | [PostgreSQL](../externals/postgresql-database.md) | Run parameterized read-only SQL |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Answer program](../systems/governed-conversational-analytics/containers/web-application/components/answer-program.md) | Generate grounded answer |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Analyst](../actors/analyst.md) | Return grounded answer |
