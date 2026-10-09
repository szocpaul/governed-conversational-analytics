"""Prompt-injection signaling (T003).

The classifier is TELEMETRY ONLY. It produces an InjectionSignal used for
observability (trace events, metrics); it is NEVER an authorization boundary
and carries no allow/deny semantics (FR-001). Deterministic backend controls
(validator, GraphJin policy, PostgreSQL read-only role) are the actual
security boundaries and are tested independently of this signal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class InjectionSignal:
    """Telemetry signal for a possibly malicious question.

    Deliberately has NO allow/deny/authorized attributes: classification is
    not authorization (FR-001). Callers may record the signal in traces but
    must never use it to grant or block access.
    """

    flagged: bool
    category: str  # stable telemetry category
    matched_patterns: tuple[str, ...] = field(default_factory=tuple)


# Heuristic patterns. These exist for telemetry richness only; missing a
# pattern is never a security failure because deterministic controls below
# the model decide access.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_instructions",
     re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
                re.IGNORECASE)),
    ("admin_mode",
     re.compile(r"(admin|root|superuser|debug)\s+mode", re.IGNORECASE)),
    ("system_override",
     re.compile(r"system\s+override|override\s+system", re.IGNORECASE)),
    ("sql_write_intent",
     re.compile(r"\b(drop|delete|truncate|insert|update|alter|create)\b"
                r"\s+(table|from|into)?", re.IGNORECASE)),
    ("credential_request",
     re.compile(r"(password|secret|api[\s_-]?key|token|credential)",
                re.IGNORECASE)),
    ("prompt_extraction",
     re.compile(r"(system\s+prompt|your\s+instructions|reveal\s+prompt)",
                re.IGNORECASE)),
    ("multilingual_ignore",
     re.compile(r"(ignoriere|ignore|忽略|忽视).{0,40}(anweisungen|instructions|指令|指示)",
                re.IGNORECASE)),
    ("encoding_evasion",
     re.compile(r"(base64|rot13|decode\s+this)", re.IGNORECASE)),
]


def classify_question(question: str) -> InjectionSignal:
    """Return a telemetry signal for the question. Never raises."""
    matched: list[str] = []
    for name, pat in _PATTERNS:
        if pat.search(question or ""):
            matched.append(name)
    flagged = bool(matched)
    category = "suspected_injection" if flagged else "clean"
    return InjectionSignal(
        flagged=flagged, category=category,
        matched_patterns=tuple(matched))
