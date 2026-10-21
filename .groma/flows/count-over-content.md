---
type: Groma Flow
title: Count over content
groma:
  id: count-over-content
---

The analyst asks how many tickets are about a topic. The classifier routes the question to the count-over-content category, the topic phrase is extracted, embedded with the pinned embedding model, and the governed hybrid count query returns a true total over the generated ticket texts (lexical match OR semantic match within the calibrated threshold). The count is never capped by the retrieval limit, and the answer is grounded in that executed count.

## Steps

| From | To | Action |
| --- | --- | --- |
| [Analyst](../actors/analyst.md) | [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | Ask how many tickets are about a topic |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Query program](../systems/governed-conversational-analytics/containers/web-application/components/query-program.md) | Classify the question as content_count |
| [Query program](../systems/governed-conversational-analytics/containers/web-application/components/query-program.md) | [Local LLM endpoint](../externals/local-llm-endpoint.md) | Classify the question with the pinned model |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Routing helpers](../systems/governed-conversational-analytics/containers/web-application/components/ai-routing.md) | Extract the count topic |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Embedding program](../systems/governed-conversational-analytics/containers/web-application/components/embeddings.md) | Embed the topic text |
| [Embedding program](../systems/governed-conversational-analytics/containers/web-application/components/embeddings.md) | [Embedding endpoint](../externals/embedding-endpoint.md) | Produce the topic vector |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Governed retrieval](../systems/governed-conversational-analytics/containers/web-application/components/ai-retrieval.md) | Run the governed hybrid count |
| [Governed retrieval](../systems/governed-conversational-analytics/containers/web-application/components/ai-retrieval.md) | [PostgreSQL](../externals/postgresql-database.md) | Count the tickets matching lexically or semantically |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Answer program](../systems/governed-conversational-analytics/containers/web-application/components/answer-program.md) | Ground the answer in the executed count |
| [Answer program](../systems/governed-conversational-analytics/containers/web-application/components/answer-program.md) | [Local LLM endpoint](../externals/local-llm-endpoint.md) | Ground the answer with the pinned model |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Analyst](../actors/analyst.md) | Return the count with a sanitized trace |
