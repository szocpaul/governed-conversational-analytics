"""FastAPI routes orchestrating the conversational query flow (T007).

Flow: question -> DSPy classify+plan -> deterministic validate -> governed
GraphJin execute -> normalize evidence -> DSPy grounded answer -> sanitized
trace + latency. Stable categories for clarification, unsupported, and
dependency failure. No model/provider fallback; no arbitrary SQL.

Security (spec 003): an overall REQUEST SAFETY TIMEOUT bounds the whole
request independently of the database-query timeout and the result-size
cap (FR-004). If any stage exceeds it, the request returns a stable
dependency_error instead of hanging.
"""
from __future__ import annotations

import concurrent.futures
import os

from fastapi import APIRouter

from app.ai.answer_program import AnswerProgram
from app.ai.query_program import QueryProgram
from app.ai.routing import extract_count_topic, extract_ticket_id
from app.ai.retrieval import (
    CountThresholdError,
    RetrievalError,
    RetrievalRequest,
    count_over_content,
    fetch_ticket_summaries,
    retrieve,
    validate_retrieval_request,
)
from app.api.schemas import (
    Evidence,
    QuestionRequest,
    QueryResponse,
    RetrievalResult,
    TraceEvent,
)
from app.data.graphjin_client import GraphJinClient, GraphJinError
from app.data.result_normalizer import apply_having, normalize_result
from app.observability.trace import Trace
from app.security.classifier import classify_question
from app.security.errors import PipelineError, UnsupportedQuestionError
from app.security.redaction import redact
from app.security.validator import validate_request

router = APIRouter()

# Overall request safety timeout (seconds), independent of the
# database-query timeout and the result-size cap (FR-004).
REQUEST_SAFETY_TIMEOUT_S = float(
    os.environ.get("REQUEST_SAFETY_TIMEOUT_S", "120"))

# Bounded executor so a timed-out request does not leak threads.
_SAFETY_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _make_query_program() -> QueryProgram:
    """Return the query program, loading the optimized program when present.

    The optimized program (app/ai/optimized_program.json) is produced by the
    approved BootstrapFewShot optimization on development cases only (spec 004,
    T006). When absent, the base program is used. Loading is best-effort: a
    malformed artifact falls back to the base program rather than failing.
    """
    program = QueryProgram()
    opt_path = os.path.join(
        os.path.dirname(__file__), "..", "ai", "optimized_program.json")
    if os.path.exists(opt_path):
        try:
            program.load(opt_path)
        except Exception:  # noqa: BLE001 - fall back to base program
            pass
    return program


def _make_answer_program() -> AnswerProgram:
    return AnswerProgram()


def _make_graphjin_client() -> GraphJinClient:
    url = os.environ.get(
        "GRAPHJIN_GRAPHQL_URL", "http://127.0.0.1:8081/api/v1/graphql")
    return GraphJinClient(url, timeout=30.0)


# ---------------------------------------------------------------------------
# Feature 011: content routing is decided by the tuned ClassifyQuestion (ONE
# classifier routes every question); the feature 010 regex router is removed.
# The deterministic ticket_id extractor and category dispatch live in
# app/ai/routing.py. Governed retrieval itself (feature 010) is unchanged.
# ---------------------------------------------------------------------------


def _embed_query_text(text: str) -> list[float]:
    """Embed the retrieval query text with the pinned embedding model.

    Uses the same pinned EmbeddingGemma-2 endpoint as the offline generator
    (EMBED_* config); no fallback. Raises RetrievalError on failure.
    """
    from app.ai.embeddings import EmbeddingConfig, EmbeddingProgram
    try:
        program = EmbeddingProgram(config=EmbeddingConfig.from_env())
        return program._embed_once(text)
    except Exception as exc:  # noqa: BLE001
        raise RetrievalError(f"query embedding failed: {exc}") from exc


def _run_retrieval(req: RetrievalRequest, trace: Trace,
                   question: str) -> QueryResponse:
    """Execute governed retrieval and ground the answer on the result."""
    try:
        result = retrieve(req, embed_query=_embed_query_text)
    except RetrievalError as exc:
        trace.add("error", f"retrieval dependency failure: {exc}")
        return _response(
            "dependency_error",
            "The retrieval dependency is unavailable; no fallback was "
            "attempted.",
            trace,
        )
    retrieval = RetrievalResult(**result)
    trace.add("retrieval",
              f"mode={retrieval.trace[0]['mode']} "
              f"ticket_ids={retrieval.ticket_ids}")

    # Ground the answer on the retrieval result; never fabricate (FR-014).
    if not retrieval.ticket_ids:
        trace.add("clarification", "retrieval returned no matching tickets")
        return _response(
            "clarification",
            "I found no tickets matching that content query. Please "
            "rephrase or broaden the search.",
            trace,
        )

    summaries = fetch_ticket_summaries(retrieval.ticket_ids)
    score_by_id = dict(zip(retrieval.ticket_ids, retrieval.scores))
    evidence = Evidence(
        rows=[{**s, "relevance_score": round(score_by_id[s["ticket_id"]], 6)}
              for s in summaries],
        row_count=len(summaries),
    )
    try:
        ap = _make_answer_program()
        answered = ap(question=question, evidence=evidence)
    except Exception:  # noqa: BLE001
        trace.add("error", "answer dependency failure")
        return _response(
            "dependency_error",
            "The language model dependency is unavailable; no fallback was "
            "attempted.",
            trace,
        )
    if not answered.grounded:
        trace.add("refused", "answer not grounded in retrieval result")
        return _response(
            "clarification",
            "I could not produce an answer fully supported by the retrieved "
            "tickets. Please rephrase or narrow the question.",
            trace,
            evidence,
        )
    trace.add("answered", "grounded answer returned from retrieval")
    return _response("answered", redact(answered.answer), trace, evidence)


def _run_count(trace: Trace, question: str) -> QueryResponse:
    """Execute the governed hybrid count and ground the answer on the total.

    The count is a TRUE total (never capped by the retrieval limit), grounded
    with up to 5 example ticket_ids. An absent/uncalibrated semantic threshold
    yields a stable dependency error (never a hardcoded default, FR-005); a
    retrieval/embedding failure likewise. Never fabricates a number.
    """
    # The governed hybrid count searches the content TOPIC (deterministically
    # extracted), not the whole count question: plainto_tsquery ANDs content
    # words, so the full question would return a misleading 0 (the word
    # "ticket" rarely appears in ticket text). If no topic can be extracted,
    # fall back to the full question text.
    topic = extract_count_topic(question) or question
    trace.add("count_topic", f"topic={topic!r}")
    try:
        result = count_over_content(topic, embed_query=_embed_query_text)
    except CountThresholdError as exc:
        trace.add("error", f"count threshold unavailable: {exc}")
        return _response(
            "dependency_error",
            "The count over content is not calibrated; the semantic-match "
            "threshold is unavailable. No count was produced.",
            trace,
        )
    except RetrievalError as exc:
        trace.add("error", f"count dependency failure: {exc}")
        return _response(
            "dependency_error",
            "The retrieval dependency is unavailable; no fallback was "
            "attempted.",
            trace,
        )

    count = result["count"]
    example_ids = result["example_ticket_ids"]
    trace.add("count",
              f"count={count} example_ticket_ids={example_ids}")

    # Ground the answer on the count + up to 5 example ids (never fabricate).
    summaries = fetch_ticket_summaries(example_ids)
    evidence = Evidence(
        rows=summaries,
        aggregate={"count": count},
        row_count=len(summaries),
    )
    try:
        ap = _make_answer_program()
        answered = ap(question=question, evidence=evidence)
    except Exception:  # noqa: BLE001
        trace.add("error", "answer dependency failure")
        return _response(
            "dependency_error",
            "The language model dependency is unavailable; no fallback was "
            "attempted.",
            trace,
        )
    if not answered.grounded:
        trace.add("refused", "answer not grounded in count result")
        return _response(
            "clarification",
            "I could not produce an answer fully supported by the count "
            "result. Please rephrase or narrow the question.",
            trace,
            evidence,
        )
    trace.add("answered", "grounded answer returned from count")
    return _response("answered", redact(answered.answer), trace, evidence)


def _response(status: str, answer: str, trace: Trace,
              evidence: Evidence | None = None) -> QueryResponse:
    return QueryResponse(
        status=status,  # type: ignore[arg-type]
        answer=answer,
        evidence=evidence,
        trace=trace.events,
        latency_ms=trace.latency_ms(),
    )


@router.post("/query", response_model=QueryResponse)
def query(req: QuestionRequest) -> QueryResponse:
    """Entry point with an independent overall request safety timeout."""
    future = _SAFETY_EXECUTOR.submit(_query_inner, req)
    try:
        return future.result(timeout=REQUEST_SAFETY_TIMEOUT_S)
    except concurrent.futures.TimeoutError:
        trace = Trace()
        trace.add("error", "overall request safety timeout exceeded")
        return _response(
            "dependency_error",
            "The request exceeded the overall safety timeout and was "
            "stopped.",
            trace,
        )


def _query_inner(req: QuestionRequest) -> QueryResponse:
    trace = Trace()
    trace.add("received", "question accepted")

    # 0. Injection telemetry (NEVER authorization; FR-001). The signal is
    # recorded in the trace only; deterministic controls below decide access.
    signal = classify_question(req.question)
    if signal.flagged:
        trace.add("injection_signal",
                  f"telemetry category={signal.category} "
                  f"patterns={len(signal.matched_patterns)}")

    # 1. Classify + plan (DSPy, pinned local model; no fallback).
    try:
        qp = _make_query_program()
        planned = qp(question=req.question)
    except UnsupportedQuestionError as exc:
        # Planner emitted a query shape the governed pipeline does not
        # support (joins, subqueries, unions, ...). Stable category; no
        # query ran.
        trace.add("refused", f"unsupported request shape: {exc.sanitized}")
        return _response(
            "unsupported",
            "That question needs a query shape outside the supported ITSM "
            "analytics scope (for example, joins or subqueries).",
            trace,
        )
    except PipelineError as exc:
        trace.add("error", exc.sanitized)
        return _response(exc.code, exc.sanitized, trace)
    except Exception as exc:  # noqa: BLE001 - model/endpoint failure
        trace.add("error", f"model dependency failure: {exc}")
        return _response(
            "dependency_error",
            "The language model dependency is unavailable; no fallback was "
            "attempted.",
            trace,
        )

    classification = planned.classification
    trace.add("classified", classification)

    # 2a. Feature 011: content categories route to governed retrieval. The
    # classifier decided the mode; the reference ticket_id for similar-mode
    # is extracted DETERMINISTICALLY (never by the model). A missing id
    # yields a stable clarification (never fabricates). The retrieval path
    # itself (feature 010) is unchanged.
    if classification == "content_about":
        content_req = validate_retrieval_request(
            {"mode": "about", "query_text": req.question})
        trace.add("routed", "content_about -> governed retrieval")
        return _run_retrieval(content_req, trace, req.question)
    if classification == "content_similar":
        ticket_id = extract_ticket_id(req.question)
        if ticket_id is None:
            trace.add("clarification",
                      "content_similar but no reference ticket_id found")
            return _response(
                "clarification",
                "Which ticket should I find similar tickets to? Please "
                "include the reference ticket id.",
                trace,
            )
        content_req = validate_retrieval_request(
            {"mode": "similar", "ticket_id": ticket_id})
        trace.add("routed",
                  f"content_similar -> governed retrieval (ticket_id="
                  f"{ticket_id})")
        return _run_retrieval(content_req, trace, req.question)

    # 2a-count. Feature 012: a COUNT over a TOPIC routes to the governed
    # hybrid count path (NOT the structured planner, which would return a
    # misleading 0). The query text is embedded and counted via the governed
    # count query; the answer grounds on the true total + up to 5 examples.
    if classification == "content_count":
        trace.add("routed", "content_count -> governed hybrid count")
        return _run_count(trace, req.question)

    # 2b. Ambiguity / unsupported -> stable categories, no query executed.
    if classification == "ambiguous":
        trace.add("clarification", "material ambiguity; no query executed")
        return _response(
            "clarification",
            "Your question is ambiguous. Please clarify (for example, the "
            "time range, priority, or entity you mean).",
            trace,
        )
    if classification != "supported":
        trace.add("refused", "unsupported question; no query executed")
        return _response(
            "unsupported",
            "That question is outside the supported ITSM analytics scope.",
            trace,
        )

    # 3. Deterministic validation before any execution.
    try:
        request = validate_request(planned.request)
        trace.add("validated", "structured request passed governed policy")
    except PipelineError as exc:
        trace.add("error", exc.sanitized)
        return _response("unsupported",
                         "The planned request violated the governed policy.",
                         trace)

    # 4. Governed execution (GraphJin only; no arbitrary SQL).
    try:
        client = _make_graphjin_client()
        raw = client.execute(request)
        evidence = normalize_result(request, raw)
        trace.add("executed", f"{evidence.row_count} rows / aggregate "
                              f"{'set' if evidence.aggregate else 'unset'}")
    except GraphJinError as exc:
        trace.add("error", f"governed execution failed: {exc}")
        return _response(
            "dependency_error",
            "The governed data dependency is unavailable; no fallback was "
            "attempted.",
            trace,
        )

    # 4b. Post-aggregation group filter (spec 005; research.md Decision 4).
    # GraphJin v3 has no native HAVING: apply the validated having filter
    # deterministically over the executed groups. Pure function; no database
    # access.
    if request.having is not None:
        before_groups = evidence.row_count
        evidence = apply_having(evidence, request)
        trace.add(
            "having_applied",
            f"{request.having.function} {request.having.op} "
            f"{request.having.value}: {evidence.having_applied.groups_dropped}"
            f" of {before_groups} groups dropped client-side")
        if evidence.row_count == 0:
            trace.add("clarification",
                      "no groups match the post-aggregation filter")
            return _response(
                "clarification",
                "No groups match the requested aggregate threshold.",
                trace,
                evidence,
            )

    # 4c. Null ratio (empty base set): the ratio is undefined when no rows
    # match the base filters (GraphJin avg over an empty set returns null).
    # Stable clarification, never a fabricated number (spec 005 FR-004).
    if (request.aggregate is not None
            and request.aggregate.function == "ratio"
            and not request.group_by
            and evidence.aggregate is not None
            and evidence.aggregate.get(
                f"ratio_{request.aggregate.field}") is None):
        trace.add("clarification",
                  "ratio undefined: the base set is empty")
        return _response(
            "clarification",
            "The ratio is undefined because no tickets match the base "
            "filters (the denominator is zero).",
            trace,
            evidence,
        )

    # 5. Grounded answer. Ungrounded output is refused, never shown as fact.
    try:
        ap = _make_answer_program()
        answered = ap(question=req.question, evidence=evidence)
    except Exception as exc:  # noqa: BLE001
        trace.add("error", f"answer dependency failure: {exc}")
        return _response(
            "dependency_error",
            "The language model dependency is unavailable; no fallback was "
            "attempted.",
            trace,
        )

    if not answered.grounded:
        trace.add("refused", "answer not grounded in evidence")
        return _response(
            "clarification",
            "I could not produce an answer fully supported by the data. "
            "Please rephrase or narrow the question.",
            trace,
            evidence,
        )

    trace.add("answered", "grounded answer returned")
    # Defense in depth: redact the final answer text so no canary, secret,
    # or private endpoint detail can reach the user (FR-006).
    return _response("answered", redact(answered.answer), trace, evidence)
