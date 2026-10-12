"""T006: Unit tests for the generation checkpoint/resume semantics.

Covers research R3: append-only JSONL checkpoint, resume-by-default,
exactly-once coverage after simulated interruption, loud failure on torn or
corrupt checkpoint data, checkpoint deletion on completion, explicit --fresh.

The LM is stubbed; the checkpoint and batching logic under test is real.
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
GENERATOR_PATH = os.path.join(REPO_ROOT, "scripts", "generate_ticket_texts.py")


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_ticket_texts", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def gen():
    return _load_generator()


def _tickets(n, open_ids=()):
    return [
        {"ticket_id": str(1000 + i), "merchant_id": "1", "category": "Notifications",
         "sub_category": "Email Delivery Failure", "priority": "P3",
         "created_at": "2025-01-01 00:00:00", "is_legacy": "false",
         "assigned_agent_id": "1", "category_mismatch": "false",
         "first_response_at": "2025-01-01 01:00:00",
         "closed_at": "" if (1000 + i) in open_ids else "2025-01-02 00:00:00",
         "ttfr_hours": "1.0", "resolution_hours": "24.0",
         "response_breached": "false", "resolution_breached": "false",
         "is_reopened": "false", "is_reopen_child": "false",
         "is_incident_ticket": "false", "csat_score": "0.9"}
        for i in range(n)
    ]


def _entry(ticket_id, is_open=False):
    return {
        "ticket_id": ticket_id,
        "short_description": f"The email for ticket {ticket_id} is not delivered.",
        "description": "The merchant reports missing emails. Customers complain. It started today.",
        "resolution_notes": None if is_open else "The queue was stuck. The team flushed it. Emails flow again.",
    }


# ---------------------------------------------------------------------------
# Checkpoint append + load
# ---------------------------------------------------------------------------

def test_checkpoint_append_and_load_roundtrip(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    gen.append_checkpoint(str(cp), [_entry(1000), _entry(1001)])
    gen.append_checkpoint(str(cp), [_entry(1002)])
    done = gen.load_checkpoint(str(cp))
    assert sorted(done.keys()) == [1000, 1001, 1002]
    assert done[1000]["ticket_id"] == 1000


def test_load_missing_checkpoint_returns_empty(gen, tmp_path):
    assert gen.load_checkpoint(str(tmp_path / "absent.jsonl")) == {}


def test_torn_final_line_fails_loudly(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    cp.write_text(json.dumps(_entry(1000)) + "\n" + '{"ticket_id": 1001, "short', encoding="utf-8")
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
        gen.plan_remaining_batches(tickets, gen.load_checkpoint(str(cp)), batch_size=5)


# ---------------------------------------------------------------------------
# Batch planning + resume
# ---------------------------------------------------------------------------

def test_plan_batches_in_csv_order(gen):
    tickets = _tickets(12)
    batches = gen.plan_remaining_batches(tickets, {}, batch_size=5)
    assert [[int(t["ticket_id"]) for t in b] for b in batches] == [
        [1000, 1001, 1002, 1003, 1004],
        [1005, 1006, 1007, 1008, 1009],
        [1010, 1011],
    ]


def test_resume_skips_only_checkpointed_tickets(gen):
    tickets = _tickets(12)
    done = {1000: _entry(1000), 1001: _entry(1001), 1002: _entry(1002),
            1003: _entry(1003), 1004: _entry(1004)}
    batches = gen.plan_remaining_batches(tickets, done, batch_size=5)
    assert [[int(t["ticket_id"]) for t in b] for b in batches] == [
        [1005, 1006, 1007, 1008, 1009],
        [1010, 1011],
    ]


def test_simulated_interruption_resume_exactly_once(gen, tmp_path):
    """Partial checkpoint -> resume -> exactly-once coverage, no re-accept, no skip."""
    tickets = _tickets(12, open_ids={1002, 1007})
    cp = tmp_path / "checkpoint.jsonl"

    # First "run": accepts batch 1 (5 tickets), then is interrupted.
    first_batch = tickets[:5]
    batch1_entries = [_entry(int(t["ticket_id"]), is_open=(t["closed_at"] == ""))
                      for t in first_batch]
    gen.append_checkpoint(str(cp), batch1_entries)

    # Resume: load, plan, accept remaining batches.
    done = gen.load_checkpoint(str(cp))
    assert sorted(done.keys()) == [1000, 1001, 1002, 1003, 1004]
    remaining = gen.plan_remaining_batches(tickets, done, batch_size=5)
    accepted = dict(done)
    for batch in remaining:
        entries = [_entry(int(t["ticket_id"]), is_open=(t["closed_at"] == "")) for t in batch]
        gen.append_checkpoint(str(cp), entries)
        for e in entries:
            assert e["ticket_id"] not in done  # never re-accepted
            accepted[e["ticket_id"]] = e
    assert sorted(accepted.keys()) == [1000 + i for i in range(12)]


# ---------------------------------------------------------------------------
# Completion + fresh
# ---------------------------------------------------------------------------

def test_finalize_writes_artifact_and_deletes_checkpoint(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    out = tmp_path / "artifact.jsonl"
    tickets = _tickets(7, open_ids={1003})
    entries = [_entry(int(t["ticket_id"]), is_open=(t["closed_at"] == "")) for t in tickets]
    gen.append_checkpoint(str(cp), entries)
    gen.finalize_artifact(str(out), entries, checkpoint_path=str(cp))
    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 7
    for line, ticket in zip(lines, tickets):
        obj = json.loads(line)
        assert obj["ticket_id"] == int(ticket["ticket_id"])
        assert set(obj.keys()) == {"ticket_id", "short_description", "description", "resolution_notes"}
    assert not cp.exists()


def test_fresh_discards_checkpoint(gen, tmp_path):
    cp = tmp_path / "checkpoint.jsonl"
    gen.append_checkpoint(str(cp), [_entry(1000)])
    assert cp.exists()
    gen.discard_checkpoint(str(cp))
    assert not cp.exists()
    assert gen.load_checkpoint(str(cp)) == {}
