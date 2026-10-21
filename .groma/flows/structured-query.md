---
type: Groma Flow
title: Structured query
groma:
  id: structured-query
---

The analyst asks a plain-English question. The pipeline classifies and plans it into a typed governed request, validates it, executes it through the read-only GraphJin GraphQL boundary over PostgreSQL, normalizes the evidence, and produces a grounded answer with a sanitized trace.

## Steps

| From | To | Action |
| --- | --- | --- |
| [Analyst](../actors/analyst.md) | [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | Ask a question |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Classifier](../systems/governed-conversational-analytics/containers/web-application/components/classifier.md) | Record injection telemetry |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Query program](../systems/governed-conversational-analytics/containers/web-application/components/query-program.md) | Classify and plan |
| [Query program](../systems/governed-conversational-analytics/containers/web-application/components/query-program.md) | [Local LLM endpoint](../externals/local-llm-endpoint.md) | Classify and plan with the pinned model |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Validator](../systems/governed-conversational-analytics/containers/web-application/components/validator.md) | Validate the request |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [GraphJin client](../systems/governed-conversational-analytics/containers/web-application/components/graphjin-client.md) | Execute governed query |
| [GraphJin client](../systems/governed-conversational-analytics/containers/web-application/components/graphjin-client.md) | [GraphJin](../externals/graphjin.md) | Run GraphQL query |
| [GraphJin](../externals/graphjin.md) | [PostgreSQL](../externals/postgresql-database.md) | Execute read-only SQL |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Result normalizer](../systems/governed-conversational-analytics/containers/web-application/components/result-normalizer.md) | Normalize evidence |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Answer program](../systems/governed-conversational-analytics/containers/web-application/components/answer-program.md) | Generate grounded answer |
| [Answer program](../systems/governed-conversational-analytics/containers/web-application/components/answer-program.md) | [Local LLM endpoint](../externals/local-llm-endpoint.md) | Ground the answer with the pinned model |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Redaction](../systems/governed-conversational-analytics/containers/web-application/components/redaction.md) | Redact user-facing output |
| [Routes](../systems/governed-conversational-analytics/containers/web-application/components/routes.md) | [Analyst](../actors/analyst.md) | Return grounded answer |
