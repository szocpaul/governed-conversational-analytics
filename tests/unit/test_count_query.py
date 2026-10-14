"""T003: Unit tests for the governed hybrid count query (feature 012).

Contracts/count-query.md + research R1/R2: the count query is a FIXED,
parameterized COUNT statement over the allowlisted text fields (via the fts
and embedding columns), connecting as the read-only role. A ticket matches
when it matches lexically (fts @@ plainto_tsquery) OR semantically
(vector distance <= a calibrated threshold). The count is a TRUE total (NO
LIMIT); only the example ticket_ids selection is capped (<= 5). The query
text, query vector, and threshold are BOUND parameters (never interpolated).
An absent/uncalibrated threshold raises a loud error (never a hardcoded
default). No live database or model is used here (construction/validation
only).
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
# Count SQL construction: fixed, parameterized, hybrid match, NO LIMIT.
# ---------------------------------------------------------------------------

def test_count_query_builder_exists(ret):
    assert hasattr(ret, "build_count_query"), "build_count_query must exist"


def test_count_sql_is_hybrid_lexical_or_semantic(ret):
    sql, params = ret.build_count_query("login", [0.01] * 768, 0.35)
    # Lexical side: full-text match over the generated fts column.
    assert "plainto_tsquery" in sql
    assert "fts @@" in sql
    # Semantic side: pgvector cosine distance within the threshold.
    assert "<=>" in sql
    # Hybrid OR semantics (a ticket counted once whether lexical/semantic/both).
    assert " OR " in sql.upper()


def test_count_sql_is_a_true_count_with_no_limit(ret):
    """The count MUST be a true total: NO LIMIT clause on the count."""
    sql, _ = ret.build_count_query("login", [0.01] * 768, 0.35)
    assert "count(" in sql.lower()
    assert "LIMIT" not in sql.upper(), "the count must not be capped"


def test_count_sql_targets_only_allowlisted_columns(ret):
    """Only the three generated text fields are searched (via fts/embedding)."""
    sql, _ = ret.build_count_query("login", [0.01] * 768, 0.35)
    assert "fts" in sql            # generated tsvector over the 3 text fields
    assert "embedding" in sql      # generated vector over the 3 text fields
    # No structured/allowlist-violating column is interpolated.
    for bad in ("category", "merchant_name", "priority", "password"):
        assert bad not in sql


def test_count_query_text_is_bound_parameter_not_interpolated(ret):
    """The query text MUST be a bound parameter; never interpolated into SQL."""
    malicious = "x'; DROP TABLE itsm.tickets; --"
    sql, params = ret.build_count_query(malicious, [0.01] * 768, 0.35)
    assert malicious not in sql          # NOT in the SQL string
    assert malicious in params           # carried as a bound parameter
    assert "%s" in sql or "$1" in sql    # a placeholder is used


def test_count_query_vector_and_threshold_are_bound_parameters(ret):
    vec = [0.01] * 768
    sql, params = ret.build_count_query("login", vec, 0.35)
    # The threshold is a bound parameter, not interpolated.
    assert "0.35" not in sql
    assert 0.35 in params
    # The vector is bound (rendered as a vector literal for psycopg binding).
    assert any("0.01" in str(p) for p in params)


def test_count_threshold_must_be_a_real_number(ret):
    with pytest.raises(Exception):
        ret.build_count_query("login", [0.01] * 768, None)
    with pytest.raises(Exception):
        ret.build_count_query("login", [0.01] * 768, "0.35")


# ---------------------------------------------------------------------------
# Example-ids selection: same match condition, capped at <= 5.
# ---------------------------------------------------------------------------

def test_count_examples_builder_exists_and_capped(ret):
    assert hasattr(ret, "build_count_examples_query")
    sql, params = ret.build_count_examples_query("login", [0.01] * 768, 0.35)
    # The example selection IS limited (<= 5) over the SAME match condition.
    assert "LIMIT" in sql.upper()
    assert "plainto_tsquery" in sql and "<=>" in sql
    # Cap is the governed example cap (<= 5), carried as a bound parameter.
    assert ret.MAX_COUNT_EXAMPLES <= 5
    assert ret.MAX_COUNT_EXAMPLES in params


# ---------------------------------------------------------------------------
# Threshold loading: absent/uncalibrated -> loud error (never hardcoded).
# ---------------------------------------------------------------------------

def test_load_threshold_missing_file_raises(ret, tmp_path, monkeypatch):
    monkeypatch.setattr(ret, "COUNT_THRESHOLD_PATH", str(tmp_path / "none.json"))
    with pytest.raises(Exception):
        ret.load_count_threshold()


def test_load_threshold_uncalibrated_raises(ret, tmp_path, monkeypatch):
    bad = tmp_path / "t.json"
    bad.write_text('{"version": "1"}')  # no "threshold" key
    monkeypatch.setattr(ret, "COUNT_THRESHOLD_PATH", str(bad))
    with pytest.raises(Exception):
        ret.load_count_threshold()


def test_load_threshold_valid(ret, tmp_path, monkeypatch):
    good = tmp_path / "t.json"
    good.write_text('{"threshold": 0.35, "version": "1"}')
    monkeypatch.setattr(ret, "COUNT_THRESHOLD_PATH", str(good))
    assert ret.load_count_threshold() == 0.35
