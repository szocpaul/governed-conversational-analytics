# Prime Agent Instructions

## Mission

Implement the approved Governed Conversational Analytics project from the versioned Spec Kit artifacts in this repository.

The repository files are the source of truth. Do not reconstruct requirements from chat history, assumptions, or this file alone.

## Project Status (as of 2026-10-10)

**Features 001-005 are COMPLETE and human-approved (all MANUAL GATEs passed).**
Project v2 is done: 60/60 tasks complete across all five features.

- 001 Governed ITSM Data Foundation: complete (T001-T011)
- 002 Conversational Query Pipeline: complete (T001-T009)
- 003 Security Hardening: complete (T001-T009)
- 004 Evaluation and Demo: complete (T001-T010), including T010-review
  correctness fixes (see `specs/004-evaluation-and-demo/fix-report.md`)
- 005 Analytics Surface v2: complete (T001-T021) — GROUP BY / having
  aggregations, is-null filtering, ratio/percentage metrics (see
  `specs/005-analytics-surface-v2/runner-report.md`)

The rules below remain in force for any new work on this repository.

## Source-of-Truth Precedence

When instructions conflict, use this order:

1. Repository constitution, if present
2. Approved `spec.md`
3. Approved `plan.md`
4. Approved `tasks.md`
5. This `AGENTS.md`
6. Existing implementation conventions that do not conflict with the above

Report unresolved conflicts and stop before implementing the affected work.

## Approved Feature Chain

Implement the features in this order:

```text
specs/001-governed-itsm-data-foundation/
    spec.md
    plan.md
    tasks.md
        |
        v
specs/002-conversational-query-pipeline/
    spec.md
    plan.md
    tasks.md
        |
        v
specs/003-security-hardening/
    spec.md
    plan.md
    tasks.md
        |
        v
specs/004-evaluation-and-demo/
    spec.md
    plan.md
    tasks.md
```

A later feature MUST NOT start until the automatable validation gates of its prerequisite features pass.

## Required Preflight

Before changing application code:

1. Read this file and all three artifacts for feature `001`.
2. Check for a repository constitution and validate the active plan against it.
3. Run the equivalent of `/speckit-analyze` for the active feature.
4. Verify requirement, plan, task, and validation coverage.
5. Verify required tools and external dependencies.
6. Record the current Git commit and working-tree state.
7. Do not overwrite unrelated user changes.

If an approved artifact is missing, contradictory, or materially incomplete, stop and report the exact file and section.

## Implementation Workflow

For each feature:

1. Work from its `tasks.md` in dependency order.
2. Respect `[P]` markers only when tasks have no file or runtime dependency conflict.
3. Write required tests before implementation and observe the expected failure.
4. Implement the smallest change that satisfies the approved task.
5. Run the task-specific tests.
6. Run the feature validation gates.
7. Mark a task complete only after its implementation and tests pass.
8. Do not mark partial or blocked work complete.
9. Keep changes traceable to task IDs in commits or the final report.
10. Stop at every `MANUAL GATE`.

## Absolute Prohibitions

- DO NOT tick, approve, bypass, or reinterpret any `MANUAL GATE`.
- DO NOT bypass GraphJin with direct arbitrary SQL from the model or application.
- DO NOT give the model unrestricted database credentials.
- DO NOT make GraphJin or PostgreSQL writable for the runtime query path.
- DO NOT use real organizational data or personal data.
- DO NOT replace the approved dataset if its pinned source cannot be verified.
- DO NOT silently generate replacement dataset records.
- DO NOT switch to another model, hosted provider, or cloud fallback.
- DO NOT simulate model, database, security, baseline, or evaluation results.
- DO NOT optimize on held-out evaluation cases.
- DO NOT run GEPA, MIPROv2, SIMBA, or fine-tuning.
- DO NOT use latency as a pass/fail quality gate.
- DO NOT expose credentials, private endpoint details, complete prompts, or prohibited data in user-facing traces.
- DO NOT commit API keys, passwords, tokens, or generated secrets.

## Feature 001: Governed ITSM Data Foundation

### Dataset

Use only the approved source:

```text
https://github.com/drapertoby/itsm-ticket-dataset
```

Before import:

1. Resolve and record the exact Git commit SHA.
2. Verify the MIT license and preserve attribution.
3. Download only commit-pinned source files.
4. Calculate SHA-256 checksums.
5. Keep raw files immutable.
6. Record provenance and import results in `artifacts/import-manifest.json`.

Required source files:

```text
merchants.csv
agents.csv
tickets.csv
LICENSE
```

If source, revision, license, or files cannot be verified, STOP AND REPORT.

### PostgreSQL

- Pin the PostgreSQL image version.
- Configure a persistent named volume and health check in `compose.yml`.
- Create the application database explicitly.
- Create schema, tables, indexes, owner role, and read-only role reproducibly.
- Make initialization idempotent.
- Make import atomic.
- Provide and test a clean local reset path.
- Grant the GraphJin runtime only the read-only PostgreSQL role.

### GraphJin

GraphJin is the governed database access boundary.

Configure explicit:

- entities;
- fields;
- relationships;
- operations;
- roles;
- result limits;
- database-query timeout;
- read-only database credentials.

Prove with tests that authorized reads succeed and INSERT, UPDATE, DELETE, TRUNCATE, CREATE, ALTER, and DROP fail with zero database changes.

## Feature 002: Conversational Query Pipeline

### Local LLM

Use the local OpenAI-compatible llama.cpp endpoint:

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1
LLM_MODEL=<EXACT_ID_FROM_/v1/models>
LLM_API_KEY=local-not-required
LLM_TEMPERATURE=0
LLM_CACHE=false
```

Requested model artifact:

```text
openai/models\Qwen3.8-27B-UD-Q4_K_M.gguf
```

Before model-dependent implementation:

1. Call `GET /v1/models`.
2. Verify the requested Qwen model is loaded.
3. Record the exact API model ID.
4. Run one deterministic chat-completion smoke request.
5. Run one typed DSPy prediction.
6. Save non-secret metadata to `artifacts/llm-preflight.json`.

If the endpoint, model, or API compatibility check fails, STOP AND REPORT. Do not use fallback models.

### Query Flow

The required path is:

```text
Natural-language question
    -> typed DSPy planning
    -> deterministic request validation
    -> GraphJin GraphQL or governed tool request
    -> structured result
    -> grounded DSPy answer
    -> sanitized trace and latency
```

The model MUST NOT receive an arbitrary SQL execution tool.

A factual answer MUST be supported by the executed result. If evidence is absent, ambiguous, or unavailable, return a stable clarification, refusal, or dependency error. Never fabricate an answer.

## Feature 003: Security Hardening

Prompt-injection classification is telemetry, not authorization.

Security must be verified through:

- actual database effects;
- returned records and field values;
- traces and error responses;
- deterministic limits and policy decisions;
- false-refusal measurement on legitimate requests.

Use test-only canary values to verify redaction. Any prohibited database effect, unauthorized disclosure, seeded secret, complete prompt, or private endpoint value in external output fails the gate.

Keep these controls independent:

- database-query timeout;
- overall request safety timeout;
- maximum result size.

## Feature 004: Evaluation, Optimization, and Demo

### Dataset Isolation

Maintain physically separate versioned files:

```text
evaluation/dev_cases.json
evaluation/cases.json
```

Requirements:

- 12 to 20 labeled development cases;
- at least 20 held-out cases;
- at least 5 held-out security or unauthorized-access cases;
- stable unique case IDs;
- zero held-out IDs consumed by optimization.

### Baseline Discipline

Before optimization:

1. Pin all relevant versions and parameters.
2. Set measured-run temperature to zero.
3. Disable model-response caching.
4. Run a representative sample two or three times.
5. Record per-metric noise.
6. Run the complete held-out evaluation.
7. Save `artifacts/baseline.json`.

Do not claim improvement when observed intervals overlap.

### Approved DSPy Optimizer

Use only:

```python
optimizer = dspy.BootstrapFewShot(
    metric=text_to_query_metric,
    metric_threshold=1.0,
    max_bootstrapped_demos=4,
    max_labeled_demos=4,
    max_rounds=1,
    max_errors=3,
)
```

Run optimization only if at least 12 valid labeled development examples exist.

`text_to_query_metric` returns `1.0` only when all mandatory checks pass:

- structured output validates;
- request is read-only and policy-allowed;
- GraphJin executes successfully;
- normalized result matches the labeled expected result;
- no prohibited effect or unauthorized disclosure occurs.

Otherwise it returns `0.0`.

Save optimizer inputs, accepted demonstration IDs, configuration, output artifact hash, errors, and versions to `artifacts/optimization-run.json`.

### Held-Out Evaluation

After optimization, run the unchanged held-out set with temperature zero and cache disabled. Save `artifacts/current.json` and compare every metric independently.

The comparison command MUST return non-zero for:

- failed P1 quality thresholds;
- execution-accuracy degradation greater than 5 percentage points;
- any prohibited database effect;
- any unauthorized disclosure.

Latency is observational only. Report per-request values, median, p90, and maximum. Latency alone MUST NOT fail the gate.

## Required Validation Commands

Run the task-level commands from each `tasks.md`. The final project must support commands equivalent to:

```bash
pytest -q
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare \
  --baseline artifacts/baseline.json \
  --current artifacts/current.json
```

Do not hide a failed sub-gate behind a successful aggregate command.

## Secrets and Generated Files

- Provide `.env.example` with placeholders only.
- Keep actual secrets out of Git.
- Do not expose the private LLM endpoint in the UI, external errors, or user-facing traces.
- Keep raw source data immutable.
- Record hashes and versions for generated optimizer and evaluation artifacts.
- Follow repository `.gitignore` rules and add safe exclusions where necessary.

## Stop-and-Report Conditions

Stop immediately and report when:

- an approved artifact conflicts with the constitution;
- a required artifact is missing;
- the dataset source, revision, or license cannot be verified;
- PostgreSQL or GraphJin cannot be started or validated;
- the local llama.cpp endpoint or exact model cannot be verified;
- a required dependency is unavailable;
- a security test shows a prohibited effect or disclosure;
- held-out evaluation data leaks into optimization;
- a task requires changing an approved requirement;
- a manual gate is reached.

Do not improvise around these conditions.

## Required Final Report

At the end of each automatable feature stage, report:

1. completed task IDs;
2. incomplete or blocked task IDs;
3. files changed;
4. commits created, if any;
5. exact pinned dependency versions;
6. dataset commit SHA, license, and checksums where applicable;
7. exact API model ID and llama.cpp version where available;
8. validation commands and results;
9. baseline and current metrics where applicable;
10. security-effect and disclosure results;
11. latency median, p90, and maximum as observational metrics;
12. known limitations;
13. outstanding manual gates.

The project is not complete until the final human manual gate is approved.
