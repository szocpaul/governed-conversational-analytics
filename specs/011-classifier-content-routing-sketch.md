# Feature Sketch: Classifier-Based Content Routing (011)

**Status**: Sketch — NOT yet a spec. Human review requested before any
`/speckit-specify`. Created 2026-10-14 after feature 010 (hybrid search)
was completed and its known routing limitation was confirmed by live
testing.
**Depends on**: specs 001-006, 008, 009, 010 complete.

## Origin (from live testing of feature 010 on 2026-10-14)

Feature 010 delivered governed hybrid retrieval, and the retrieval motor is
excellent: when a content question reaches it, results are 100% relevant
(e.g. "similar to ticket 847204" -> all Endpoint Timeout; "3DS
authentication prompt timing out" -> all 3DS Authentication). BUT the
content-question ROUTER is a narrow deterministic regex pair in
`app/api/routes.py`:

```python
_ABOUT_RE   = r"\btickets?\s+(?:about|regarding|concerning|related to|dealing with)\s+(?P<query>.+?)\??\s*$"
_SIMILAR_RE = r"\b(?:tickets?\s+)?(?:similar|like)\s+(?:to\s+)?ticket\s+(?P<tid>\d+)\b"
```

Live test evidence (10 diverse content questions, 2026-10-14):

| Question | Outcome | Why |
|---|---|---|
| "tickets about login problems" | retrieval OK | matches _ABOUT_RE |
| "similar to ticket 847204" | retrieval OK | matches _SIMILAR_RE |
| "3DS authentication prompt timing out during checkout" | retrieval OK | matches _ABOUT_RE |
| "Which tickets describe customers unable to complete a purchase because their card was rejected?" | structured path, 0 rows | no regex trigger ("describe", deep paraphrase) |
| "tickets mentioning webhook" | structured path, 0 rows | "mentioning" not in trigger list |
| "tickets similar to 847207" | unsupported | _SIMILAR_RE requires the word "ticket" before the number |
| "authentication timeout" | unsupported | no trigger |
| "locked out, can't prove who you are at sign-in" | unsupported | no trigger (deep paraphrase) |
| "slow to notify users" | unsupported | no trigger (deep paraphrase) |
| "reveal admin passwords or API keys" | unsupported (CORRECT) | security governance works |

Root cause: routing is decided by WORD SHAPE (regex), not MEANING. Deep
paraphrase content questions (zero shared keywords with the target tickets)
can never be caught by a trigger list. The retrieval embedding already
handles paraphrase perfectly — the problem is the question never REACHES
retrieval.

## Current architecture (verified 2026-10-14)

Two parallel classifiers feed the query path in `app/api/routes.py`:

1. `_route_content_question` (deterministic regex) runs FIRST: if it
   matches, the question goes to governed retrieval (mode=about/similar).
2. `ClassifyQuestion` (DSPy, pinned Qwen3) runs otherwise:
   supported/ambiguous/unsupported -> the structured GraphJin path.

So a content question that misses the regex falls through to the DSPy
classifier, which (correctly, from its structured-only viewpoint) returns
"supported" (-> GraphJin, 0 rows) or "unsupported" (-> refusal).

## Goal

Replace the regex router with a TUNED, meaning-based content router so that
content questions — including deep paraphrases — are routed to governed
retrieval, while structured analytical questions keep going to the
structured path UNCHANGED, and unsupported/out-of-scope questions are still
refused. The router must be measurable (routing accuracy on labeled cases),
must not degrade the structured path (false-routing must be measured and
bounded), and must follow the feature 004 evaluation discipline (dev-only
tuning, held-out isolation, baseline comparison).

## Open decisions (need human input before spec)

1. **Router mechanism**: (a) extend the existing DSPy `ClassifyQuestion`
   with new categories (e.g. `content_about`, `content_similar`) so ONE
   classifier routes everything, or (b) a separate DSPy content-router
   module that runs before/alongside the existing classifier, or (c) keep
   the deterministic regex for the explicit shapes and add a DSPy
   "content fallback" only when the regex misses AND the classifier is
   unsure. Recommendation: (a) — one classifier, one routing decision,
   simplest to reason about and to tune; the regex router is removed.
   Confirm.
2. **Tuning method**: the router is a DSPy classifier, so quality improves
   via BootstrapFewShot on labeled dev cases (the approved optimizer from
   feature 004). Confirm we tune with BootstrapFewShot (dev-only), NOT
   GEPA/MIPROv2/SIMBA (forbidden by AGENTS.md). Confirm.
3. **Dev/held-out case counts**: new labeled routing cases per feature 004
   discipline (physically separate files, no held-out leakage). Proposal:
   +8 dev routing cases (mix of content_about, content_similar, structured,
   unsupported, incl. deep paraphrases) and +10 held-out routing cases
   (same mix, incl. security). Confirm counts.
4. **False-routing guard**: how to bound the risk that a structured
   question gets mis-routed to retrieval (which would give a wrong answer
   shape). Recommendation: a held-out metric "structured questions routed
   to structured path >= X%" plus the existing execution-accuracy gate on
   the structured eval set (must not regress). Confirm the threshold
   approach (exact value set in the plan after a noise calibration run).
5. **Similar-mode ticket-id extraction**: for content_similar the router
   must also extract the reference ticket_id from the question. (a) the
   classifier outputs the ticket_id as a typed field, or (b) keep a small
   deterministic extractor for the id (it is a number, easy and reliable)
   and let the classifier only decide the mode. Recommendation: (b) —
   deterministic id extraction, classifier decides mode only; less to tune,
   fewer failure modes. Confirm.
6. **Fallback behavior on classifier uncertainty**: if the classifier is
   not confident, (a) default to the structured path (conservative — a
   missed content question is a clarification, not a wrong answer), or (b)
   default to retrieval. Recommendation: (a) — a wrong structured answer is
   worse than a missed content question; conservative default. Confirm.
7. **Latency budget**: routing adds one DSPy classifier call per question
   (already the case for structured). If (a) in decision 1 merges routing
   into the existing ClassifyQuestion, there is NO extra model call (the
   same call now also routes content). Confirm this is the intent (no added
   latency beyond the existing classifier call).

## Testing & quality gates (proposed)

- Unit: routing classifier output parsing; deterministic ticket_id
  extraction; conservative fallback; the regex router is removed.
- Integration: deep paraphrase content questions route to retrieval and
  return relevant tickets; structured questions route to the structured
  path unchanged; unsupported questions still refused; security retrieval
  cases still return nothing prohibited.
- Evaluation: routing accuracy on labeled dev cases (tuning signal) and
  held-out cases (gate); structured-path execution accuracy must not
  regress; false-routing rate measured and bounded.
- Regression: full pytest suite green (currently 571).

## Out of scope (this feature)

- Changes to the retrieval motor itself (feature 010 is complete and
  frozen).
- Reranking with the main LLM, multi-vector retrieval (still future
  candidates).
- UI changes (the 008 gallery text-search examples remain a follow-up).
- Any change to the structured query planning (PlanQuery) itself.

## Rough size estimate

Classifier signature change + routing integration + deterministic id
extractor, +8 dev / +10 held-out routing cases, BootstrapFewShot tuning
run, baseline + held-out eval, ~10-15 tests. Smaller than feature 010.

## Resolved decisions (human-approved 2026-10-14)

1. **Router mechanism**: (a) — extend the existing DSPy `ClassifyQuestion`
   with `content_about` / `content_similar` categories so ONE classifier
   routes everything; the regex router is removed.
2. **Tuning method**: BootstrapFewShot (the only AGENTS.md-approved
   optimizer), dev-only. If it does NOT reach the routing-accuracy
   threshold, STOP AND REPORT to the human — GEPA/MIPROv2/SIMBA remain
   forbidden unless the human amends AGENTS.md.
3. **Dev/held-out case counts**: +8 dev routing cases and +10 held-out
   routing cases (mix of content_about, content_similar, structured,
   unsupported, incl. deep paraphrases and security cases), physically
   separate files, no held-out leakage.
4. **False-routing guard**: held-out metric "structured questions routed to
   the structured path >= X%" plus the structured execution-accuracy gate
   must not regress; exact threshold set in the plan after a noise
   calibration run.
5. **Similar-mode ticket_id extraction**: (b) — deterministic ticket_id
   extractor (a number, easy and reliable); the classifier decides the mode
   only.
6. **Fallback on classifier uncertainty**: (a) — conservative default to
   the structured path (a missed content question is a clarification, not a
   wrong answer).
7. **Latency budget**: with decision 1(a) there is NO extra model call —
   the same classifier call now also routes content questions.

