#!/usr/bin/env python3
"""Deterministic validation suite for generated ticket texts (feature 009).

Offline, model-free, stdlib-only quality gate over a generated artifact
(data/raw/tickets_texts.jsonl) against the pinned tickets.csv. Implements
the 7 checks of specs/009-synthetic-ticket-texts/contracts/validation-suite.md:

  1. schema + coverage (every pinned ticket exactly once)
  2. non-empty fields + {...} slot-marker rejection
  3. length limits with deterministic [.!?] sentence counting
  4. English-only heuristic (>=95% printable ASCII + function-word presence)
  5. secrets/PII canary scan
  6. category-consistency lexicon (20 sub_category pairs)
  7. NULL rule (resolution_notes null exactly for open tickets)

Exit 0 on 100% pass; exit 1 with a per-violation report otherwise.
Unit tests (tests/unit/test_ticket_texts_validation.py) reuse these check
functions with canary inputs.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass

REPO_ROOT = __file__.rsplit("/scripts/", 1)[0] if "/scripts/" in __file__ else "."
DEFAULT_INPUT = "data/raw/tickets_texts.jsonl"
DEFAULT_TICKETS = "data/raw/tickets.csv"

CHECK_NAMES = [
    "schema+coverage",
    "non-empty",
    "lengths",
    "english-only",
    "secrets-pii-scan",
    "category-consistency",
    "null-rule",
]

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    check: str
    ticket_id: object
    detail: str

    def as_dict(self) -> dict:
        return {"check": self.check, "ticket_id": self.ticket_id, "detail": self.detail}


def load_tickets(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_entries(path: str) -> list[dict]:
    entries = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{lineno}: unparseable JSON line (torn or corrupt "
                    f"artifact): {exc}") from exc
    return entries


# ---------------------------------------------------------------------------
# Check 1: schema + coverage
# ---------------------------------------------------------------------------

ENTRY_KEYS = ("ticket_id", "short_description", "description", "resolution_notes")


def _schema_errors(entry: object) -> list[str]:
    if not isinstance(entry, dict):
        return ["entry is not a JSON object"]
    errors = []
    for key in ENTRY_KEYS:
        if key not in entry:
            errors.append(f"missing key {key!r}")
    if errors:
        return errors
    if not isinstance(entry["ticket_id"], int) or isinstance(entry["ticket_id"], bool):
        errors.append("ticket_id must be an integer")
    for key in ("short_description", "description"):
        if not isinstance(entry[key], str):
            errors.append(f"{key} must be a string")
    if entry["resolution_notes"] is not None and not isinstance(entry["resolution_notes"], str):
        errors.append("resolution_notes must be a string or null")
    return errors


def check_schema_coverage(entries: list[dict], tickets: list[dict]) -> list[Violation]:
    violations: list[Violation] = []
    valid_ids: list[int] = []
    for entry in entries:
        errors = _schema_errors(entry)
        if errors:
            tid = entry.get("ticket_id") if isinstance(entry, dict) else None
            for detail in errors:
                violations.append(Violation("schema+coverage", tid, detail))
        else:
            valid_ids.append(entry["ticket_id"])
    expected_ids = [int(t["ticket_id"]) for t in tickets]
    seen: set[int] = set()
    for tid in valid_ids:
        if tid in seen:
            violations.append(Violation(
                "schema+coverage", tid, f"duplicate entry for ticket_id {tid}"))
        seen.add(tid)
    expected_set = set(expected_ids)
    for tid in sorted(seen - expected_set):
        violations.append(Violation(
            "schema+coverage", tid, f"unknown ticket_id {tid} (not in pinned tickets.csv)"))
    for tid in sorted(expected_set - seen):
        violations.append(Violation(
            "schema+coverage", tid, f"missing entry for ticket_id {tid}"))
    return violations


# ---------------------------------------------------------------------------
# Check 2: non-empty fields + slot markers
# ---------------------------------------------------------------------------

_SLOT_MARKER = re.compile(r"\{[^{}]*\}")


def check_non_empty(entries: list[dict]) -> list[Violation]:
    violations: list[Violation] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("ticket_id")
        for key in ("short_description", "description", "resolution_notes"):
            if key not in entry:
                continue
            value = entry[key]
            if value is None and key == "resolution_notes":
                continue
            if not isinstance(value, str):
                continue
            if not value.strip():
                violations.append(Violation("non-empty", tid, f"{key} is empty"))
            elif _SLOT_MARKER.search(value):
                violations.append(Violation(
                    "non-empty", tid, f"{key} contains an unresolved slot marker"))
    return violations


# ---------------------------------------------------------------------------
# Check 3: length limits + sentence counting
# ---------------------------------------------------------------------------

# Sentence convention (research R5): a sentence is a segment terminated by
# one or more of [.!?] followed by whitespace or end of text. A trailing
# segment without a terminator counts as one sentence.
_SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s+|$)")

LIMITS = {
    "short_description": {"sentences": (1, 1), "chars": 100},
    "description": {"sentences": (2, 4), "chars": 600},
    "resolution_notes": {"sentences": (1, 3), "chars": 450},
}


def count_sentences(text: str) -> int:
    text = text.strip()
    if not text:
        return 0
    segments = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    return len(segments)


def check_lengths(entries: list[dict]) -> list[Violation]:
    violations: list[Violation] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("ticket_id")
        for key, limits in LIMITS.items():
            value = entry.get(key)
            if value is None or not isinstance(value, str):
                continue
            lo, hi = limits["sentences"]
            n = count_sentences(value)
            if not (lo <= n <= hi):
                violations.append(Violation(
                    "lengths", tid,
                    f"{key} has {n} sentences (expected {lo}-{hi})"))
            if len(value) > limits["chars"]:
                violations.append(Violation(
                    "lengths", tid,
                    f"{key} is {len(value)} chars (limit {limits['chars']})"))
    return violations


# ---------------------------------------------------------------------------
# Check 4: English-only heuristic
# ---------------------------------------------------------------------------

_FUNCTION_WORDS = frozenset({
    "the", "a", "an", "and", "or", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "on", "for", "with", "at", "by", "from", "as", "it",
    "its", "this", "that", "these", "those", "not", "no", "but", "if", "then",
    "than", "so", "we", "they", "he", "she", "i", "you", "has", "have", "had",
    "do", "does", "did", "will", "would", "can", "could", "should", "after",
    "when", "while", "during", "every", "all", "each", "per", "their", "our",
})
_WORD = re.compile(r"[A-Za-z]+")
_ASCII_PRINTABLE = re.compile(r"^[\x20-\x7e\s]*$")


def _english_ratio(text: str) -> float:
    if not text:
        return 1.0
    printable = sum(1 for ch in text if ch in "\n\t" or 0x20 <= ord(ch) <= 0x7E)
    return printable / len(text)


def check_english_only(entries: list[dict]) -> list[Violation]:
    violations: list[Violation] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("ticket_id")
        for key in ("short_description", "description", "resolution_notes"):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            if _english_ratio(value) < 0.95:
                violations.append(Violation(
                    "english-only", tid,
                    f"{key} has < 95% printable ASCII characters"))
                continue
            sentences = [s for s in _SENTENCE_SPLIT.split(value.strip()) if s.strip()]
            for segment in sentences:
                words = {w.lower() for w in _WORD.findall(segment)}
                if words and not (words & _FUNCTION_WORDS):
                    violations.append(Violation(
                        "english-only", tid,
                        f"{key} sentence without any English function word: "
                        f"{segment.strip()[:60]!r}"))
                    break
    return violations


# ---------------------------------------------------------------------------
# Check 5: secrets/PII canary scan
# ---------------------------------------------------------------------------

_SECRETS_PATTERNS = [
    ("password assignment", re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE)),
    ("bearer token", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)),
    ("api key", re.compile(r"\b(?:api[_-]?key|apikey|access[_-]?token|secret[_-]?key)\s*[:=]\s*\S+", re.IGNORECASE)),
    ("api-key shape", re.compile(r"\bsk-[A-Za-z0-9]{12,}\b")),
    ("PEM header", re.compile(r"-----BEGIN [A-Z ]*-----")),
    ("e-mail address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone number", re.compile(r"(?:\+?\d[\s().-]?){7,}\d")),
    ("IPv4 address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]


def check_secrets_pii(entries: list[dict]) -> list[Violation]:
    violations: list[Violation] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("ticket_id")
        for key in ("short_description", "description", "resolution_notes"):
            value = entry.get(key)
            if not isinstance(value, str):
                continue
            for name, pattern in _SECRETS_PATTERNS:
                if pattern.search(value):
                    violations.append(Violation(
                        "secrets-pii-scan", tid,
                        f"{key} matches {name} pattern"))
    return violations


# ---------------------------------------------------------------------------
# Check 6: category-consistency lexicon (hand-maintained, reviewed like code)
# ---------------------------------------------------------------------------

# required: >= 1 keyword must appear in short_description + description
#           (case-insensitive substring match).
# exclusive_conflict: keywords that unambiguously belong to OTHER categories
#           and must NOT appear in this pair's text.
CATEGORY_LEXICON: dict[tuple[str, str], dict[str, list[str]]] = {
    ("API Integrations", "Authentication Error"): {
        "required": ["api", "authentication", "auth token", "credential", "api key", "token"],
        "exclusive_conflict": [],
    },
    ("API Integrations", "Endpoint Timeout"): {
        "required": ["api", "endpoint", "timeout", "timed out", "request"],
        "exclusive_conflict": [],
    },
    ("API Integrations", "Rate Limiting"): {
        "required": ["rate limit", "rate-limit", "429", "throttl", "quota", "api"],
        "exclusive_conflict": [],
    },
    ("API Integrations", "Webhook Failures"): {
        "required": ["webhook", "callback", "delivery", "endpoint"],
        "exclusive_conflict": [],
    },
    ("Account Access", "2FA Reset"): {
        "required": ["2fa", "two-factor", "two factor", "authenticator", "verification code", "mfa"],
        "exclusive_conflict": [],
    },
    ("Account Access", "Password Reset"): {
        "required": ["password", "reset", "credential", "account"],
        "exclusive_conflict": [],
    },
    ("Account Access", "SSO Failure"): {
        "required": ["sso", "single sign-on", "single sign on", "saml", "identity provider", "login", "sign in", "sign-in"],
        "exclusive_conflict": [],
    },
    ("Account Access", "User Permissions"): {
        "required": ["permission", "role", "access", "user", "authorization"],
        "exclusive_conflict": [],
    },
    ("Fulfilment & Logistics", "Carrier Sync Failure"): {
        "required": ["carrier", "sync", "shipment", "shipping", "tracking"],
        "exclusive_conflict": [],
    },
    ("Fulfilment & Logistics", "Inventory Mismatch"): {
        "required": ["inventory", "stock", "warehouse", "sku", "count"],
        "exclusive_conflict": [],
    },
    ("Fulfilment & Logistics", "Label Generation"): {
        "required": ["label", "shipping", "print", "barcode", "shipment"],
        "exclusive_conflict": [],
    },
    ("Fulfilment & Logistics", "Tracking Updates"): {
        "required": ["tracking", "shipment", "carrier", "status", "scan"],
        "exclusive_conflict": [],
    },
    ("Notifications", "Email Delivery Failure"): {
        "required": ["email", "e-mail", "mail", "delivery", "inbox", "smtp"],
        "exclusive_conflict": [],
    },
    ("Notifications", "SMS Gateway Drag"): {
        "required": ["sms", "text message", "gateway", "message", "delivery"],
        "exclusive_conflict": [],
    },
    ("Notifications", "Template Syntax Error"): {
        "required": ["template", "syntax", "render", "placeholder", "variable"],
        "exclusive_conflict": [],
    },
    ("Notifications", "Webhook Retries"): {
        "required": ["webhook", "retry", "retries", "notification", "delivery", "callback"],
        "exclusive_conflict": [],
    },
    ("Payments & Checkout", "3DS Authentication"): {
        "required": ["3ds", "3-d secure", "3d secure", "authentication", "verification", "challenge", "payment"],
        "exclusive_conflict": [],
    },
    ("Payments & Checkout", "Card Declines"): {
        "required": ["card", "decline", "declined", "checkout", "payment", "charge"],
        "exclusive_conflict": [],
    },
    ("Payments & Checkout", "Payout Delays"): {
        "required": ["payout", "settlement", "transfer", "bank", "delay", "disbursement"],
        "exclusive_conflict": [],
    },
    ("Payments & Checkout", "Refund Processing"): {
        "required": ["refund", "reimbursement", "return", "credit", "payment"],
        "exclusive_conflict": [],
    },
}

# Category-level exclusive markers: keywords that unambiguously indicate one
# category; their presence in a ticket of a DIFFERENT category is a
# consistency violation (research R5 example: "login"/"password" on a
# Payments ticket fails). Deliberately short and unambiguous.
CATEGORY_EXCLUSIVE_KEYWORDS: dict[str, list[str]] = {
    "Account Access": ["login", "log in", "sign in", "sign-in", "password",
                       "2fa", "two-factor", "sso"],
    "Payments & Checkout": ["refund", "payout", "3ds", "card declined",
                            "chargeback"],
    "Fulfilment & Logistics": ["shipment", "carrier", "inventory", "warehouse",
                               "shipping label"],
    "Notifications": ["sms", "smtp", "email template"],
    "API Integrations": [],
}


def check_category_consistency(entries: list[dict], tickets: list[dict]) -> list[Violation]:
    pair_by_id = {int(t["ticket_id"]): (t["category"], t["sub_category"]) for t in tickets}
    violations: list[Violation] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("ticket_id")
        if tid not in pair_by_id:
            continue
        category, sub_category = pair_by_id[tid]
        lex = CATEGORY_LEXICON.get((category, sub_category))
        if lex is None:
            violations.append(Violation(
                "category-consistency", tid,
                f"no lexicon entry for {category!r}/{sub_category!r}"))
            continue
        haystack = " ".join(
            str(entry.get(k) or "") for k in ("short_description", "description")
        ).lower()
        if not any(kw.lower() in haystack for kw in lex["required"]):
            violations.append(Violation(
                "category-consistency", tid,
                f"no required keyword of {sub_category!r} found "
                f"(any of {lex['required']!r})"))
        for other_category, keywords in CATEGORY_EXCLUSIVE_KEYWORDS.items():
            if other_category == category:
                continue
            for kw in keywords:
                if kw.lower() in haystack:
                    violations.append(Violation(
                        "category-consistency", tid,
                        f"exclusive {other_category!r} keyword {kw!r} present on a "
                        f"{category!r} ticket"))
    return violations


# ---------------------------------------------------------------------------
# Check 7: NULL rule
# ---------------------------------------------------------------------------


def check_null_rule(entries: list[dict], tickets: list[dict]) -> list[Violation]:
    open_by_id = {int(t["ticket_id"]): not t["closed_at"].strip() for t in tickets}
    violations: list[Violation] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("ticket_id")
        if tid not in open_by_id or "resolution_notes" not in entry:
            continue
        is_open = open_by_id[tid]
        notes = entry["resolution_notes"]
        if is_open and notes is not None:
            violations.append(Violation(
                "null-rule", tid,
                "resolution_notes present for an open ticket (must be null)"))
        if not is_open and notes is None:
            violations.append(Violation(
                "null-rule", tid,
                "resolution_notes null for a closed ticket (must be present)"))
    return violations


# ---------------------------------------------------------------------------
# Full suite
# ---------------------------------------------------------------------------


def validate(input_path: str, tickets_path: str) -> list[Violation]:
    tickets = load_tickets(tickets_path)
    entries = load_entries(input_path)
    violations: list[Violation] = []
    violations += check_schema_coverage(entries, tickets)
    violations += check_non_empty(entries)
    violations += check_lengths(entries)
    violations += check_english_only(entries)
    violations += check_secrets_pii(entries)
    violations += check_category_consistency(entries, tickets)
    violations += check_null_rule(entries, tickets)
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", default=DEFAULT_INPUT,
                        help="generated artifact JSONL (default: %(default)s)")
    parser.add_argument("--tickets", default=DEFAULT_TICKETS,
                        help="pinned tickets.csv (default: %(default)s)")
    parser.add_argument("--report", default=None,
                        help="optional JSON report output path")
    args = parser.parse_args(argv)

    try:
        violations = validate(args.input, args.tickets)
    except (OSError, ValueError) as exc:
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        return 1

    entries = load_entries(args.input)
    report = {
        "input": args.input,
        "tickets": args.tickets,
        "entries": len(entries),
        "checks": CHECK_NAMES,
        "violations": [v.as_dict() for v in violations],
        "passed": not violations,
    }
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

    if violations:
        print(f"VALIDATION FAILED: {len(violations)} violation(s) across "
              f"{len(entries)} entries", file=sys.stderr)
        cap = 50
        for v in violations[:cap]:
            print(f"  [{v.check}] ticket {v.ticket_id}: {v.detail}", file=sys.stderr)
        if len(violations) > cap:
            print(f"  ... and {len(violations) - cap} more", file=sys.stderr)
        return 1
    print(f"VALIDATION PASSED: all {len(CHECK_NAMES)} checks, "
          f"{len(entries)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
