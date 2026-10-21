# AI Interview Prep Brief — "Governed Conversational Analytics"

**Who this file is for:** an AI assistant (e.g. Microsoft Copilot) that has **no access to
the GitHub repository**. Everything needed to understand the project and to run a
realistic interview rehearsal is inside this file.

**Who the user is:** the developer of this project. They are applying for
**Applied AI Engineer – Conversational Analytics** at ALDI Hungary
(`https://karrier.aldi.hu/job/1442769633`, IT, Budapest, full-time, as soon as possible).
The job description is reproduced in condensed form in Part C.

**If the assistant cannot open files, paste the whole content of this file as the
first message, then use Part E.**

**How the user will use it:** they paste this file (or upload it) into an AI chat and
then ask it to quiz them, act as the interviewer, rewrite their answers, or explain
parts of the system. Part E contains the explicit task list the AI should follow.

---

# PART A — Instructions for the AI assistant

You are an **interview coach** for a senior applied-AI engineering role. The user is
the author of the project described below. Your job is to make them able to talk
about this project fluently, honestly, and convincingly in a 45–60 minute interview
(in Hungarian or English, as the user requests).

Rules you must follow:

1. **Use only the facts in this file.** If something is not covered here, say
   "the brief does not cover that" and ask the user, or tell them to check the repo.
   Never invent metrics, file names, or features.
2. **Never let the user overstate.** Part D lists real gaps (no LLM-as-a-judge, no
   multilingual support, no LLM reranking, 2.44% false-refusal rate, self-hosted
   model instead of a managed API, …). If the user says something that contradicts
   the brief, correct them and point at the gap.
3. **Coach for spoken delivery.** Answers must be short, structured, in the user's own
   voice. Prefer "problem → decision → evidence → limit" over feature lists.
4. **One number at a time.** Make the user quote the numbers from Part F without
   looking, and correct them if they drift.
5. **Never let them promise something the project does not do.** If they describe a
   feature that is only a follow-up, flag it immediately.
6. Default language: match the user's request. If they ask in Hungarian, answer in
   Hungarian.

**The single most important message the user must be able to deliver:**
> "The model is never the security boundary. The boundary is where the system is
> actually constrained, and that is also where it is measurable."

---

# PART B — The project, in full

## B1. What it is

**Governed Conversational Analytics** is a conversational analytics application over a
governed ITSM (helpdesk) dataset. A business user asks a plain-English question in a
web UI; the system answers with a grounded, traceable result, and the model is never
allowed to touch the database.

The two non-negotiable design decisions:

1. **The model has no power.** It does not write SQL, it does not get database
   credentials, and it is not the security layer. It chooses entities, fields and
   operations inside an allowlist; a deterministic validator re-checks the request; a
   read-only GraphQL layer executes it; the database role can only SELECT.
2. **Everything is measured.** There is a 57-case held-out evaluation set (16 of them
   security cases) and a regression gate that exits non-zero on quality degradation,
   any prohibited database effect, or any unauthorized disclosure.

## B2. Actors, containers, external systems

**Actors**

- **Analyst** — a business/operations analyst who asks plain-English questions about
  the ITSM dataset (tickets, merchants, agents) and expects grounded answers with a
  sanitized execution trace.
- **Operator** — the maintainer who configures the pinned local LLM and embedding
  endpoints, runs the offline data/text/embedding pipelines, performs model preflight,
  and executes the evaluation and optimization toolkit.

**Containers**

| Container | Responsibility | Main files |
|---|---|---|
| **Web application** (FastAPI) | The runtime query pipeline: classify → plan → validate → execute → normalize → ground → redact. Serves the demo UI and `POST /query`. | `app/main.py`, `app/api/routes.py`, `app/api/schemas.py` |
| **Evaluation toolkit** | Runs the live pipeline over held-out cases, computes deterministic metrics, compares with the baseline, runs the security suite. | `evaluation/run.py`, `evaluation/run_security.py`, `evaluation/metrics.py`, `evaluation/compare.py`, `evaluation/verify_examples.py` |
| **9 offline CLI containers** | DB init + reset, atomic dataset import, ticket-text generation, ticket-text validation, embedding generation, count-threshold calibration, model preflight, BootstrapFewShot optimization. | `scripts/*.py`, `app/ai/optimization.py`, `app/ai/count_calibration.py`, `app/ai/preflight.py`, `app/ai/text_generation.py`, `app/ai/embeddings.py` |

**External systems**

- **PostgreSQL** (pinned image `pgvector/pgvector:pg16`, PG 16.15, pgvector 0.8.7) —
  the ITSM store: `tickets`, `merchants`, `agents`, plus generated text columns, a
  `vector(768)` embedding column, and a generated `fts` tsvector column. Two roles:
  `itsm_owner` (setup/import) and `itsm_readonly` (SELECT-only, `statement_timeout 5s`).
- **GraphJin** (external, v3) — the governed GraphQL access boundary over PostgreSQL.
  `default_block: true`, explicit entity/field/operation allowlists, `default_limit: 100`.
- **Local LLM endpoint** — pinned llama.cpp OpenAI-compatible chat endpoint serving
  Qwen3 27B (Q4_K_M). Verified via `GET /v1/models`. **No fallback model or provider.**
- **Embedding endpoint** — a *separate* pinned llama.cpp instance started with
  `--embeddings`, serving EmbeddingGemma-2 (Q8_0 GGUF), 768 dimensions, all values
  finite, no fallback.

**Supporting infrastructure:** `compose.yml` (pinned PostgreSQL + GraphJin services,
named volume, healthcheck), `database/` (schema, roles, bootstrap SQL),
`graphjin/config/` (`dev.yml`, `policies.yml`), `data/raw/` (immutable pinned sources),
`specs/` (12 features with `spec.md` / `plan.md` / `tasks.md` / `runner-report.md`),
`artifacts/` (baseline, current, optimization, calibration, preflight manifests),
`tests/` (664 tests).

## B3. The five flows (C4 flow view)

**1. Structured query** (the classic NL → SQL-shaped path)

```
Analyst → Routes → (injection telemetry) → Query program (classify + plan, pinned model)
        → Validator (deterministic)
        → GraphJin client → GraphJin → PostgreSQL (read-only SQL)
        → Result normalizer → Answer program (grounded answer, pinned model)
        → Redaction → Analyst
```

**2. Content search** (search the *text* of the tickets)

```
Analyst → Routes → Query program (classify as content_about / content_similar)
        → Routing helpers (extract a ticket_id reference for "similar" mode)
        → Embedding client → Embedding endpoint (query vector)
        → Governed retrieval → PostgreSQL (parameterized read-only SQL: ts_rank + pgvector cosine)
        → RRF fusion → Answer program → Redaction → Analyst
```

**3. Count over content** ("how many tickets are about X?")

```
Analyst → Routes → Query program (classify as content_count)
        → Routing helpers (extract the topic phrase, strip count boilerplate)
        → Embedding program → Embedding endpoint
        → Governed hybrid COUNT (no LIMIT) + up to 5 example ticket_ids
        → Answer program (grounded in the executed count) → Analyst
```

**4. Quality and security gate**

```
Operator → Evaluation toolkit → Local LLM endpoint (every case)
         → PostgreSQL (snapshot before and after EVERY case)
         → deterministic metrics → compare with baseline → exit code → Operator
```

**5. Content preparation** (offline, before import)

```
Operator → Generate ticket texts (pinned model, batched, checkpoint/resume)
         → Validate ticket texts (schema, coverage, length, language, category, null rule)
         → Generate embeddings (one 768-d vector per ticket, checkpoint/resume)
         → Import dataset (CSV rows + texts + embeddings, ONE transaction) → PostgreSQL
```

## B4. The runtime pipeline in detail (app/api/routes.py)

`POST /query` runs the whole pipeline inside an overall request safety timeout
(default 120 s) and a bounded thread pool. The ordered stages:

1. **Injection telemetry** — `app/security/classifier.py` produces an
   `InjectionSignal(flagged, category, matched_patterns)` from heuristic regexes
   (ignore-instructions, admin-mode, SQL-write-intent, credential-request,
   prompt-extraction, multilingual-ignore, encoding-evasion). The signal is
   **recorded in the trace and never used to grant or block anything.**
2. **Classification + planning** — `app/ai/query_program.py` runs two typed DSPy
   predictors: `ClassifyQuestion` and `PlanQuery`. The planner's JSON is parsed into
   a validated `StructuredQueryRequest`. Unsupported shapes (joins, subqueries,
   unions, distinct-as-key) raise `UnsupportedShapeError` **before any GraphJin call**.
   An unknown classifier category falls back conservatively to the structured path.
3. **Routing by category**
   - `content_about` / `content_similar` → governed hybrid retrieval channel.
   - `content_count` → governed hybrid count.
   - `ambiguous` / `unsupported` → stable clarification / refusal, no data access.
   - `supported` → validate → GraphJin execute → normalize.
4. **Validation** — `app/security/validator.py`, a pure function, no LLM, no I/O.
5. **Execution** — `app/data/graphjin_client.py` builds GraphQL from the validated
   request: `list` (fields + optional where/order_by/limit), `aggregate`
   (`count`, `ratio` as an aliased expression aggregate, or `fn_field`), grouped
   operations (`distinct` + aggregate columns). **No arbitrary SQL is ever
   constructed or sent.** HAVING is not rendered (GraphJin v3 has no native HAVING);
   the post-aggregation filter is applied client-side by the result normalizer.
6. **Normalization** — `app/data/result_normalizer.py` produces a JSON-serializable
   `Evidence` object: aggregates flattened (count stays an int), lists become rows +
   `row_count`, grouped results become per-group rows with a truncation flag,
   `apply_having()` is a pure function over already-executed group rows.
   **Empty results stay empty — no data is invented.**
7. **Grounding check** — `app/ai/answer_program.py` generates the answer from the
   question + evidence and runs a deterministic `is_grounded()` check: every factual
   token (numbers, named values, ratios) in the answer must appear in the evidence.
   Ungrounded answers are flagged so the caller can refuse. Empty evidence, null
   ratios (undefined), grouped results and ratio percentages are handled explicitly.
8. **Redaction** — `app/security/redaction.py`: every user-facing string (response,
   trace detail, error message) passes through `redact()`. It replaces test-only
   canary literals, bearer tokens, API keys, passwords, secrets, private endpoint
   URLs, bare `IP:port` literals and port suffixes. Deterministic and total.
9. **Trace + latency** — `app/observability/trace.py` records ordered
   `(event, detail)` pairs and wall-clock latency. Included in every response.
   **Latency is observational only; it never fails a gate.**

Error handling: every stage failure yields a stable `dependency_error` or a
clarification, never a fabricated answer. Stable error codes in
`app/security/errors.py`: `ambiguous`, `unsupported`, `malformed_plan`,
`validation_error`, `dependency_error`.

## B5. Typed requests (the core abstraction)

The model never emits SQL. It fills a **typed request** — a Pydantic model in
`app/api/schemas.py`:

```python
ENTITIES = {
  "merchants": {"merchant_id","merchant_name","sector","tier","region"},
  "agents":    {"agent_id","agent_name","tier","primary_category",
                "shift_region","efficiency_multiplier"},
  "tickets":   {"ticket_id","merchant_id","category","sub_category","priority",
                "created_at","is_legacy","assigned_agent_id","category_mismatch",
                "first_response_at","closed_at","ttfr_hours","resolution_hours",
                "response_breached","resolution_breached","is_reopened",
                "is_reopen_child","is_incident_ticket","csat_score"},
}
RELATIONSHIPS = {"tickets": {"merchants","agents"},
                 "merchants": {"tickets"}, "agents": {"tickets"}}
COLUMN_TYPES = {...}   # integer / text / numeric / timestamp / boolean per column
MAX_LIMIT = 100        # matches the GraphJin default_limit hard cap
MAX_GROUP_BY = 3

class StructuredQueryRequest(BaseModel):
    entity: str
    operation: Literal["list", "aggregate"]
    fields: list[str]
    filters: list[Filter]        # field + op + value
    aggregate: Aggregate | None  # count | sum | avg | min | max | ratio
    group_by: list[str]
    having: list[HavingFilter]
    order_by: ...
    limit: int
```

`FilterOp` = `eq, ne, gt, gte, lt, lte, in, like, is_null, is_not_null`.
`AggregateFunction` = `count, sum, avg, min, max, ratio`.

**Why this matters (a favourite interview point):** typing gives *authorization*,
measurement gives *correctness*.

- The form guarantees the model **cannot execute** a request that is not allowed
  and not well formed — it fails at the validator, before the database is touched.
  (The model can still *emit* such a request; it just cannot get it executed.)
- The form does **not** guarantee the request is *semantically sensible*. A
  well-formed, allowed request such as "priority = 'P9'" passes validation, runs,
  and returns zero rows. The evaluation catches that kind of drift
  (execution accuracy drops), not the validator.
- Because the expected result in the evaluation set is the *same kind of typed
  request*, accuracy is measured by **equivalence on executed results**, not by
  "does the answer look similar".

## B6. The deterministic validator (app/security/validator.py)

A pure function; the same input always produces the same decision. It validates:

- entity (must be in `ENTITIES`);
- operation (`list` / `aggregate`);
- fields (must belong to the entity's allowlist);
- filters: field known, operator known, **value type-compatible with the column
  type**; `is_null` / `is_not_null` carry no value;
- relationships (only declared ones);
- limit (≤ `MAX_LIMIT`);
- aggregate: function known; `avg`/`sum` require a numeric field; `ratio` requires a
  boolean field; `count` needs no field;
- `group_by`: 1–3 fields, aggregate operations only;
- `having`: post-aggregation group filter, numeric value, numeric field required
  for non-`count` functions.

Type-incompatible filters and aggregates are rejected **before any GraphJin call**,
and the request becomes the stable "unsupported" category with **zero governed calls**.

## B7. Hybrid retrieval (app/ai/retrieval.py)

- **Lexical**: `ts_rank(fts, plainto_tsquery('english', %s))` over the generated
  `fts` tsvector column, `WHERE fts @@ plainto_tsquery('english', %s)`, `LIMIT %s`.
- **Semantic**: `SELECT ticket_id, embedding <=> %s::vector AS distance ...
  WHERE embedding IS NOT NULL LIMIT %s` (pgvector cosine distance).
- **Fusion**: deterministic **Reciprocal Rank Fusion with k = 60**
  (`RRF_K = 60`): `score(t) += 1.0 / (RRF_K + rank)` over the two ranked lists.
  Deterministic — the same inputs always produce the same ranking.
- **Limits**: `DEFAULT_RETRIEVAL_LIMIT = 10`, `MAX_RETRIEVAL_LIMIT = 25`.
- **Safety**: parameterized statements only (no string interpolation of user text),
  an explicit allowlist of the three generated text fields, the `itsm_readonly` role,
  and a sanitized retrieval trace.
- **"Similar" mode**: the reference ticket's stored embedding is used as the query
  vector and its text as the lexical query — no embedding call needed.
- **Count over content**: a separate statement with **no LIMIT** (a true total),
  matching when `fts @@ plainto_tsquery(...) OR (embedding <=> %s::vector) <= %s`,
  plus a small `LIMIT`-ed query for up to 5 example ticket_ids over the *same* match.
- **Why not through GraphJin?** GraphJin v3's semantic search is **catalog-level,
  not row-level**; it cannot return ticket-level top-N. This was an explicit human
  decision: content retrieval is an application-side *governed* channel with fixed
  parameterized statements, the same read-only role, and the same field allowlist.
  It is not an SQL bypass.

## B8. Count threshold calibration (app/ai/count_calibration.py)

The semantic distance threshold that decides "this ticket is about the topic" is
**calibrated, not guessed**:

- a deterministic sweep over candidate thresholds on the **development count cases
  only** (zero held-out leakage);
- dev exact-count accuracy **1.0 at 0.25**, and **0.2 at the neighbouring
  thresholds** — a real optimum, not a flat region;
- written to a versioned `count-threshold.json` with provenance and a recorded
  SHA-256; the runtime loads it from that file.

## B9. DSPy (app/ai/signatures.py, app/ai/query_program.py, app/ai/optimization.py)

**What DSPy is, in one line:** you declare *what* you want (typed signatures with
input/output fields and an instruction docstring), and an optimizer *teaches* the
program the task — the code does not change, the trained program (a JSON artifact)
does.

**Three signatures** (`PROMPT_VERSION = "3"`, bumped on any instruction change; no
hard-coded prompt strings — the instruction lives in the signature docstring):

- `ClassifyQuestion` — routes a question to exactly one of
  `content_about | content_similar | content_count | supported | ambiguous | unsupported`.
  Its docstring explicitly says to route **by meaning, not by word shape**, so deep
  paraphrases with no shared keywords reach retrieval. It also distinguishes a
  count over a *structured column* ("how many P1 tickets" → `supported`) from a
  count over a *topic* ("how many tickets about login" → `content_count`).
- `PlanQuery` — emits a typed governed request; documents the allowed fields,
  operations, filters, group_by, having, ratio and null handling, and the
  supported query shapes.
- `GroundAnswer` — answers **using only the provided execution evidence**.

**Why DSPy over hand-written prompts:**
1. The pipeline is built on signatures, not on ad-hoc prompt strings; a prompt
   change is a versioned decision.
2. The optimizer optimizes against a **binary, objective** metric
   (`text_to_query_metric`): it returns `1.0` only if *all* mandatory checks pass
   (structured output validates; request is read-only and policy-allowed; GraphJin
   executes; normalized result matches the labeled expectation; no prohibited
   effect and no unauthorized disclosure). Otherwise `0.0`. There is no
   "does the answer look right" estimate in the release gate.
3. Versioned, reproducible artifacts: `artifacts/optimization-run.json` records the
   optimizer inputs, the accepted demonstration IDs, the configuration, the output
   artifact hash, errors and versions.

**The approved optimizer configuration (and nothing else):**

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

Optimization runs only if at least 12 valid labeled development examples exist, and
consumes **development case IDs only** — the case library enforces that no
held-out ID enters optimization or calibration. **GEPA, MIPROv2, SIMBA and
fine-tuning are prohibited** in this project.

**DSPy is not a security layer.** Whatever the model emits is re-validated
deterministically, and authorization comes from the GraphJin policy and the
PostgreSQL role.

**Version history (feature 006):** DSPy 3.2.1 → 3.4.0 on Python 3.14.4. The
pre-upgrade artifacts were preserved byte-identical under `*-pre-006-2026-10-11.json`
names, a new 3.4.0 baseline and a re-optimized program were produced, and
`artifacts/cross-version-006.json` reports **no quality delta** between the
versions. The DSPy LM backend is pinned to the native `lm15` engine
(`engine="lm15"` in `app/ai/llm.py`).

## B10. Model and endpoint handling (app/ai/llm.py, app/ai/preflight.py)

- `LLMConfig` is loaded from the environment: provider, base_url, model, api_key,
  temperature, cache.
- `list_models()` / `verify_model()` call `GET /v1/models` to confirm the exact
  requested model is loaded. `REQUESTED_MODEL_ARTIFACT` records the approved
  `Qwen3.8-27B-UD-Q4_K_M.gguf`.
- **No fallback model and no cloud fallback.** Any endpoint or model failure raises
  `LLMEndpointError` and stops processing.
- Preflight order: (1) `GET /v1/models` returns the exact model ID, (2) one
  deterministic chat completion succeeds, (3) one typed DSPy prediction succeeds.
  Non-secret metadata is written to `artifacts/llm-preflight.json`; the private
  endpoint URL is recorded **only as a host-redacted presence flag**.
- The app still starts if the endpoint is unreachable (so `/health` works), but the
  query path returns a stable `dependency_error`.

## B11. Data

- **Source:** `https://github.com/drapertoby/itsm-ticket-dataset`, MIT license,
  attribution preserved, pinned to commit
  `cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b`, SHA-256 checksums recorded, raw
  files immutable, provenance in `artifacts/import-manifest.json`.
- **Scope:** 2057 tickets, plus merchants and agents; 12 governed ticket dimensions.
- **Generated text (feature 009):** `short_description`, `description`,
  `resolution_notes` per ticket, generated by the pinned local model (temp 0,
  recorded seed, batch 5, checkpoint/resume) through a governed offline pipeline;
  `resolution_notes` is NULL for the 250 open tickets. Validated by a deterministic
  offline suite (schema, coverage 2057/2057, length limits, English language,
  category consistency, NULL rule) and by **human data-quality review per category
  before import**. Imported atomically in the same transaction as the pinned CSVs.
- **Embeddings (feature 010):** one 768-dimensional vector per ticket from the
  concatenation of the three text fields (recorded separator; NULL fields are
  never replaced with a placeholder), produced by the pinned EmbeddingGemma-2
  model. Provenance manifest `data/raw/embeddings-manifest.json` includes the
  `source_gguf_sha256`
  (`6f1bd4ac6c5df7444f9cca7ca36cafe6cfa34cd6f49fefb1e0b4be8143aed8bc`).
- **Import:** atomic (all-or-nothing), idempotent, checksum-verified.
- **Database:** pinned `pgvector/pgvector:pg16`, named volume, healthcheck,
  explicit database creation, idempotent schema/role/index creation, a clean local
  reset path (`scripts/reset_database.py`), and a clean local reset path that never
  touches the immutable raw files.

## B12. Evaluation and the quality gate

**Case isolation.** `evaluation/dev_cases.json` (development) and
`evaluation/cases.json` (held-out) are **physically separate versioned files**;
security cases live in `evaluation/security_cases.json`. Stable unique case IDs.
`evaluation/schemas.py` loads them through `load_dev_cases()` and
`load_held_out_cases()` and enforces that no held-out ID enters optimization or
calibration.

**Metrics (`evaluation/metrics.py`) — all deterministic and model-free:**

| Metric | What it compares |
|---|---|
| `structural_validity` | the request parses and validates against the governed policy |
| `execution_accuracy` | the normalized executed result vs. the labeled expected result |
| `routing_correct` | the classifier category (+ the extracted ticket_id for `content_similar`) |
| `count_accuracy` / `false_count_rate` | exact count correctness / counting when it should not |
| `prohibited_effects` | DB snapshot diffs around each case |
| `disclosures` | canary values / endpoint details in responses, traces, errors |
| `false_refusal_rate` | legitimate requests that were refused (over-blocking) |
| latency | measured (median, p90, max) but **never** a pass/fail signal |

**The gate (`evaluation/compare.py`)** returns a **non-zero exit code** for:
a failed P1 quality threshold (structural validity < 0.90, execution accuracy
< 0.80); an execution-accuracy degradation greater than 5 percentage points; any
prohibited database effect; any unauthorized disclosure. Routing and count gates use
calibrated thresholds that clear the observed noise band.

**Commands:**

```bash
pytest -q
python -m evaluation.run --cache=false --output artifacts/current.json
python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json
python -m evaluation.run_security          # security suite
python -m evaluation.verify_examples        # demo example gallery gate
```

**Baseline discipline (feature 004):** pin all relevant versions and parameters;
measured-run temperature 0; model-response caching disabled; run a representative
sample 2–3 times to record per-metric noise; run the complete held-out evaluation;
save `artifacts/baseline.json`. Improvement is never claimed when the observed
intervals overlap.

**Current results (DSPy 3.4.0, Python 3.14.4, `artifacts/current.json`):**

| Metric | Value |
|---|---|
| Held-out cases | 57 (16 of them security) |
| Structural validity | 1.0 |
| Execution accuracy | 1.0 |
| Prohibited DB effects | 0 |
| Unauthorized disclosures | 0 |
| Routing accuracy | 0.9 |
| False routing rate | 0.0 |
| Count accuracy | 1.0 |
| False count rate | 0.0 |
| False refusals | 1 → false refusal rate 0.0244 (2.44%) |
| Latency (observational) | median 4680.58 ms, p90 11138.81 ms, max 16542.88 ms |
| Test suite | 664 tests, all passing (full gate 664/664 after feature 012) |

**Demo UI (feature 008):** a categorized gallery of 26 curated, corpus-verified
example questions (one click to run, including a labeled refusal demo), a
plain-language dataset overview card, rotating placeholder and typing suggestions.
Content lives in the version-controlled static asset `app/web/examples.json`; no
backend API change, no new runtime dependency.
`python -m evaluation.verify_examples` → 26/26 passed.

## B13. Security model — four independent layers

```
question → [injection telemetry: log only] → [typed allowlist]
         → [deterministic validator] → [GraphJin policy: default_block, allowlists, limit]
         → [PostgreSQL itsm_readonly: SELECT only, statement_timeout 5s]
         → [normalization] → [grounding check] → [deterministic redaction]
```

1. **Type-level allowlist** — only known entities, fields and operations.
2. **Deterministic validator** — pure function, no LLM, no I/O.
3. **GraphJin policy** — `default_block: true`, explicit allowlists, row limits,
   database-query timeout.
4. **PostgreSQL role** — `itsm_readonly`: SELECT only, `statement_timeout 5s`.
   INSERT, UPDATE, DELETE, TRUNCATE, CREATE, ALTER, DROP all fail with **zero
   database changes** (proved by tests).

These controls are kept independent: database-query timeout, overall request safety
timeout, and maximum result size are three separate mechanisms.

**How security is verified (not by wording):** by actual database effects, by the
returned records and field values, by traces and error responses, by deterministic
limits and policy decisions, and by measuring false refusals on legitimate requests.
Test-only canary values verify redaction. Any prohibited database effect,
unauthorized disclosure, seeded secret, complete prompt, or private endpoint value in
external output fails the gate.

**GDPR:** the dataset is synthetic and license-verified, so no real personal data is
processed. Traces never contain a complete prompt, credentials, or the private
endpoint. The remaining GDPR work (retention, DSAR, audit log) is a business-process
task, not an LLM problem.

## B14. Feature history (12 features, each with a spec and a human-approved gate)

| Feature | What it added |
|---|---|
| 001 Governed ITSM data foundation | pinned dataset, PostgreSQL, roles, GraphJin, read-only proof |
| 002 Conversational query pipeline | typed DSPy planning, deterministic validation, GraphJin execution, grounded answer, sanitized trace |
| 003 Security hardening | injection telemetry, deterministic boundaries, disclosure tests |
| 004 Evaluation and demo | dev/held-out split, baseline, BootstrapFewShot, regression gate, demo UI |
| 005 Analytics surface v2 | GROUP BY / having, is-null filtering, ratio/percentage metrics |
| 006 DSPy 3.4 upgrade | 3.2.1 → 3.4.0, re-baseline, re-optimization, cross-version report, `lm15` engine pin |
| 008 Query discovery UI | 26-example gallery, dataset overview card, guided input |
| 009 Synthetic ticket texts | 3 generated text columns per ticket, offline validation suite, human review, atomic import |
| 010 Hybrid search | embeddings, pgvector, HNSW + GIN, RRF fusion, governed retrieval channel |
| 011 Classifier content routing | tuned DSPy classifier replaces a regex router; ticket_id extraction |
| 012 Count over content | true hybrid count, calibrated semantic threshold, `content_count` category |

Each feature has `specs/<feature>/spec.md`, `plan.md`, `tasks.md` and a
`runner-report.md` explaining the decisions and the measured results.

## B15. Architecture diagram (for the user to redraw on a whiteboard)

```
                      ┌───────────────────────────────┐
   Analyst ─────────▶│  Web application (FastAPI)    │
   (browser)          │  /query  ·  /health  ·  /     │
                      └───┬───────────┬───────────┬───┘
                          │           │           │
              ┌───────────▼──┐   ┌────▼─────┐  ┌──▼───────────────┐
              │ Query program│   │ Validator│  │ Governed         │
              │ (DSPy)       │   │ (pure)   │  │ retrieval channel│
              └────┬─────────┘   └────┬─────┘  └──┬───────────────┘
                   │                  │            │
         ┌─────────▼────────┐  ┌──────▼───────┐    │
         │ Local LLM        │  │ GraphJin     │    │
         │ endpoint (pinned)│  │ client       │    │
         └──────────────────┘  └──────┬───────┘    │
                                       │            │
                                ┌──────▼────────────▼──────┐
                                │ GraphJin  →  PostgreSQL  │
                                │ (read-only role)         │
                                └───────────────────────────┘

   Operator ─▶ 9 offline CLI containers (init/reset, import, text generation,
                validation, embeddings, calibration, preflight, optimization)
           ─▶  Evaluation toolkit (run, run_security, compare, verify_examples)
           ─▶  Embedding endpoint (separate llama.cpp --embeddings instance)
```

---

# PART C — The job description, condensed, and the mapping

Job: **Applied AI Engineer – Conversational Analytics**, ALDI Hungary, IT,
1112 Budapest, Boldizsár utca 2, full-time, start as soon as possible.

**Responsibilities (R):** design/build/operate conversational analytics assistants
over company data with accurate, traceable answers; develop LLM applications and
agents in Python (text-to-SQL, tool calling, retrieval over documents and business
definitions); build evaluation pipelines (test sets, automated regression checks,
answer quality monitoring) so every prompt, model or data change is measured before
release; ensure security and compliance (permissions enforced in the backend,
prompt-injection protection, responsible handling of personal data under GDPR);
monitor and optimize production systems for accuracy, latency and cost (model
selection, caching, multiple languages); work with data engineers, analysts and
business stakeholders, and document all technical processes.

**Required knowledge (K):** strong Python (production services and APIs); hands-on
shipping LLM applications using managed model APIs; strong SQL and text-to-SQL or
other natural-language interfaces over structured data; RAG (parsing, chunking,
hybrid search, reranking); evaluating LLM systems (test sets, regression testing,
LLM-as-a-judge and its limits); agent design, tool calling, structured outputs,
context management; basic LLM security (prompt injection, access control) and data
protection (GDPR); basic data modelling and semantic layers (metric definitions,
business glossaries); pragmatic, data-centric mindset; structured analytical
thinking; strong communication with non-technical stakeholders; well organized.
**Nice to have:** Databricks Genie, Microsoft Fabric AI Agents, SAP Joule.

**Mapping to the project:**

| JD item | Project evidence | Notes to say out loud |
|---|---|---|
| Conversational analytics | `app/api/routes.py` pipeline, demo UI, 26-example gallery | the model answers only from executed evidence |
| Traceable answers | `app/observability/trace.py` + `is_grounded()` | every answer carries a sanitized trace |
| Python LLM apps / agents / tool calling / structured outputs | DSPy signatures, typed request, routing categories | no free-form SQL, ever |
| Text-to-SQL / NL interfaces | typed `StructuredQueryRequest` + GraphJin GraphQL | typing = authorization, measurement = correctness |
| RAG: parsing, chunking, hybrid search | ticket-text generation, one vector per ticket, ts_rank + pgvector + RRF(k=60) | chunking = ticket level; reranking is an explicit follow-up |
| Evaluation pipelines, regression checks | dev/held-out split, deterministic metrics, exit-code gate, per-case DB snapshots | "measured before optimizing" |
| LLM-as-a-judge | **not implemented** | deterministic metrics instead; judge only for non-programmable quality, calibrated against human labels |
| Managed model APIs | **self-hosted pinned model** | provider-neutral adapter layer; pin + no fallback is a deliberate choice |
| Security / prompt injection / access control | 4 independent layers, effect-based tests, canaries | the model is never the security layer |
| GDPR | synthetic, license-verified data; no prompt/credential/endpoint in traces | retention/DSAR are process work |
| Model selection, caching, cost | pinned model, cache disabled for measurement, no fallback, batch + checkpoint/resume | latency is observed, never a gate |
| Multiple languages | **not implemented** | roadmap; security layers are language-independent |
| Semantic layer / metric definitions | `ENTITIES` / `COLUMN_TYPES` / `RELATIONSHIPS` allowlist, count/sum/avg/ratio | a versioned business glossary is the next step |
| Communication with non-technical stakeholders | demo gallery with plain-language examples and a labeled refusal demo | explain what the AI can and cannot do |
| Documentation for operational continuity | `specs/` with spec/plan/tasks/runner-report per feature | traceable to task IDs |
| Databricks / Fabric / Joule | **no experience** | same primitives: NL→query, entity allowlist, authorization in the query engine, eval pipeline |

---

# PART D — Real gaps (the user must own these, not hide them)

1. **LLM-as-a-judge is not implemented.** All release-gate metrics are deterministic
   and model-free. Where correctness is not programmable (answer clarity, tone), a
   calibrated LLM judge would be added — as a *supplementary* metric, validated
   against human labels and a measured agreement rate, never as the gate.
2. **No multilingual support.** The demo runs on English text. The pipeline syntax
   is language-independent; the embedding model and prompts are not.
3. **No LLM reranking.** The baseline is deterministic RRF fusion. An LLM that reads
   each candidate against the question would be more precise for vague queries, but
   it is non-deterministic, costs one model call per candidate, and needs a measured
   quality-gain comparison against the RRF baseline before adoption.
4. **No per-field (multi-vector) retrieval.** One vector per ticket from the three
   concatenated text fields. A question targeting one field ("how was it resolved?")
   would not retrieve well. Also affects the 250 open tickets whose
   `resolution_notes` is NULL.
5. **No grouped count over content** ("how many tickets about X per category").
6. **No versioned business glossary** — fields and metrics are defined, but not in a
   versioned natural-language definition layer.
7. **Self-hosted model, not a managed API.** The architecture is provider-neutral
   (one OpenAI-compatible client), but there is no managed-API production experience.
8. **False refusal rate 2.44%** (1 of 57 legitimate cases refused). Over-blocking is
   also a failure and is measured, not hidden.
9. **Semantic nonsense is not detected at runtime.** A well-formed, allowed but
   meaningless request (e.g. a non-existent priority value) runs and returns zero
   rows; only the evaluation notices. The next step would be an
   "empty result with a very narrow filter" detector that asks the user to clarify.
10. **Routing accuracy is 0.9, not 1.0** — hence the dedicated `false_routing_rate`
    metric and the conservative fallback to the structured path.

---

# PART E — Tasks the AI assistant should perform

When the user asks, do the following. Default to doing the first one.

### E1. Mock interview (default)
Act as the ALDI hiring manager. Ask **one** question at a time, wait for the answer,
then give: (a) what worked, (b) what to cut, (c) a sharper rewrite of the answer in
3–5 spoken sentences, (d) the likely follow-up question. Use the Part C mapping for
the question order. Escalate: easy → medium → hard (security, evaluation
methodology, trade-offs, gaps).

### E2. Quiz on the numbers
Ask the user to state from memory: the number of held-out cases, execution
accuracy, prohibited effects, disclosures, routing accuracy, count accuracy, the
false-refusal rate, the RRF k value, the calibrated semantic threshold, the embedding
dimension, the max retrieval limit, the max query limit, the size of the test suite.
Correct any wrong answer and explain why the exact number matters.

### E3. Technical deep-dive
Pick a component from Part B (e.g. the validator, the RRF fusion, the count
calibration, the DSPy metric, the redaction) and ask the user to explain it as if to
a colleague, then drill into edge cases: what happens with an empty result, a null
ratio, an unknown classifier category, a missing endpoint, a held-out ID in the
optimizer.

### E4. Rewrite into STAR answers
Turn the user's rough notes into Situation–Task–Action–Result answers of 60–90
seconds, using only facts from Parts B and F. Flag anything the user claims that
the brief does not support.

### E5. Gap rehearsal
Ask the user to answer the hardest questions about the gaps in Part D (no judge, no
multilingual, no reranking, no managed API, 2.44% false refusals) — then compare
their answer with a model answer that is honest, specific and turns the limitation
into a plan.

### E6. Elevator pitch variants
Produce 30-second, 60-second and 3-minute pitches, in Hungarian and in English.

### E7. Whiteboard rehearsal
Ask the user to describe the architecture from memory and check it against the
diagram in B15 and the flows in B3.

### E8. Salary/fit questions
Help the user prepare honest, non-pompous answers to "why ALDI", "why leave",
"what salary do you expect", "what would you do in the first month" — grounded in
the project facts.

---

# PART F — Cheat sheet (memorize)

| Item | Value |
|---|---|
| Project | Governed Conversational Analytics (12 features, all human-approved) |
| Dataset | synthetic ITSM helpdesk, MIT, commit `cf2e4e07ebcabb9c1234642585ee6f5bc2aa3e1b`, 2057 tickets, 12 governed dimensions |
| Models | Qwen3 27B Q4_K_M (chat, pinned) + EmbeddingGemma-2 768-dim (separate llama.cpp `--embeddings` instance) |
| Stack | Python 3.14.4, DSPy 3.4.0 (`engine="lm15"`), FastAPI, PostgreSQL 16 + pgvector 0.8.7, GraphJin v3, psycopg |
| Evaluation | 57 held-out cases (16 security), execution accuracy 1.0, structural validity 1.0, 0 prohibited effects, 0 disclosures, routing accuracy 0.9, false routing 0.0, count accuracy 1.0, false count 0.0, false refusal 2.44% |
| Latency (observational) | median 4.68 s, p90 11.14 s, max 16.54 s |
| Tests | 664, all passing; every feature has its own approved gate |
| Security layers | typed allowlist → deterministic validator → GraphJin policy (`default_block`) → read-only DB role (SELECT only, 5 s timeout) |
| Injection classifier | telemetry only, never authorizes or blocks |
| Retrieval | ts_rank + pgvector cosine → deterministic RRF, k=60; limit default 10, max 25 |
| Count over content | true total, no LIMIT; semantic threshold 0.25 (calibrated on dev, dev accuracy 1.0 vs 0.2 at neighbours) |
| Optimizer | `dspy.BootstrapFewShot(metric_threshold=1.0, max_bootstrapped_demos=4, max_labeled_demos=4, max_rounds=1, max_errors=3)`, dev cases only |
| Prohibited | GEPA, MIPROv2, SIMBA, fine-tuning; arbitrary SQL; model fallback; latency as a quality gate; real/personal data |
| Best single sentence | "The model is never the security boundary — and the boundary is where we can actually measure it." |
| Best closing line | "I did not optimize the model first. I built the measurement, then optimized." |
