"""T005: Unit tests for the embedding checkpoint/resume semantics.

Mirrors the feature 009 checkpoint discipline (research R4): append-only
JSONL checkpoint, resume-by-default, exactly-once coverage after simulated
interruption, loud failure on torn/corrupt/unknown data, checkpoint deletion
on completion, explicit --fresh. The endpoint is stubbed; the checkpoint and
ordering logic under test is real.
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
GENERATOR_PATH = os.path.join(REPO_ROOT, "scripts", "generate_embeddings.py")

DIM = 768


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_embeddings", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def gen():
    return _load_generator()


def _tickets(n):
    """Pinned-order ticket stubs (ticket_id ascending, as in tickets.csv)."""
    return [{"ticket_id": str(847201 + i), "closed_at": "2025-01-02 00:00:00"}
            for i in range(n)]


def _entry(ticket_id):
    return {"ticket_id": ticket_id, "embedding": [0.01] * DIM}


# ---------------------------------------------------------------------------
# Checkpoint append + load
# ---------------------------------------------------------------------------

def test_checkpoint_append_and_load_roundtrip(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    gen.append_checkpoint(str(cp), [_entry(847201), _entry(847202)])
    gen.append_checkpoint(str(cp), [_entry(847203)])
    done = gen.load_checkpoint(str(cp))
    assert sorted(done.keys()) == [847201, 847202, 847203]
    assert done[847201]["embedding"] == [0.01] * DIM


def test_load_missing_checkpoint_returns_empty(gen, tmp_path):
    assert gen.load_checkpoint(str(tmp_path / "absent.jsonl")) == {}


def test_torn_final_line_fails_loudly(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    cp.write_text(json.dumps(_entry(847201)) + "\n" + '{"ticket_id": 847202, "emb',
                  encoding="utf-8")
    with pytest.raises(gen.CheckpointError):
        gen.load_checkpoint(str(cp))


def test_corrupt_json_line_fails_loudly(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    cp.write_text("not json at all\n", encoding="utf-8")
    with pytest.raises(gen.CheckpointError):
        gen.load_checkpoint(str(cp))


def test_unknown_ticket_id_in_checkpoint_fails_loudly(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    cp.write_text(json.dumps(_entry(999999)) + "\n", encoding="utf-8")
    tickets = _tickets(3)
    with pytest.raises(gen.CheckpointError):
        gen.plan_remaining(tickets, gen.load_checkpoint(str(cp)))


def test_duplicate_ticket_id_in_checkpoint_fails_loudly(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    cp.write_text(json.dumps(_entry(847201)) + "\n" + json.dumps(_entry(847201)) + "\n",
                  encoding="utf-8")
    with pytest.raises(gen.CheckpointError):
        gen.load_checkpoint(str(cp))


# ---------------------------------------------------------------------------
# Resume planning (pinned tickets.csv order, never re-accept, never skip)
# ---------------------------------------------------------------------------

def test_plan_remaining_full_when_no_checkpoint(gen):
    tickets = _tickets(4)
    remaining = gen.plan_remaining(tickets, {})
    assert [int(t["ticket_id"]) for t in remaining] == [847201, 847202, 847203, 847204]


def test_resume_continues_with_remaining_in_order(gen):
    tickets = _tickets(6)
    done = {847201: _entry(847201), 847202: _entry(847202), 847203: _entry(847203)}
    remaining = gen.plan_remaining(tickets, done)
    assert [int(t["ticket_id"]) for t in remaining] == [847204, 847205, 847206]


def test_simulated_interruption_resume_exactly_once(gen, tmp_path):
    """Partial checkpoint -> resume -> exactly-once coverage of all tickets."""
    tickets = _tickets(10)
    cp = tmp_path / "checkpoint.jsonl"

    # First "run": accepts 4 tickets, then is interrupted.
    gen.append_checkpoint(str(cp), [_entry(847201 + i) for i in range(4)])

    done = gen.load_checkpoint(str(cp))
    assert sorted(done.keys()) == [847201, 847202, 847203, 847204]
    remaining = gen.plan_remaining(tickets, done)
    accepted = dict(done)
    for t in remaining:
        tid = int(t["ticket_id"])
        assert tid not in done  # never re-accepted
        e = _entry(tid)
        gen.append_checkpoint(str(cp), [e])
        accepted[tid] = e
    assert sorted(accepted.keys()) == [847201 + i for i in range(10)]


# ---------------------------------------------------------------------------
# Completion + fresh
# ---------------------------------------------------------------------------

def test_finalize_writes_artifact_and_deletes_checkpoint(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    out = tmp_path / "artifact.jsonl"
    tickets = _tickets(5)
    entries = [_entry(int(t["ticket_id"])) for t in tickets]
    gen.append_checkpoint(str(cp), entries)
    gen.finalize_artifact(str(out), entries, checkpoint_path=str(cp))
    assert not cp.exists()
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 5
    for line, t in zip(lines, tickets):
        obj = json.loads(line)
        assert obj["ticket_id"] == int(t["ticket_id"])
        assert len(obj["embedding"]) == DIM


def test_fresh_discards_checkpoint(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    gen.append_checkpoint(str(cp), [_entry(847201)])
    assert cp.exists()
    gen.discard_checkpoint(str(cp))
    assert not cp.exists()
    assert gen.load_checkpoint(str(cp)) == {}
