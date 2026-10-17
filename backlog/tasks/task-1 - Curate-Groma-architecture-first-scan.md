---
id: TASK-1
title: Curate Groma architecture (first scan)
status: Done
assignee:
  - '@ubuntu'
created_date: '2026-10-17 15:28'
updated_date: '2026-10-17 16:01'
labels: []
dependencies: []
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The .groma/ directory holds a raw first scan: 15 single-file script containers plus 30+ flat auto-named components under the project-named system, with no descriptions, actors, external systems, or relationships. The user asked to curate the architecture as it exists (no application code changes) so the map describes the real design: a governed conversational-analytics FastAPI web app over a read-only GraphJin GraphQL boundary on PostgreSQL, backed by a pinned local LLM and embedding endpoints, plus offline data/text/embedding pipelines and an evaluation/optimization toolkit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Container boundaries are settled: one web-application container with grouped components; one evaluation container; offline pipeline containers; dev/test tooling excluded
- [x] #2 Actors (Analyst, Operator) and external systems (PostgreSQL, GraphJin, local LLM, embedding model) are declared
- [x] #3 Every visible element has a truthful title, description, and overview grounded in the source
- [x] #4 Key relationships (app -> GraphJin -> PostgreSQL; app -> LLM; app -> embedding; pipelines -> PostgreSQL; evaluation -> pipeline/DB) and the main query flow are recorded
- [x] #5 Two consecutive groma scan runs are stable (no new components for already-owned files) and the rendered map is reviewed
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Exclude dev/test tooling (tests/) via scanners.json; scan.
2. Remove 3 orphaned empty containers (graphjin-server, itsm-database, web-application).
3. Create containers: web-application, evaluation, data-pipelines (offline); move app/ai+app/api+app/data+app/security+app/observability components into web-application.
4. Group web-application components by domain: Query pipeline, Security controls, Data access, Model & endpoints, Observability.
5. Combine __init__.py skyscrapers into domain components; rename script-script containers to meaningful names.
6. Declare actors (Analyst, Operator) and external systems (PostgreSQL, GraphJin, local LLM, Embedding model).
7. Describe every element (title/description/overview/technology) from source.
8. Add relationships (app->GraphJin, GraphJin->PostgreSQL, app->LLM, app->Embedding, pipelines->PostgreSQL, eval->pipeline/DB) and the main query flow + content-search flow.
9. Verify with two consecutive scans + rendered map review.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Curation complete. Structure: 1 system (governed-conversational-analytics), 2 main containers (web-application, evaluation), 14 script containers. web-application has 18 components grouped by domain (Query pipeline, Security controls, Data access, Model & endpoints, API & UI). evaluation has 2 components (case schemas, metrics). Actors: Analyst, Operator. External systems: PostgreSQL, GraphJin, Local LLM, Embedding endpoint. 2 flows: structured-query, content-search. Two consecutive scans stable (0 created, 35 refreshed). All elements described with title, description, overview.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Curated the Groma first scan into a truthful architecture map. Structure: 1 system, 2 main containers (web-application with 18 grouped components, evaluation with 2 components), 14 script containers. Declared 2 actors (Analyst, Operator) and 4 external systems (PostgreSQL, GraphJin, Local LLM, Embedding endpoint). Described every element with title, description, and overview grounded in source. Added 27 relationships and 2 flows (structured-query, content-search). Two consecutive scans stable (0 created, 35 refreshed). Verified with groma view --plain, groma view web-application, and groma view structured-query.
<!-- SECTION:FINAL_SUMMARY:END -->
