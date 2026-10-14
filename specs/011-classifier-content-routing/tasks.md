# Tasks: Classifier-Based Content Routing

**Input**: Design documents from `/specs/011-classifier-content-routing/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — AGENTS.md requires tests before implementation, with the
expected failure observed first. Unit tests stub the LM (`dspy.utils.DummyLM`);
the shipped tuned artifact and all routing metrics only ever come from real
recorded runs (research R9).

**Organization**: Tasks are grouped by user story (US1 meaning-based routing =
P1, US2 measured tuning under isolation = P2). US2 hard-depends on US1 (the
extended classifier must exist before it can be tuned and evaluated).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2 — maps to spec.md user stories
- All file paths are repository-relative

## Phase 1: Setup

- [X] T001 Record the pre-implementation baseline in `specs/011-classifier-content-routing/runner-report.md` (skeleton): current git commit + working-tree state, and `pytest -q` result (expect 571 passed, 0 failed). Do not overwrite unrelated user changes.
- [X] T002 [P] Endpoint preflight per the `app/ai/llm.py` discipline: verify the pinned chat model ID (`models\Qwen3.8-27B-UD-Q4_K_M.gguf`) responds on the configured endpoint AND the pinned embedding model ID (`models\embeddinggemma-2-Q8_0.gguf`) responds on the embeddings route (both are needed: chat for classification, embedding for retrieval). STOP AND REPORT on any mismatch — no fallback.

## Phase 2: Foundational (tests first — BLOCKS all user stories)

- [X] T003 [P] Write `tests/unit/test_ticket_id_extractor.py`: the deterministic extractor in `app/ai/routing.py` returns the reference ticket_id for "tickets similar to 847207", "similar to ticket 847207", and "find tickets like 847207"; returns None when no plausible id is present; does NOT false-positive on priorities (P1-P4), counts, limits, or other numbers; anchored to the pinned ticket-id shape. Run `pytest tests/unit/test_ticket_id_extractor.py -q` and observe FAIL (`app/ai/routing.py` missing).
- [X] T004 [P] Write `tests/unit/test_routing_classifier.py` with a stubbed LM (`dspy.utils.DummyLM`): the extended `ClassifyQuestion` parses all five categories (`content_about`, `content_similar`, `supported`, `ambiguous`, `unsupported`); unparseable or unknown category output triggers the conservative fallback to the structured path; a `content_about` classification routes to the retrieval dispatch (not the structured planner); a `content_similar` classification plus a deterministic ticket_id routes to retrieval similar-mode; a `supported` classification routes to the structured planner unchanged. Run and observe FAIL (extended signature / dispatch missing).

## Phase 3: User Story 1 — Meaning-based content routing via a tuned classifier (P1) 🎯 MVP

**Goal**: Content questions — including deep paraphrases — route to governed
retrieval, while structured questions route to the structured path unchanged
and unsupported questions are refused, all via ONE extended classifier (the
regex router removed).

**Independent Test**: Ask deep paraphrase content questions and verify they
route to retrieval and return relevant tickets; ask structured questions and
verify they route to the structured path exactly as before; ask unsupported
questions and verify they are refused.

- [ ] T005 [US1] Extend `app/ai/signatures.py` `ClassifyQuestion` per contracts/classifier-signature.md: add `content_about` and `content_similar` to the `category` output field; extend the docstring (the versioned instruction) to define the content categories — content_about = find tickets by their text content INCLUDING deep paraphrases with zero shared keywords (e.g. "customers unable to complete a purchase because their card was rejected"); content_similar = find tickets similar to a referenced ticket; a COUNT/AGGREGATE/GROUP_BY question is `supported` even when it mentions a topic ("how many tickets about login" -> supported); when uncertain prefer `supported` (conservative fallback). Bump `PROMPT_VERSION`. Iterate until T004 (classification part) passes.
- [ ] T006 [P] [US1] Implement `app/ai/routing.py` per contracts/routing-integration.md: the deterministic ticket_id extractor (pure function, no LLM, no I/O; returns the reference id or None; anchored to the pinned ticket-id shape, no false positives on priorities/counts) and routing-dispatch helpers mapping a category to the governed path. Iterate until T003 passes.
- [ ] T007 [US1] Integrate routing into `app/api/routes.py` and `app/ai/query_program.py` per contracts/routing-integration.md (depends on T005, T006): REMOVE `_ABOUT_RE`, `_SIMILAR_RE`, and `_route_content_question`; dispatch on the classifier category — `content_about` -> governed retrieval (embed query text via the pinned embedding endpoint, retrieve, ground, sanitized trace, reusing feature 010 `_run_retrieval`); `content_similar` -> deterministic ticket_id extraction -> governed retrieval similar-mode (None id -> stable clarification); `supported` -> structured planner unchanged; `ambiguous`/`unsupported` -> stable clarification/refusal unchanged; unparseable/unknown -> conservative fallback to the structured path. Iterate until T004 passes.
- [ ] T008 [US1] Write `tests/integration/test_content_routing_e2e.py` (depends on T007, live stack): a deep paraphrase content question ("customers unable to complete a purchase because their card was rejected") routes to retrieval and returns Card Declines tickets; "locked out, can't prove who you are at sign-in" routes to retrieval and returns Account Access tickets; "tickets similar to 847207" routes to retrieval similar-mode and returns same-category tickets; "how many tickets about login" routes to the STRUCTURED path (a count), NOT retrieval; "how many P1 tickets" routes to the structured path unchanged; an unsupported question is refused. Run against the live stack and iterate until pass.

## Phase 4: User Story 2 — Measured tuning under dataset isolation (P2)

**Goal**: The classifier is tuned with BootstrapFewShot on dev routing cases
only, routing accuracy is measured on the held-out set, the structured path
does not regress, false-routing is bounded, and if the threshold is not
reached the run stops and reports to the human.

**Independent Test**: Run BootstrapFewShot on the dev routing cases; run the
held-out evaluation; verify routing accuracy meets the calibrated threshold,
the structured execution-accuracy gate does not regress, the false-routing
rate is bounded, and zero held-out IDs appear in the tuning input.

- [ ] T009 [P] [US2] Add +8 routing development cases to `evaluation/dev_cases.json` per contracts/evaluation.md (physically separate from held-out; stable unique IDs; categories `route_content_about`, `route_content_similar`, `route_structured`, `route_unsupported`; including deep paraphrases; `expected` = `{"route": ...}` plus `"ticket_id"` for content_similar).
- [ ] T010 [P] [US2] Add +10 held-out routing cases to `evaluation/cases.json` per contracts/evaluation.md (physically separate from dev; stable unique IDs; same category mix PLUS `security_*` content cases that must return nothing prohibited).
- [ ] T011 [US2] Add the routing metric and metrics to `app/ai/optimization.py` and `evaluation/metrics.py` per contracts/evaluation.md (depends on T009): a binary routing metric (1.0 when the classifier category matches the labeled route and, for content_similar, the extracted ticket_id matches; else 0.0) for BootstrapFewShot; routing-accuracy and false-routing metrics for the held-out gate; a routing trainset builder consuming development routing cases ONLY (guarded by `assert_no_held_out_leakage`).
- [ ] T012 [US2] Noise calibration (quickstart step 1): run the held-out evaluation on the CURRENT program 2-3 times at temperature 0 (`python -m evaluation.run --cache=false --output /tmp/eval_cal_N.json`), record the routing-relevant noise band, and set the routing-accuracy and false-routing thresholds ABOVE the noise band. Record the thresholds in the runner notes.
- [ ] T013 [US2] Run BootstrapFewShot tuning on the dev routing cases (quickstart step 2, depends on T011, T012): the approved bounded config (`optimizer_config()`), the routing metric, dev-only trainset; produce a tuned `app/ai/optimized_program.json` (routing demos added) and record provenance in `artifacts/optimization-run.json` (optimizer config, accepted demo IDs, artifact hash, versions). Verify zero held-out IDs in the trainset.
- [ ] T014 [US2] Run the held-out evaluation + comparison (quickstart step 4, depends on T013): `python -m evaluation.run --cache=false --output artifacts/current.json` then `python -m evaluation.compare --baseline artifacts/baseline.json --current artifacts/current.json`; verify routing accuracy >= calibrated threshold, false-routing rate <= calibrated bound, the structured execution-accuracy gate does NOT regress, and security content cases return nothing prohibited. Regenerate `artifacts/baseline.json` (pre-011 preserved) to include routing metrics. If routing accuracy does NOT reach the threshold: STOP AND REPORT to the human — do not ship a degraded router, do not use GEPA/MIPROv2/SIMBA.
- [ ] T015 [US2] Write `tests/integration/test_routing_eval.py` (depends on T014): deterministic checks that the routing case files are physically separate with disjoint IDs, the leakage guard rejects any held-out ID in a routing trainset, the routing metric returns 1.0/0.0 correctly on canary cases, and the committed `artifacts/optimization-run.json` records only development case IDs. (The live tuning run and held-out eval are quickstart procedures, not pytest.)

## Phase 5: Polish & Validation

- [ ] T016 Run the full validation gate set from `specs/011-classifier-content-routing/quickstart.md` steps 1-5: `pytest -q` green (all 571 pre-existing + new tests, SC-008); routing smoke test passes (deep paraphrase -> retrieval, structured unchanged); held-out gate passes. Fix any failure at its source.
- [ ] T017 Verify artifact pinning (SC-006): recompute SHA-256 of `app/ai/optimized_program.json` and confirm it equals the `output_artifact_sha256` recorded in `artifacts/optimization-run.json`; confirm the accepted demo IDs are development case IDs only.
- [ ] T018 Complete `specs/011-classifier-content-routing/runner-report.md` per the AGENTS.md Required Final Report: completed/blocked task IDs, files changed, commits, exact pinned versions, validation commands with exact results, the noise-calibration thresholds, routing accuracy + false-routing + structured-regression results, security content-case results, latency (median, p90, max, observational), known limitations.

## Dependencies

```text
T001 -> T002 (baseline first; preflight parallel)
T003/T004 parallel (different test files) — both must FAIL before implementation
T003 -> T006; T004 -> T005; T005 + T006 -> T007; T007 -> T008
T009/T010 parallel (separate eval files); T009 -> T011
T011 -> T012 -> T013 -> T014 -> T015 (calibration -> tuning -> held-out gate -> eval tests)
T008 (US1) before T013 (US2 tuning needs the integrated classifier)
T016/T017 depend on all stories; T018 last
```

User stories are sequential: US2 (tuning/eval) consumes the US1 integrated
classifier. Within phases, the marked [P] tasks are parallel.

## Parallel Execution Examples

- T003 and T004 written in parallel (two different test files).
- T009 and T010 in parallel (separate evaluation files).
- T006 (`app/ai/routing.py`) in parallel with T005 (signatures) once their
  tests exist.

## Implementation Strategy

1. Setup + Foundational (T001-T004): baseline, preflight, failing tests.
2. MVP = Phase 3 (US1): the extended classifier routing deep paraphrases to
   retrieval while the structured path stays unchanged.
3. Increment: US2 (tuning + held-out evaluation under isolation).
4. Polish: gates + pinning verification + runner report.

## Notes

- [P] tasks = different files, no dependencies
- Tests MUST be observed failing before their implementation task starts
- The tuned artifact is NEVER hand-edited; it comes only from a real
  BootstrapFewShot run on dev cases
- Commit after each task or logical group; keep task IDs in commit messages
- The private chat/embedding endpoints, credentials, and prompts must not
  appear in user-facing output, committed files, or traces
- Routing latency is observational only — never a pass/fail gate
- If BootstrapFewShot does not reach the routing-accuracy threshold, STOP AND
  REPORT to the human — do not ship a degraded router, do not use
  GEPA/MIPROv2/SIMBA (AGENTS.md prohibition)
- UI changes are out of scope; the retrieval motor and the structured planner
  are frozen — only the routing decision changes
