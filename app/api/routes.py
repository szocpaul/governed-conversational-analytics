"""FastAPI routes orchestrating the conversational query flow (T007).

Flow: question -> DSPy classify+plan -> deterministic validate -> governed
GraphJin execute -> normalize evidence -> DSPy grounded answer -> sanitized
trace + latency. Stable categories for clarification, unsupported, and
dependency failure. No model/provider fallback; no arbitrary SQL.
"""
from __future__ import annotations

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
from app.security.errors import PipelineError
from app.security.validator import validate_request

router = APIRouter()


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
    trace = Trace()
    trace.add("received", "question accepted")

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
    return _response("answered", answered.answer, trace, evidence)
