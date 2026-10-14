"""T006: Unit tests for deterministic Reciprocal Rank Fusion (RRF, k=60).

Research R8: fused score = sum over sides of 1/(60 + rank), rank assigned by
score DESC (1-based); a missing side contributes 0; ties break on ticket_id
ASC; identical inputs produce identical fused rankings; empty inputs produce
an empty result. Pure function — no database, no model.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MODULE_PATH = os.path.join(REPO_ROOT, "app", "ai", "retrieval.py")

RRF_K = 60


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


def _ranked(pairs):
    """A ranked side: list of (ticket_id, score) already ordered best-first."""
    return list(pairs)


# ---------------------------------------------------------------------------
# Core RRF math (k=60)
# ---------------------------------------------------------------------------

def test_rrf_score_math_single_side(ret):
    """One side only: score = 1/(60+rank); missing other side contributes 0."""
    lexical = _ranked([(10, 0.9), (20, 0.5), (30, 0.1)])
    fused = ret.rrf_fuse(lexical, [])
    by_id = {tid: score for tid, score in fused}
    assert by_id[10] == pytest.approx(1 / (RRF_K + 1))
    assert by_id[20] == pytest.approx(1 / (RRF_K + 2))
    assert by_id[30] == pytest.approx(1 / (RRF_K + 3))


def test_rrf_score_math_both_sides(ret):
    """A ticket on both sides sums the two reciprocal-rank contributions."""
    lexical = _ranked([(10, 0.9), (20, 0.5)])
    semantic = _ranked([(10, 0.2), (30, 0.1)])
    fused = ret.rrf_fuse(lexical, semantic)
    by_id = {tid: score for tid, score in fused}
    # ticket 10: rank 1 on both sides
    assert by_id[10] == pytest.approx(1 / (RRF_K + 1) + 1 / (RRF_K + 1))
    # ticket 20: lexical rank 2 only
    assert by_id[20] == pytest.approx(1 / (RRF_K + 2))
    # ticket 30: semantic rank 2 only
    assert by_id[30] == pytest.approx(1 / (RRF_K + 2))


def test_rrf_k_constant_is_60(ret):
    assert ret.RRF_K == 60


# ---------------------------------------------------------------------------
# Ordering + determinism
# ---------------------------------------------------------------------------

def test_fused_ordering_by_score_desc(ret):
    lexical = _ranked([(1, 0.9), (2, 0.8), (3, 0.7)])
    semantic = _ranked([(3, 0.1), (1, 0.2)])
    fused = ret.rrf_fuse(lexical, semantic)
    ids = [tid for tid, _ in fused]
    # ticket 1: rank1+rank2; ticket 3: rank3+rank1; ticket 2: rank2 only
    assert ids[0] == 1
    assert ids[-1] == 2


def test_ties_break_on_ticket_id_asc(ret):
    # Both tickets only on lexical, adjacent -> distinct scores. Force a tie
    # by giving two tickets identical presence (same rank on the same single
    # side is impossible), so construct equal fused scores via symmetry.
    lexical = _ranked([(5, 0.9), (9, 0.9)])  # equal score -> same side
    semantic = _ranked([(9, 0.3), (5, 0.3)])  # mirrored equal scores
    fused = ret.rrf_fuse(lexical, semantic)
    ids = [tid for tid, _ in fused]
    # 5: rank1+rank2 ; 9: rank2+rank1 -> identical fused score -> id ASC
    assert ids == sorted(ids)
    assert ids[0] == 5


def test_identical_inputs_identical_ranking(ret):
    lexical = _ranked([(1, 0.9), (2, 0.7), (3, 0.5), (4, 0.3)])
    semantic = _ranked([(4, 0.05), (2, 0.04), (1, 0.03)])
    a = ret.rrf_fuse(lexical, semantic)
    b = ret.rrf_fuse(list(lexical), list(semantic))
    assert a == b


def test_ticket_on_only_one_side_still_ranks(ret):
    fused = ret.rrf_fuse(_ranked([(1, 0.9)]), _ranked([(2, 0.1)]))
    ids = {tid for tid, _ in fused}
    assert ids == {1, 2}


def test_empty_inputs_empty_result(ret):
    assert ret.rrf_fuse([], []) == []


def test_result_is_list_of_id_score_pairs(ret):
    fused = ret.rrf_fuse(_ranked([(1, 0.9), (2, 0.8)]), _ranked([(2, 0.1)]))
    assert all(isinstance(tid, int) and isinstance(score, float)
               for tid, score in fused)
