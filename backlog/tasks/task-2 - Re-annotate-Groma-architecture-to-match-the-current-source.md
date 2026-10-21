---
id: TASK-2
title: Re-annotate Groma architecture to match the current source
status: Done
assignee:
  - '@ubuntu'
created_date: '2026-10-20 11:27'
updated_date: '2026-10-20 13:08'
labels: []
dependencies: []
references:
  - evaluation
  - evaluation-schemas
  - metrics
  - run
  - compare
  - run-security
  - verify-examples
  - cross-version-report
  - embeddings
  - count-calibration
  - web-application
  - governed-conversational-analytics
  - query-program
  - answer-program
  - routes
  - app
  - preflight
  - optimization
  - generate-embeddings
  - generate-ticket-texts
  - import-dataset
  - initialize-database
  - reset-database
  - validate-ticket-texts
  - text-generation
  - operator
  - local-llm-endpoint
  - script-count-calibration
  - script-generate-embeddings
modified_files:
  - .groma/actors/operator.md
  - .groma/externals/local-llm-endpoint.md
  - .groma/flows/content-preparation.md
  - .groma/flows/count-over-content.md
  - .groma/flows/quality-gate.md
  - .groma/project.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/evaluation/components/compare.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/evaluation/components/cross-version-report.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/evaluation/components/evaluation-schemas.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/evaluation/components/metrics.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/evaluation/components/run-security.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/evaluation/components/run.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/evaluation/components/verify-examples.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/evaluation/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-compare/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-count-calibration/components/count-calibration.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-cross-version-report/components/cross-version-report.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-cross-version-report/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-generate-embeddings/components/embeddings.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-generate-embeddings/components/generate-embeddings.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-generate-embeddings/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-generate-ticket-texts/components/generate-ticket-texts.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-generate-ticket-texts/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-import-dataset/components/import-dataset.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-import-dataset/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-initialize-database/components/initialize-database.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-optimization/components/optimization.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-preflight/components/preflight.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-reset-database/components/reset-database.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-run-security/components/run-security.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-run-security/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-run/components/run.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-run/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-validate-ticket-texts/components/validate-ticket-texts.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-verify-examples/components/verify-examples.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/script-verify-examples/container.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/web-application/components/answer-program.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/web-application/components/app.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/web-application/components/count-calibration.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/web-application/components/embeddings.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/web-application/components/query-program.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/web-application/components/routes.md
  - >-
    .groma/systems/governed-conversational-analytics/containers/web-application/container.md
  - .groma/systems/governed-conversational-analytics/system.md
  - groma-export/index.html
  - groma-export/render.js
  - groma-export/snapshot.js
  - groma-export/version.js
  - >-
    groma/systems/governed-conversational-analytics/containers/script-compare/components/compare.md
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Groma architecture map (curated in TASK-1) no longer matches the source after features 010-012: the evaluation package is split across six one-file script containers although it is one command-line toolkit; app/ai/embeddings.py is documented as offline-only but the runtime query path imports it; app/ai/count_calibration.py is an offline calibration CLI placed under the runtime web application; the system overview states an outdated number of offline containers; and the evaluation/retrieval/LLM interactions, the operator's use of the offline pipelines, and the count-over-content scenario are missing as relationships or flows. Curate the map so it describes the code as it is, using only the groma CLI, and keep the Backlog task's file and architecture references current.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The evaluation toolkit is one container whose components cover schemas, metrics, the held-out runner, the comparison gate, the security runner, the example verification, and the cross-version report
- [x] #2 Every component description matches the source: the shared embedding client and the count-threshold calibration are described by their real runtime and offline roles
- [x] #3 The system and container overviews state the current container set and responsibilities, with no stale counts
- [x] #4 Relationships cover the evaluation toolkit driving the live pipeline, the pinned LLM serving the planner and the answer program, and the operator running every offline pipeline
- [x] #5 A count-over-content flow is recorded from the analyst question to the grounded answer
- [x] #6 Two consecutive groma scan runs are stable and the rendered map is reviewed
- [x] #7 The Backlog task records every changed file and the affected architecture element IDs
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
6. Run two groma scans, review the rendered map, and record every changed file and affected element ID on TASK-2.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Structural work done with the groma CLI only. The evaluation package (schemas, metrics, runner, comparison gate, security runner, example verification, cross-version report) is now one container named evaluation; the six one-file script containers were combined into it and the container was renamed so the operator relation still points at it. The embedding client (app/ai/embeddings.py) moved to the web application because the runtime query path imports it; its old description claimed it was never imported at runtime. The count-threshold calibration (app/ai/count_calibration.py) moved to the offline calibration container because only the calibration sweep uses it; the runtime reads the calibrated value from count-threshold.json through the retrieval channel. Tooling limits: authored relationships cannot be removed, so components that already had a relationship to an external system could not be moved directly; they were moved by detaching the file, rescanning, moving the new component, and re-adding the relationship. Relations between two elements that both own code must use file endpoints, so the evaluation-to-case-library relation is recorded from app/ai/count_calibration.py to evaluation/schemas.py. Files that no scanner reads (database/*.sql, graphjin/config/*.yml, app/web/index.html, app/web/styles.css, app/web/examples.json, compose.yml) stay without a code owner; they are described in the overviews of the components and containers that use them.

Follow-up fix after review: the three analyst flows (structured-query, content-search, count-over-content) did not link to the local LLM endpoint, so the model call was invisible on the map. Added the missing steps: Query program -> Local LLM endpoint (classify and plan) and Answer program -> Local LLM endpoint (ground the answer). The relations already existed; the flow tables were the missing part. The operator flows (quality-gate, content-preparation) already linked to the endpoint.

Verified after the flow fix: two consecutive groma scans create no new components (0 created, 35 refreshed) and every one of the five flows now links to the local LLM endpoint; the groma-export static map was regenerated.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Re-annotated the Groma architecture so it matches the current source. Combined the six one-file evaluation script containers into one evaluation toolkit container with seven components, moved the shared embedding client into the web application and the count-threshold calibration into its offline container, rewrote the stale system, container, and component overviews (including the wrong 'offline only' claim about the embedding client), added the missing relationships (evaluation toolkit to the live pipeline, the pinned LLM to the planner and the answer program, the operator to every offline pipeline) and three flows (count over content, offline content preparation, quality and security gate), and linked every flow to the local LLM endpoint so the model call is visible on the map. Verified with two consecutive groma scans that create no new components, a reviewed groma view --plain, and a regenerated groma-export static map; no application code was changed.
<!-- SECTION:FINAL_SUMMARY:END -->
