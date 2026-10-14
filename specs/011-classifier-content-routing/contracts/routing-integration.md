# Contract: Routing Integration (query path)

**Files**: `app/api/routes.py` (dispatch), `app/ai/routing.py` (deterministic
helpers), `app/ai/query_program.py` (category-driven planning).

## Flow (replaces the regex router)

```text
question
  -> classify (tuned ClassifyQuestion)        [1 model call, unchanged]
  -> dispatch on category:
       content_about   -> governed retrieval (embed query text, retrieve, ground)
       content_similar -> deterministic ticket_id extraction
                          -> governed retrieval (similar mode)
       supported       -> structured planner (PlanQuery, unchanged)
       ambiguous       -> stable clarification (unchanged)
       unsupported     -> stable refusal (unchanged)
```

## Deterministic ticket_id extractor (app/ai/routing.py)

- Pure function, no LLM, no I/O.
- Input: the question string. Output: the reference ticket_id (int) or None.
- Matches a 5-6 digit number in the pinned ticket-id shape; anchored so it
  does NOT match priorities (P1-P4), counts, or other numbers.
- Never guesses: no plausible id -> None -> the answer path returns a stable
  clarification (never fabricates).

## Conservative fallback

- Unparseable/unknown classifier output -> route to the structured path.
- A missed content question yields a clarification from the structured path
  ("no matching data"), never a wrong answer.

## Removed

- `_ABOUT_RE`, `_SIMILAR_RE`, `_route_content_question` (the regex router).

## Reused unchanged (feature 010)

- `_run_retrieval` (governed retrieval, grounding, sanitized trace).
- The request safety timeout and the result-size cap (independent controls).
- The read-only retrieval channel and the GraphJin structured boundary.

## Guarantees (verified by tests)

- Deep paraphrase content questions reach retrieval and return relevant
  tickets.
- Structured questions route to the structured path unchanged.
- Unsupported questions are refused with a stable category.
- Security content questions return nothing prohibited; the trace contains
  no credentials, endpoint details, or prompts.
