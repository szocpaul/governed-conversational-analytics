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
from app.api.schemas import (
    Evidence,
    QuestionRequest,
    QueryResponse,
    TraceEvent,
)
from app.data.graphjin_client import GraphJinClient, GraphJinError
from app.data.result_normalizer import normalize_result
from app.observability.trace import Trace
from app.security.classifier import classify_question
from app.security.errors import PipelineError
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
    return QueryProgram()


def _make_answer_program() -> AnswerProgram:
    return AnswerProgram()


def _make_graphjin_client() -> GraphJinClient:
    url = os.environ.get(
        "GRAPHJIN_GRAPHQL_URL", "http://127.0.0.1:8081/api/v1/graphql")
    return GraphJinClient(url, timeout=30.0)


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

    # 2. Ambiguity / unsupported -> stable categories, no query executed.
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
