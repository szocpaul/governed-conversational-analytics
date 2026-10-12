"""T004: Canary-driven unit tests for the deterministic ticket-text validation suite.

Covers all 7 checks from specs/009-synthetic-ticket-texts/contracts/validation-suite.md:
(1) schema + coverage, (2) non-empty fields + slot-marker rejection, (3) length limits
with deterministic sentence counting, (4) English-only heuristic, (5) secrets/PII canary
scan, (6) category-consistency lexicon, (7) NULL rule against pinned tickets.csv.

The module under test is scripts/validate_ticket_texts.py (stdlib only, no model calls).
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
VALIDATOR_PATH = os.path.join(REPO_ROOT, "scripts", "validate_ticket_texts.py")
TICKETS_CSV = os.path.join(REPO_ROOT, "data", "raw", "tickets.csv")


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_ticket_texts", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass/pydantic introspection resolves the
    # module's namespace.
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def vv():
    return _load_validator()


@pytest.fixture(scope="module")
def tickets(vv):
    return vv.load_tickets(TICKETS_CSV)


def _entry(ticket_id, short="The sync job fails nightly.",
           desc="The merchant reports the sync job fails every night. It started after the update. No data reaches the warehouse.",
           notes="The team restarted the sync service. The job completed after the restart. Monitoring confirmed the fix."):
    return {
        "ticket_id": ticket_id,
        "short_description": short,
        "description": desc,
        "resolution_notes": notes,
    }


# ---------------------------------------------------------------------------
# Fixtures from the pinned dataset
# ---------------------------------------------------------------------------

def test_pinned_dataset_ground_truth(tickets):
    """The pinned dataset ground truths the suite relies on (spec Background)."""
    assert len(tickets) == 2057
    open_ids = [t for t in tickets if not t["closed_at"].strip()]
    assert len(open_ids) == 250
    pairs = {(t["category"], t["sub_category"]) for t in tickets}
    assert len(pairs) == 20


# ---------------------------------------------------------------------------
# Check 1: schema + coverage
# ---------------------------------------------------------------------------

def test_schema_coverage_small_fixture_passes(vv, tickets):
    small = tickets[:5]
    entries = [_entry(int(t["ticket_id"]),
                      notes=None if not t["closed_at"].strip() else "Fixed it. Verified it.") 
               for t in small]
    violations = vv.check_schema_coverage(entries, small)
    assert violations == []


def test_schema_coverage_rejects_missing_ticket(vv, tickets):
    small = tickets[:5]
    entries = [_entry(int(t["ticket_id"])) for t in small[:4]]
    violations = vv.check_schema_coverage(entries, small)
    assert any("missing" in v.detail.lower() or "coverage" in v.check for v in violations)


def test_schema_coverage_rejects_duplicate_ticket(vv, tickets):
    small = tickets[:5]
    entries = [_entry(int(t["ticket_id"])) for t in small]
    entries.append(_entry(int(small[0]["ticket_id"])))
    violations = vv.check_schema_coverage(entries, small)
    assert any("duplicate" in v.detail.lower() for v in violations)


def test_schema_coverage_rejects_unknown_ticket(vv, tickets):
    small = tickets[:5]
    entries = [_entry(int(t["ticket_id"])) for t in small[:4]]
    entries.append(_entry(999999999))
    violations = vv.check_schema_coverage(entries, small)
    assert violations


def test_schema_rejects_missing_key(vv, tickets):
    small = tickets[:3]
    entries = [_entry(int(t["ticket_id"])) for t in small]
    del entries[1]["description"]
    violations = vv.check_schema_coverage(entries, small)
    assert violations


def test_schema_rejects_wrong_type(vv, tickets):
    small = tickets[:3]
    entries = [_entry(int(t["ticket_id"])) for t in small]
    entries[0]["ticket_id"] = str(entries[0]["ticket_id"])
    violations = vv.check_schema_coverage(entries, small)
    assert violations


# ---------------------------------------------------------------------------
# Check 2: non-empty fields + slot markers
# ---------------------------------------------------------------------------

def test_non_empty_accepts_valid(vv):
    assert vv.check_non_empty([_entry(1)]) == []


def test_non_empty_rejects_empty_string(vv):
    assert vv.check_non_empty([_entry(1, short="")])


def test_non_empty_rejects_whitespace_string(vv):
    assert vv.check_non_empty([_entry(1, desc="   \n  ")])


def test_non_empty_rejects_slot_markers(vv):
    assert vv.check_non_empty([_entry(1, short="Issue with {sub_category}.")])
    assert vv.check_non_empty([_entry(1, desc="The {merchant_name} reports a problem. It recurs daily. Nothing works.")])
    assert vv.check_non_empty([_entry(1, notes="Fixed {issue}. Verified.")])


def test_non_empty_allows_null_resolution_notes(vv):
    assert vv.check_non_empty([_entry(1, notes=None)]) == []


# ---------------------------------------------------------------------------
# Check 3: length limits + sentence counting
# ---------------------------------------------------------------------------

def test_sentence_counting_convention(vv):
    assert vv.count_sentences("One sentence.") == 1
    assert vv.count_sentences("First. Second! Third?") == 3
    assert vv.count_sentences("No terminator") == 1
    assert vv.count_sentences("") == 0


def test_lengths_accept_valid(vv):
    assert vv.check_lengths([_entry(1)]) == []


def test_short_description_two_sentences_rejected(vv):
    assert vv.check_lengths([_entry(1, short="Sync fails. It broke Tuesday.")])


def test_short_description_over_100_chars_rejected(vv):
    assert vv.check_lengths([_entry(1, short="x" * 101 + ".")])


def test_short_description_exactly_100_chars_accepted(vv):
    assert vv.check_lengths([_entry(1, short="x" * 99 + ".")]) == []


def test_description_one_sentence_rejected(vv):
    assert vv.check_lengths([_entry(1, desc="Only one sentence here.")])


def test_description_five_sentences_rejected(vv):
    assert vv.check_lengths([_entry(1, desc="One. Two. Three. Four. Five.")])


def test_description_over_600_chars_rejected(vv):
    long_desc = ("x" * 200 + ". ") * 3
    assert vv.check_lengths([_entry(1, desc=long_desc.strip())])


def test_resolution_notes_four_sentences_rejected(vv):
    assert vv.check_lengths([_entry(1, notes="One. Two. Three. Four.")])


def test_resolution_notes_over_450_chars_rejected(vv):
    long_notes = ("x" * 160 + ". ") * 3
    assert vv.check_lengths([_entry(1, notes=long_notes.strip())])


def test_resolution_notes_null_skips_length_check(vv):
    assert vv.check_lengths([_entry(1, notes=None)]) == []


# ---------------------------------------------------------------------------
# Check 4: English-only heuristic
# ---------------------------------------------------------------------------

def test_english_only_accepts_english(vv):
    assert vv.check_english_only([_entry(1)]) == []


def test_english_only_rejects_non_ascii_canary(vv):
    entry = _entry(1, short="Die Synchronisation schlägt fehl.",
                   desc="Der Händler meldet ein Problem. Es tritt jede Nacht auf. Keine Daten kommen an.")
    assert vv.check_english_only(entry and [entry])


def test_english_only_rejects_mojibake_canary(vv):
    garbled = "Sync fails \u00e2\u20ac\u201c the job is broken."
    entry = _entry(1, short=garbled,
                   desc="The merchant reports garbled output. It recurs nightly. Nothing works.")
    assert vv.check_english_only([entry])


def test_english_only_rejects_text_without_function_words(vv):
    entry = _entry(1, short="Xyzzy plugh qwerty.",
                   desc="Xyzzy plugh qwerty. Foo bar baz qux. Zzz yyy xxx.")
    assert vv.check_english_only([entry])


# ---------------------------------------------------------------------------
# Check 5: secrets/PII canary scan
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("canary", [
    "The password=hunter2 was rotated.",
    "Use Bearer abcdef1234567890abcdef to authenticate.",
    "The api_key=sk-abcdef1234567890abcdef was exposed.",
    "-----BEGIN PRIVATE KEY----- was found in the log.",
    "Contact jane.doe@example.com for details.",
    "Call +1-555-123-4567 for the on-call engineer.",
    "The server at 192.168.1.100 refused the connection.",
])
def test_secrets_pii_canaries_rejected(vv, canary):
    entry = _entry(1, desc=f"The merchant reports an issue. {canary} It recurs nightly.")
    assert vv.check_secrets_pii([entry]), canary


def test_secrets_pii_clean_text_accepted(vv):
    assert vv.check_secrets_pii([_entry(1)]) == []


# ---------------------------------------------------------------------------
# Check 6: category-consistency lexicon
# ---------------------------------------------------------------------------

def _ticket_for_pair(tickets, category, sub_category):
    for t in tickets:
        if t["category"] == category and t["sub_category"] == sub_category:
            return t
    raise AssertionError(f"no ticket for {category}/{sub_category}")


def test_lexicon_covers_all_20_pairs(vv, tickets):
    pairs = {(t["category"], t["sub_category"]) for t in tickets}
    assert set(vv.CATEGORY_LEXICON.keys()) == pairs
    assert len(pairs) == 20


def test_category_consistency_accepts_matching_text(vv, tickets):
    t = _ticket_for_pair(tickets, "Account Access", "Password Reset")
    entry = _entry(int(t["ticket_id"]),
                   short="The user cannot complete a password reset.",
                   desc="The merchant reports the password reset email never arrives. Users remain locked out of the account. The issue started this morning.")
    assert vv.check_category_consistency([entry], tickets) == []


def test_category_consistency_rejects_missing_own_keyword(vv, tickets):
    t = _ticket_for_pair(tickets, "Account Access", "Password Reset")
    entry = _entry(int(t["ticket_id"]))  # generic text with no password/account keyword
    assert vv.check_category_consistency([entry], tickets)


def test_category_consistency_rejects_exclusive_other_category_keyword(vv, tickets):
    t = _ticket_for_pair(tickets, "Payments & Checkout", "Card Declines")
    entry = _entry(int(t["ticket_id"]),
                   short="The customer card is declined at checkout.",
                   desc="The merchant reports cards are declined at the checkout. The login page also fails for the user. It started today.")
    assert vv.check_category_consistency([entry], tickets)


# ---------------------------------------------------------------------------
# Check 7: NULL rule against pinned tickets.csv
# ---------------------------------------------------------------------------

def test_null_rule_small_fixture(vv, tickets):
    small = tickets[:20]
    entries = []
    for t in small:
        is_open = not t["closed_at"].strip()
        entries.append(_entry(int(t["ticket_id"]),
                              notes=None if is_open else "Fixed it. Verified it."))
    assert vv.check_null_rule(entries, small) == []


def test_null_rule_rejects_notes_on_open_ticket(vv, tickets):
    open_ticket = next(t for t in tickets if not t["closed_at"].strip())
    entry = _entry(int(open_ticket["ticket_id"]), notes="Fixed it. Verified it.")
    violations = vv.check_null_rule([entry], [open_ticket])
    assert violations


def test_null_rule_rejects_null_on_closed_ticket(vv, tickets):
    closed_ticket = next(t for t in tickets if t["closed_at"].strip())
    entry = _entry(int(closed_ticket["ticket_id"]), notes=None)
    violations = vv.check_null_rule([entry], [closed_ticket])
    assert violations


# ---------------------------------------------------------------------------
# Full-suite CLI behavior on synthetic artifacts
# ---------------------------------------------------------------------------

def test_validate_full_artifact_synthetic_pass(vv, tickets, tmp_path):
    """A synthetic artifact covering all 2057 tickets with per-ticket valid text
    passes the whole suite (uses lexicon-aware text per sub_category)."""
    entries = []
    for t in tickets:
        pair = (t["category"], t["sub_category"])
        kw = vv.CATEGORY_LEXICON[pair]["required"][0]
        is_open = not t["closed_at"].strip()
        entries.append({
            "ticket_id": int(t["ticket_id"]),
            "short_description": f"The {kw} workflow fails for the merchant.",
            "description": (f"The merchant reports a {kw} problem. It started after "
                            f"the last update. The impact is limited to one account."),
            "resolution_notes": None if is_open else
                "The team applied a fix. The workflow recovered after the change. Verification confirmed the result.",
        })
    artifact = tmp_path / "texts.jsonl"
    artifact.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    violations = vv.validate(str(artifact), TICKETS_CSV)
    assert violations == []


def test_validate_detects_torn_jsonl_line(vv, tmp_path):
    artifact = tmp_path / "texts.jsonl"
    artifact.write_text('{"ticket_id": 1, "short_description": "a.", "description": "b. c.", "resolution_notes": null}\n{"ticket_id": 2, "short', encoding="utf-8")
    with pytest.raises(Exception):
        vv.load_entries(str(artifact))
