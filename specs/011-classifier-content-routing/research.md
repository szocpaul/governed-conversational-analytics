# Phase 0 Research: Classifier-Based Content Routing

**Feature**: 011-classifier-content-routing | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

All design unknowns from the plan's Technical Context are resolved below.
Each entry: Decision / Rationale / Alternatives considered. Grounding:
`app/ai/signatures.py` (ClassifyQuestion), `app/ai/query_program.py`
(classification-driven planning), `app/api/routes.py` (the regex router being
replaced), `app/ai/optimization.py` (the approved BootstrapFewShot discipline
+ leakage guard), `evaluation/metrics.py` + `evaluation/run.py` (the held-out
gate), and the feature 010 retrieval path (frozen).

## R1 — One classifier, extended categories (router mechanism)

**Decision**: Extend the existing `ClassifyQuestion` signature with two new
output categories, `content_about` and `content_similar`, alongside the
existing `supported` / `ambiguous` / `unsupported`. ONE classifier routes
every question. The regex pair (`_ABOUT_RE`, `_SIMILAR_RE`) and
`_route_content_question` in `app/api/routes.py` are removed.

**Rationale**: Human decision 1. A single classifier makes a single routing
decision, which is simplest to reason about and to tune. The docstring (the
versioned instruction) is extended to define the content categories: a
question is `content_about` when it asks to find tickets by their text
content (including deep paraphrases), and `content_similar` when it asks for
tickets similar to a referenced ticket. PROMPT_VERSION is bumped.

**Alternatives considered**: (a) A separate DSPy content-router module
running before the existing classifier — rejected: two classifiers = two
routing decisions to reconcile, more failure modes, and an extra model call
(violates decision 7). (b) Keep the regex for explicit shapes and add a DSPy
"content fallback" — rejected: keeps the fragile regex alive and adds a
second, contradictory routing layer; the human chose to remove the regex.

## R2 — Deterministic ticket_id extraction for content_similar

**Decision**: A small pure function extracts the reference ticket_id from a
content_similar question (e.g. "similar to 847207", "tickets similar to
ticket 847207"). The classifier decides the mode; the extractor finds the
number. It returns the first plausible ticket_id (a 5-6 digit number in the
pinned ticket id range) or None; it never guesses.

**Rationale**: Human decision 5. A ticket_id is a number — trivially and
reliably extracted deterministically, with no LLM and no tuning. Keeping it
out of the classifier reduces what must be tuned and removes a whole failure
class (the classifier misreading the number).

**Alternatives considered**: (a) The classifier outputs the ticket_id as a
typed field — rejected: more to tune, more failure modes, for zero benefit
over a deterministic extractor. (b) Free-regex over the whole question —
rejected: too loose (would grab any number, e.g. a priority or a count); the
extractor is anchored to the pinned ticket-id shape.

## R3 — Conservative fallback on uncertainty

**Decision**: When the classifier output is missing, unparseable, or not one
of the known categories, routing defaults to the structured path (the
existing behavior for an unclear question). A missed content question then
yields a clarification from the structured path, never a fabricated answer.

**Rationale**: Human decision 6. A wrong structured answer is worse than a
missed content question: routing a content question to the structured path
produces "no matching data" (a safe clarification), whereas routing a
structured question to retrieval would produce a wrong answer shape. The
fallback is therefore asymmetric toward the structured path.

**Alternatives considered**: (a) Default to retrieval on uncertainty —
rejected: risks wrong-shape answers for structured questions. (b) A separate
"uncertain" category that always asks for clarification — rejected: adds a
category without improving the safe outcome; the structured path already
clarifies.

## R4 — Routing metric for tuning and the held-out gate

**Decision**: A binary routing metric: 1.0 when the classifier's category
matches the labeled routing category (and, for content_similar, the
extracted ticket_id matches the labeled reference), else 0.0. This metric
drives BootstrapFewShot (tuning signal on dev cases) and the held-out
routing-accuracy gate. A separate false-routing metric counts structured
questions mis-routed to a content category.

**Rationale**: The metric mirrors the approved `text_to_query_metric`
discipline (binary, no partial credit) but targets the routing decision
rather than the query result. Routing accuracy = fraction of held-out
routing cases classified into the correct category. False-routing rate =
fraction of labeled structured cases routed to content (must be bounded).

**Alternatives considered**: (a) A soft/graded metric — rejected: binary is
the house discipline and is unambiguous for a categorical decision. (b)
End-to-end answer correctness as the tuning metric — rejected: conflates
routing with retrieval/answer quality; the routing decision is the unit
being tuned.

## R5 — Routing case categories and counts

**Decision**: New labeled routing cases reuse the existing evaluation case
schema (`evaluation/schemas.py` EvalCase: id, category, question, expected).
New routing categories: `route_content_about`, `route_content_similar`,
`route_structured`, `route_unsupported` (plus security content cases under
the existing `security_*` prefix). Counts: +8 development cases in
`evaluation/dev_cases.json` and +10 held-out cases in
`evaluation/cases.json`, physically separate, stable unique IDs, including
deep paraphrases and security content cases. The `expected` field carries
the labeled routing category (and reference ticket_id for content_similar).

**Rationale**: Human decision 3. Reusing the existing schema and files keeps
one isolation story (dev vs held-out) and lets the existing leakage guard
(`assert_no_held_out_leakage`) protect the new cases unchanged. The feature
010 retrieval cases (`retrieval_about`/`retrieval_similar`) already exist in
these files; the routing cases are additive and distinct (they label the
routing decision, not the retrieval result).

**Alternatives considered**: (a) A separate routing-cases file — rejected:
breaks the single dev/held-out isolation structure and would need a parallel
leakage guard. (b) Reusing the 010 retrieval cases as routing labels —
rejected: they label retrieval relevance, not the routing category; routing
needs its own labels (including structured/unsupported negatives).

## R6 — Tuning method: BootstrapFewShot with stop-and-report

**Decision**: Tune the extended classifier with the approved bounded
BootstrapFewShot (`optimizer_config()` from feature 004: metric_threshold
1.0, max_bootstrapped_demos 4, max_labeled_demos 4, max_rounds 1, max_errors
3), using the routing metric (R4) on the routing dev cases only. The tuned
program is saved to `app/ai/optimized_program.json` (extending the existing
artifact with routing demos) with provenance in
`artifacts/optimization-run.json`. If the held-out routing accuracy does NOT
reach the calibrated threshold, the run STOPS and reports to the human; it
does not ship a degraded router and does not use GEPA/MIPROv2/SIMBA.

**Rationale**: Human decision 2. BootstrapFewShot is the only
AGENTS.md-approved optimizer. A 4-5-way classification is a simple task for
a model that already understands paraphrase, so few-shot bootstrapping is
expected to suffice; if it does not, the honest outcome is stop-and-report,
not a forbidden optimizer.

**Alternatives considered**: (a) Hand-written prompt only (no tuning) —
rejected: the whole point is to tune the content boundary on dev cases; an
untuned prompt is what the regex already failed at. (b) GEPA — rejected:
forbidden by AGENTS.md unless the human amends it.

## R7 — False-routing guard and threshold calibration

**Decision**: Two held-out gates protect the structured path: (1) the
existing structured execution-accuracy gate must not regress (the structured
cases in `evaluation/cases.json` are re-evaluated with the new classifier);
(2) a false-routing rate (structured questions mis-routed to a content
category) bounded by a threshold. Both thresholds are set in the plan after
a noise calibration run (the same artifact measured 2-3 times at temperature
0 to observe the noise band), per the measurement-noise lesson.

**Rationale**: Human decision 4. The structured path is proven and must not
degrade. Thresholds set without a noise measurement risk being tighter than
the run-to-run variance (a known trap on small eval sets).

**Alternatives considered**: (a) A fixed arbitrary threshold — rejected:
risks being inside the noise band. (b) No false-routing guard — rejected: a
tuned classifier could silently start mis-routing structured questions.

## R8 — Integration into the query path (routes.py)

**Decision**: `app/api/routes.py` removes the regex router. The flow becomes:
classify (tuned `ClassifyQuestion`) -> dispatch on category:
`content_about` -> governed retrieval (embed query text, retrieve, ground);
`content_similar` -> deterministic ticket_id extraction -> governed
retrieval (similar mode); `supported` -> structured planner (unchanged);
`ambiguous`/`unsupported` -> stable clarification/refusal (unchanged).
Retrieval grounding, the sanitized trace, the request safety timeout, and
the result-size cap are reused unchanged from feature 010.

**Rationale**: The routing decision moves from regex to the classifier, but
every downstream governed path is untouched (FR-011). The content dispatch
reuses the existing `_run_retrieval` machinery; only the trigger changes.

**Alternatives considered**: (a) Keep the regex as a fast-path before the
classifier — rejected: human decision 1 removes it; a fast-path regex would
re-introduce the fragile word-shape routing.

## R9 — Test strategy (stubbed LM for unit, live for gated validation)

**Decision**: Unit tests stub the LM (`dspy.utils.DummyLM`) and cover:
category parsing for all five categories, conservative fallback on
unparseable/unknown output, content categories routing to the retrieval
dispatch, and the deterministic ticket_id extractor (valid ids, no false
positives on priorities/counts, missing id). Integration tests cover
end-to-end routing on the live stack: deep paraphrase content questions
reach retrieval and return relevant tickets; structured questions route to
the structured path unchanged; unsupported questions are refused; security
content cases return nothing prohibited. The tuning run and the held-out
routing evaluation are quickstart/validation procedures whose outputs are
committed and then verified by deterministic tests — not pytest live tests.

**Rationale**: AGENTS.md forbids simulated results for shipped artifacts but
stubbed-LM unit tests are standard for logic; keeping the tuning run and the
live routing eval out of pytest keeps the 571-test suite fast and hermetic.

**Alternatives considered**: Live-LM pytest routing tests as default —
rejected: endpoint availability would gate unrelated CI; live runs are part
of quickstart validation instead.
