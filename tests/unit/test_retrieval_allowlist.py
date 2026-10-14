"""T007: Unit tests for the governed retrieval request validator.

Research R1/R7/R8 + contracts/retrieval-api.md: the validator accepts only
the fixed allowlist of searchable fields (the three generated text fields),
rejects any non-allowlisted field, clamps the result limit to the governed
maximum, and builds the lexical tsvector query with plainto_tsquery and the
query text as a BOUND parameter (no arbitrary SQL string interpolation).
"""
from __future__ import annotations

import importlib.util
import os

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MODULE_PATH = os.path.join(REPO_ROOT, "app", "ai", "retrieval.py")

ALLOWLIST = {"short_description", "description", "resolution_notes"}


def _load_module():
    spec = importlib.util.spec_from_file_location("app.ai.retrieval", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ret():
    return _load_module()


# ---------------------------------------------------------------------------
# Allowlist of searchable fields
# ---------------------------------------------------------------------------

def test_allowlist_is_exactly_the_three_text_fields(ret):
    assert set(ret.SEARCHABLE_FIELDS) == ALLOWLIST


def test_validate_accepts_allowlisted_fields(ret):
    req = ret.validate_retrieval_request(
        {"mode": "about", "query_text": "login problems", "limit": 10})
    assert req.mode == "about"
    assert req.query_text == "login problems"


def test_non_allowlisted_field_rejected(ret):
    with pytest.raises(Exception):
        ret.validate_retrieval_request(
            {"mode": "about", "query_text": "x", "limit": 10,
             "fields": ["category"]})  # category is NOT searchable


def test_arbitrary_field_rejected(ret):
    with pytest.raises(Exception):
        ret.validate_retrieval_request(
            {"mode": "about", "query_text": "x", "limit": 10,
             "fields": ["password"]})


def test_invalid_mode_rejected(ret):
    with pytest.raises(Exception):
        ret.validate_retrieval_request({"mode": "delete", "query_text": "x"})


def test_about_mode_requires_query_text(ret):
    with pytest.raises(Exception):
        ret.validate_retrieval_request({"mode": "about", "limit": 10})


def test_similar_mode_requires_ticket_id(ret):
    with pytest.raises(Exception):
        ret.validate_retrieval_request({"mode": "similar", "limit": 10})


def test_similar_mode_valid(ret):
    req = ret.validate_retrieval_request(
        {"mode": "similar", "ticket_id": 847203, "limit": 10})
    assert req.mode == "similar" and req.ticket_id == 847203


# ---------------------------------------------------------------------------
# Result limit clamped to the governed maximum
# ---------------------------------------------------------------------------

def test_limit_clamped_to_governed_max(ret):
    req = ret.validate_retrieval_request(
        {"mode": "about", "query_text": "x", "limit": 100000})
    assert req.limit == ret.MAX_RETRIEVAL_LIMIT
    assert req.limit <= ret.MAX_RETRIEVAL_LIMIT


def test_limit_default(ret):
    req = ret.validate_retrieval_request({"mode": "about", "query_text": "x"})
    assert req.limit == ret.DEFAULT_RETRIEVAL_LIMIT


def test_governed_max_is_bounded(ret):
    assert ret.MAX_RETRIEVAL_LIMIT <= 100  # never exceeds the governed cap


# ---------------------------------------------------------------------------
# Lexical tsvector query construction (plainto_tsquery, bound parameter)
# ---------------------------------------------------------------------------

def test_lexical_sql_uses_plainto_tsquery(ret):
    sql, params = ret.build_lexical_query("login problems", limit=10)
    assert "plainto_tsquery" in sql
    assert "to_tsquery" not in sql.replace("plainto_tsquery", "")
    assert "ts_rank" in sql


def test_query_text_is_bound_parameter_not_interpolated(ret):
    """The query text must be a bound parameter; never interpolated into SQL."""
    malicious = "x'; DROP TABLE itsm.tickets; --"
    sql, params = ret.build_lexical_query(malicious, limit=10)
    assert malicious not in sql  # the text is NOT in the SQL string
    assert malicious in params   # it is carried as a bound parameter
    assert "%s" in sql or "$1" in sql  # a placeholder is used


def test_lexical_sql_targets_only_allowlisted_fts_column(ret):
    sql, _ = ret.build_lexical_query("login", limit=10)
    assert "fts" in sql  # the generated tsvector column over the 3 text fields
    # No arbitrary field names are interpolated.
    assert "category" not in sql and "merchant_name" not in sql


def test_semantic_sql_uses_cosine_distance_bound_vector(ret):
    sql, params = ret.build_semantic_query([0.01] * 768, limit=10)
    assert "<=>" in sql  # cosine distance operator
    assert "%s" in sql or "$1" in sql
    assert params  # the query vector is a bound parameter
