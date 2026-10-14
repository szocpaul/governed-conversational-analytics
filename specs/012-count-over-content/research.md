# Phase 0 Research: Count over Content

**Feature**: 012-count-over-content | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

All design unknowns from the plan's Technical Context are resolved below.
Each entry: Decision / Rationale / Alternatives considered. Grounding:
`app/ai/retrieval.py` (the governed retrieval channel: allowlist, read-only
role, parameterized SQL, sanitized trace, MAX_RETRIEVAL_LIMIT=25),
`app/ai/routing.py` + `app/ai/signatures.py` (the feature 011 classifier
routing), `evaluation/metrics.py` (the held-out gate), and a live probe of
`pgvector/pgvector:pg16` verifying the hybrid-count SQL shape.

## R1 — Governed hybrid count query (lexical OR semantic-within-threshold)

**Decision**: A single governed, parameterized COUNT query over the
allowlisted text fields: a ticket matches when
`fts @@ plainto_tsquery('english', :q)` (lexical) OR
`(embedding <=> :qvec) <= :threshold` (semantic). The query text `:q`, the
embedded query vector `:qvec`, and the threshold `:threshold` are all bound
parameters — never interpolated — so no arbitrary SQL is possible. The query
connects as the `itsm_readonly` role and returns one number plus up to 5
example ticket_ids for grounding.

**Rationale**: Human decision 1 (hybrid). The lexical side is deterministic
and threshold-free; the semantic side catches deep paraphrases that share no
keywords. The OR semantics means a ticket is counted once whether it matches
lexically, semantically, or both. The SQL shape was verified live against
`pgvector/pgvector:pg16` (`WITH q AS (...) SELECT count(*) ... WHERE fts @@ q.qts OR (emb <=> q.qvec) <= :threshold`).

**Alternatives considered**: (a) Lexical-only count — rejected by the human
(misses paraphrases). (b) Semantic-only count — rejected: needs the
threshold for ALL matches and loses the deterministic exact-word signal.
(c) Retrieval-then-count — rejected: the list is capped at 25 and would
undercount (88 login tickets would report 25).

## R2 — The count is a true total, never capped

**Decision**: The count query has NO LIMIT clause on the count itself — it
counts ALL matching tickets. Only the example ticket_ids for grounding are
capped (at 5), and they come from a separate small LIMITed selection over
the same match condition.

**Rationale**: FR-003 / SC-003. The whole point is that "how many tickets
about login" returns 88, not 25. The retrieval result limit exists for
context size in the LIST path; a COUNT has no such constraint and is cheap.

**Alternatives considered**: Counting the retrieval list — rejected
(undercounts). A separate COUNT with the list's LIMIT — rejected (same
undercount).

## R3 — Semantic-match threshold calibration (deterministic sweep)

**Decision**: The semantic threshold is calibrated by a DETERMINISTIC sweep
over the development count cases: for a grid of candidate thresholds, embed
each dev question, compute the resulting count against the labeled true
count, and pick the threshold that maximizes exact-count accuracy on dev
(ties broken toward the larger threshold = more inclusive, then recorded).
The calibrated threshold is written to a versioned, committed artifact
(`count-threshold.json`) with provenance (calibration dev IDs, method,
created_at, artifact SHA-256). This is a deterministic sweep, NOT a
forbidden optimizer (no GEPA/MIPROv2/SIMBA).

**Rationale**: Human decision 3. A threshold sweep over a handful of dev
cases is simple, deterministic, auditable, and does not need a learned
optimizer. Recording the threshold as a versioned artifact satisfies FR-005
(never hardcoded; absent/uncalibrated -> stop and report).

**Alternatives considered**: (a) A hardcoded threshold — rejected: FR-005
forbids it. (b) BootstrapFewShot to "learn" the threshold — rejected: the
threshold is a scalar, not a prompt; a sweep is the right tool and avoids
any optimizer question. (c) A per-query adaptive threshold — rejected:
non-deterministic and unmeasurable at this scale.

## R4 — Routing: a content_count category in the 011 classifier

**Decision**: The feature 011 `ClassifyQuestion` gains a `content_count`
category. The docstring (versioned instruction) is extended: a question
asking "how many tickets about X" / "how many tickets are about X" (a count
over a topic) is `content_count`, NOT `supported`. `app/ai/routing.py`
dispatches `content_count` to the count path. PROMPT_VERSION is bumped. The
classifier is re-tuned with the approved bounded BootstrapFewShot on the
extended dev set (routing + count cases), dev-only.

**Rationale**: Human decision 2. One classifier routes everything (the 011
discipline); adding a category is consistent. The key instruction change is
that a count over a TOPIC routes to content_count, while a count over a
STRUCTURED value ("how many P1 tickets") stays `supported`.

**Alternatives considered**: (a) A deterministic count-keyword + about
detector before the classifier — rejected by the human (decision 2 chose
the classifier category). (b) A separate count classifier — rejected: two
classifiers, two routing decisions, an extra model call.

## R5 — False-count guard and structured non-regression

**Decision**: The feature 011 false-routing metric is extended with the
`content_count` category: it counts (a) count-over-content questions
mis-routed to the structured path (which would return a misleading 0) and
(b) structured count questions mis-routed to content_count. The structured
execution-accuracy gate must not regress. Both thresholds are set after a
noise calibration run (the same artifact measured 2-3 times at temperature
0).

**Rationale**: Human decision 6. The structured path is proven and must not
degrade; the new category introduces a new mis-routing risk that must be
measured and bounded.

**Alternatives considered**: (a) No guard — rejected: a tuned classifier
could silently mis-route counts. (b) A fixed arbitrary threshold — rejected:
risks being inside the noise band.

## R6 — Grounding the count answer

**Decision**: The answer grounds on the count (a single number) plus up to 5
example ticket_ids drawn from the same match condition (capped, sanitized).
The trace records the count and the example ids. If the count query fails or
the threshold is absent, the answer path returns a stable clarification or
dependency error — never a fabricated number.

**Rationale**: Human decision 4. A bare number is unverifiable; a few example
tickets make the count transparent without the context-size cost of a full
list. FR-014-style grounding (feature 010) applies: no fabrication.

**Alternatives considered**: (a) Count only, no examples — rejected: less
transparent. (b) A full list — rejected: context-size cost and unnecessary
for a count question.

## R7 — Count-over-content case categories and counts

**Decision**: New labeled cases reuse the existing `EvalCase` schema. New
category `count_content` (plus a `security_*` count case). The `expected`
field carries the labeled true count (and optionally the expected matching
categories for spot-checks). Counts: +5 development cases in
`evaluation/dev_cases.json` and +6 held-out cases in `evaluation/cases.json`,
physically separate, stable unique IDs, including a security count case.

**Rationale**: Human decision 5. Reusing the existing schema and files keeps
one isolation story and lets the existing leakage guard protect the new
cases unchanged.

**Alternatives considered**: (a) A separate count-cases file — rejected:
breaks the single dev/held-out isolation structure.

## R8 — Test strategy (stubbed for unit, live for gated validation)

**Decision**: Unit tests cover: count SQL construction (parameterized, no
arbitrary SQL), field-allowlist enforcement, threshold validation (absent/
uncalibrated -> error), and content_count routing (including conservative
fallback). Integration tests cover end-to-end on the live stack: "how many
tickets about login" returns the true count (not 0, not 25); a paraphrase
count includes semantic matches; a structured count is unchanged; a security
count case returns nothing prohibited. The threshold calibration and the
held-out count evaluation are quickstart/validation procedures whose outputs
are committed and then verified by deterministic tests — not pytest live
tests.

**Rationale**: AGENTS.md forbids simulated results for shipped artifacts but
unit tests are standard for logic; keeping the calibration and live count
eval out of pytest keeps the 622-test suite fast and hermetic.

**Alternatives considered**: Live pytest count tests as default — rejected:
endpoint availability would gate unrelated CI.
