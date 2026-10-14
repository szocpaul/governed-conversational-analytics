# Tasks: Count over Content

**Input**: Design documents from `/specs/012-count-over-content/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — AGENTS.md requires tests before implementation, with the
expected failure observed first. Unit tests cover logic without an LLM; the
calibrated threshold and all count metrics only ever come from real recorded
runs (research R8).

**Organization**: Tasks are grouped by user story (US1 true count over content
= P1, US2 calibrated threshold + measured quality = P2). US2 hard-depends on
US1 (the count path must exist before the threshold can be calibrated and
measured).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2 — maps to spec.md user stories
- All file paths are repository-relative

## Phase 1: Setup

- [X] T001 Record the pre-implementation baseline in `specs/012-count-over-content/runner-report.md` (skeleton): current git commit + working-tree state, and `pytest -q` result (expect 622 passed, 0 failed). Do not overwrite unrelated user changes.
- [X] T002 [P] Endpoint preflight per the `app/ai/llm.py` discipline: verify the pinned chat model ID (`models\Qwen3.8-27B-UD-Q4_K_M.gguf`) responds AND the pinned embedding model ID (`models\embeddinggemma-2-Q8_0.gguf`) responds on the embeddings route (chat for classification, embedding for the count query text). STOP AND REPORT on any mismatch — no fallback.

## Phase 2: Foundational (tests first — BLOCKS all user stories)

- [X] T003 [P] Write `tests/unit/test_count_query.py`: the governed hybrid count query in `app/ai/retrieval.py` — the SQL is a fixed parameterized statement (query text, query vector, and threshold as bound parameters; assert no arbitrary SQL string interpolation of the query text); the field allowlist is enforced (only the three generated text fields via the fts/embedding columns); the count has NO LIMIT clause (true total); the example-ids selection is capped at 5; an absent/uncalibrated threshold raises a loud error (never a hardcoded default). Run `pytest tests/unit/test_count_query.py -q` and observe FAIL (count query missing).
- [X] T004 [P] Write `tests/unit/test_count_routing.py` with a stubbed LM (`dspy.utils.DummyLM`): the extended `ClassifyQuestion` parses the `content_count` category alongside the existing five; "how many tickets about login" routes to the count path (not the structured planner); "how many P1 tickets" routes to the structured path; unparseable/unknown category output triggers the conservative fallback to the structured path. Run and observe FAIL (content_count category / dispatch missing).

## Phase 3: User Story 1 — True count over content via a governed hybrid count (P1) 🎯 MVP

**Goal**: "how many tickets about X" returns the TRUE count of matching
tickets (lexical OR semantic-within-threshold), not 0 and not a capped list
length, via a governed read-only hybrid count query, grounded with up to 5
example ticket_ids.

**Independent Test**: Ask "how many tickets about login" and verify it
returns the true count (not 0, not 25); ask a paraphrase count and verify
semantic matches are included; ask a structured count and verify it is
unchanged.

- [X] T005 [US1] Implement the governed hybrid count query in `app/ai/retrieval.py` per contracts/count-query.md: a fixed parameterized COUNT statement — `count(*) WHERE fts @@ plainto_tsquery('english', %s) OR (embedding <=> %s::vector) <= %s` — connecting as `itsm_readonly`; NO LIMIT on the count (true total); a separate small LIMITed selection (<= 5) over the SAME match condition for the example ticket_ids; the query text embedded via the pinned EmbeddingGemma-2 endpoint; the threshold loaded from `count-threshold.json` (absent/uncalibrated -> loud error); sanitized trace (count + up to 5 example ids). Iterate until T003 passes.
- [X] T006 [US1] Extend `app/ai/signatures.py` `ClassifyQuestion` per contracts/routing.md: add the `content_count` category; extend the docstring (versioned instruction) — a COUNT over a TOPIC ("how many tickets about X") is `content_count`, NOT `supported`; a COUNT over a STRUCTURED value ("how many P1 tickets") stays `supported`; a LIST about a topic is `content_about`; when uncertain prefer `supported`. Bump `PROMPT_VERSION`. Iterate until T004 (classification part) passes.
- [X] T007 [US1] Integrate the count path into `app/ai/routing.py` and `app/api/routes.py` per contracts/routing.md (depends on T005, T006): dispatch `content_count` -> embed query text -> governed hybrid count -> ground the answer on the count plus up to 5 example ticket_ids (never fabricate; absent threshold -> stable dependency error); `supported`/`content_about`/`content_similar`/`ambiguous`/`unsupported` unchanged; conservative fallback to the structured path. Iterate until T004 passes.
- [X] T008 [US1] Write `tests/integration/test_count_over_content_e2e.py` (depends on T007, live stack): "how many tickets about login" returns the true count (lexical + semantic; NOT 0, NOT 25); a paraphrase count ("how many tickets are about sign-in problems") includes semantic matches; a topic with few matches returns the exact small count; "how many P1 tickets" returns the structured count unchanged (112); the trace shows the count + up to 5 example ids with no credentials/endpoints/prompts. Run against the live stack and iterate until pass.

## Phase 4: User Story 2 — Calibrated threshold and measured count quality under isolation (P2)

**Goal**: The semantic threshold is calibrated on dev cases only, count
accuracy is measured on the held-out set, the structured path does not
regress, false-count routing is bounded, and if the threshold is not reached
the run stops and reports to the human.

**Independent Test**: Calibrate the threshold on dev cases; run the held-out
evaluation; verify count accuracy meets the threshold, the structured
execution-accuracy gate does not regress, the false-count rate is bounded,
and zero held-out IDs appear in the calibration input.

- [X] T009 [P] [US2] Add +5 count-over-content development cases to `evaluation/dev_cases.json` per contracts/evaluation.md (physically separate from held-out; stable unique IDs; category `count_content`; `expected` = `{"count": <int>}` plus optional `"relevant_categories"`).
- [X] T010 [P] [US2] Add +6 held-out count-over-content cases to `evaluation/cases.json` per contracts/evaluation.md (physically separate from dev; stable unique IDs; `count_content` PLUS a `security_*` count case that must return nothing prohibited).
- [X] T011 [US2] Implement `app/ai/count_calibration.py` and the count/false-count metrics in `evaluation/metrics.py` per contracts/evaluation.md (depends on T009): a deterministic distance sweep over the development count cases (a grid of candidate thresholds; embed each dev question; compute the count; pick the threshold maximizing exact-count accuracy on dev, ties toward the larger threshold) writing `count-threshold.json` (threshold, version, calibration_method, calibration_dev_ids, created_at, artifact_sha256); count-accuracy (exact match) and false-count routing metrics; the sweep consumes development cases ONLY (guarded by `assert_no_held_out_leakage`).
- [X] T012 [US2] Noise calibration (quickstart step 1): run the held-out evaluation on the CURRENT program 2-3 times at temperature 0 (`python -m evaluation.run --cache=false --output /tmp/eval_cal_N.json`), record the count-relevant noise band, and set the count-accuracy and false-count thresholds ABOVE the noise band. Record the thresholds in the runner notes.
- [X] T013 [US2] Run the threshold calibration + classifier re-tuning (quickstart step 2, depends on T011, T012): run the deterministic threshold sweep (writes `count-threshold.json`); re-tune the extended classifier with the approved bounded BootstrapFewShot on the extended dev set (routing + count cases), dev-only, recording provenance in `artifacts/optimization-run.json`. Verify zero held-out IDs in both the sweep and the tuning trainset.
- [X] T014 [US2] Run the held-out evaluation + comparison (quickstart step 4, depends on T013): `python -m evaluation.run --cache=false --output artifacts/current.json` then `python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json`; verify count accuracy >= calibrated threshold, false-count rate <= calibrated bound, the structured execution-accuracy gate does NOT regress, and security count cases return nothing prohibited. Regenerate `artifacts/baseline.json` (pre-012 preserved) to include count metrics. If count accuracy does NOT reach the threshold: STOP AND REPORT to the human — do not ship an uncalibrated/degraded count.
- [X] T015 [US2] Write `tests/integration/test_count_eval.py` (depends on T014): deterministic checks that the count case files are physically separate with disjoint IDs, the leakage guard rejects any held-out ID in a calibration trainset, the count-accuracy metric returns correct values on canary cases, and the committed `count-threshold.json` records only development case IDs and a valid threshold. (The live calibration and held-out eval are quickstart procedures, not pytest.)

## Phase 5: Polish & Validation

- [X] T016 Run the full validation gate set from `specs/012-count-over-content/quickstart.md` steps 1-5: `pytest -q` green (all 622 pre-existing + new tests, SC-009); count smoke test passes (true count, paraphrase count, no undercount, structured unchanged); held-out gate passes. Fix any failure at its source.
- [X] T017 Verify artifact pinning: recompute SHA-256 of `count-threshold.json` and confirm it equals the recorded `artifact_sha256`; confirm the calibration dev IDs are development case IDs only; confirm `app/ai/optimized_program.json` matches the `output_artifact_sha256` in `artifacts/optimization-run.json`.
- [ ] T018 Complete `specs/012-count-over-content/runner-report.md` per the AGENTS.md Required Final Report: completed/blocked task IDs, files changed, commits, exact pinned versions, validation commands with exact results, the calibrated threshold + noise-calibration thresholds, count accuracy + false-count + structured-regression results, security count-case results, latency (median, p90, max, observational), known limitations.

## Dependencies

```text
T001 -> T002 (baseline first; preflight parallel)
T003/T004 parallel (different test files) — both must FAIL before implementation
T003 -> T005; T004 -> T006; T005 + T006 -> T007; T007 -> T008
T009/T010 parallel (separate eval files); T009 -> T011
T011 -> T012 -> T013 -> T014 -> T015 (noise -> calibration+tuning -> held-out gate -> eval tests)
T008 (US1) before T013 (US2 calibration needs the count path)
T016/T017 depend on all stories; T018 last
```

User stories are sequential: US2 (calibration/eval) consumes the US1 count
path. Within phases, the marked [P] tasks are parallel.

## Parallel Execution Examples

- T003 and T004 written in parallel (two different test files).
- T009 and T010 in parallel (separate evaluation files).
- T005 (count query) and T006 (signature) in parallel once their tests exist.

## Implementation Strategy

1. Setup + Foundational (T001-T004): baseline, preflight, failing tests.
2. MVP = Phase 3 (US1): the governed hybrid count returning true totals.
3. Increment: US2 (threshold calibration + held-out evaluation under
   isolation).
4. Polish: gates + pinning verification + runner report.

## Notes

- [P] tasks = different files, no dependencies
- Tests MUST be observed failing before their implementation task starts
- The calibrated threshold and the tuned artifact are NEVER hand-edited; they
  come only from a real calibration sweep / BootstrapFewShot run on dev cases
- Commit after each task or logical group; keep task IDs in commit messages
- The private chat/embedding endpoints, credentials, and prompts must not
  appear in user-facing output, committed files, or traces
- Count latency is observational only — never a pass/fail gate
- If count accuracy does not reach the threshold, STOP AND REPORT to the
  human — do not ship an uncalibrated/degraded count, do not use
  GEPA/MIPROv2/SIMBA (AGENTS.md prohibition)
- Grouped counts over content ("per category") are out of scope; the
  retrieval list path and the structured planner are frozen
