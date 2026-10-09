"""Unit tests for deterministic request validation and stable errors (T004).

Covers ambiguous, unsupported, malformed-output, and endpoint-failure
categories. The validator is deterministic and performs no LLM calls.
"""
from __future__ import annotations

import pytest

from app.api.schemas import StructuredQueryRequest
from app.security.errors import (
    AmbiguousQuestionError,
    DependencyError,
    MalformedPlanError,
    UnsupportedQuestionError,
    ValidationError as GovernedValidationError,
)
from app.security.validator import validate_request


def _valid_request() -> StructuredQueryRequest:
    return StructuredQueryRequest(
        entity="tickets", operation="list", fields=["ticket_id"], limit=5)


# ---------------------------------------------------------------------------
# Stable error categories exist and carry a stable code
# ---------------------------------------------------------------------------

def test_error_categories_have_stable_codes():
    assert AmbiguousQuestionError("x").code == "ambiguous"
    assert UnsupportedQuestionError("x").code == "unsupported"
    assert MalformedPlanError("x").code == "malformed_plan"
    assert DependencyError("x").code == "dependency_error"
    assert GovernedValidationError("x").code == "validation_error"


def test_errors_do_not_leak_endpoint():
    err = DependencyError("connection to "
                          "http://desktop-c5ikame-1.tailee6bc1.ts.net:8033 "
                          "refused")
    # The sanitized form must not expose the private endpoint.
    assert "tailee6bc1" not in err.sanitized
    assert "8033" not in err.sanitized


# ---------------------------------------------------------------------------
# Deterministic validation
# ---------------------------------------------------------------------------

def test_validate_accepts_valid_request():
    req = _valid_request()
    validated = validate_request(req)
    assert validated is req


def test_validate_rejects_disallowed_field():
    req = StructuredQueryRequest.model_construct(
        entity="tickets", operation="list", fields=["ticket_id", "secret_col"],
        filters=[], aggregate=None, relationships=[], order_by=None,
        order_dir="asc", limit=5)
    with pytest.raises(GovernedValidationError):
        validate_request(req)


def test_validate_rejects_disallowed_entity():
    req = StructuredQueryRequest.model_construct(
        entity="pg_shadow", operation="list", fields=["ticket_id"],
        filters=[], aggregate=None, relationships=[], order_by=None,
        order_dir="asc", limit=5)
    with pytest.raises(GovernedValidationError):
        validate_request(req)


def test_validate_rejects_oversized_limit():
    req = StructuredQueryRequest.model_construct(
        entity="tickets", operation="list", fields=["ticket_id"],
        filters=[], aggregate=None, relationships=[], order_by=None,
        order_dir="asc", limit=5000)
    with pytest.raises(GovernedValidationError):
        validate_request(req)


def test_validate_rejects_bad_filter_op():
    req = StructuredQueryRequest.model_construct(
        entity="tickets", operation="list", fields=["ticket_id"],
        filters=[], aggregate=None, relationships=[], order_by=None,
        order_dir="asc", limit=5)
    # Force an invalid filter through construct.
    from app.api.schemas import Filter
    bad = Filter.model_construct(field="priority", op="drop", value="x")
    req.filters.append(bad)
    with pytest.raises(GovernedValidationError):
        validate_request(req)
