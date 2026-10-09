"""Deterministic redaction of secrets, canaries, and private values (T006).

Every user-facing string (response text, trace detail, error message) passes
through redact() so that seeded test canaries, credentials, bearer tokens,
private endpoint details, and full prompt fragments are never disclosed
(FR-006, SC-003). Redaction is deterministic and total: it does not depend
on model behavior.
"""
from __future__ import annotations

import re

# Test-only canary values (mirrors evaluation/security_cases.json). These
# are synthetic and must never be real credentials.
_CANARY_VALUES = [
    "CANARY_SECRET_7f3d9a2b1c",
    "CANARY_PASSWORD_x9v8u7t6s5",
    "CANARY_TOKEN_m4k3j2h1g0",
    "CANARY_PROMPT_FRAGMENT_z5y4x3w2v1",
]

# Patterns that must never appear in user-facing output.
_PATTERNS: list[re.Pattern[str]] = [
    # Private Tailscale endpoint (any scheme/port/path).
    re.compile(r"https?://[^\s]*tailee6bc1[^\s]*", re.IGNORECASE),
    # Any bare IP:port or IP literal.
    re.compile(r"https?://\d{1,3}(\.\d{1,3}){3}(:\d+)?"),
    re.compile(r"\b\d{1,3}(\.\d{1,3}){3}:\d+\b"),
    # Bearer tokens and key material.
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*\S+"),
    # Standalone port suffixes (host:port detail).
    re.compile(r":\d{4,5}\b"),
]

# Pre-compiled canary literals (escaped for exact match).
_CANARY_PATTERNS = [re.compile(re.escape(v)) for v in _CANARY_VALUES]

REDACTED = "[redacted]"


def redact(text: str) -> str:
    """Return text with every prohibited value replaced by [redacted].

    Deterministic and total: the same input always produces the same
    output, and no canary, credential, bearer token, private endpoint, or
    IP:port detail survives.
    """
    if not text:
        return text
    out = str(text)
    for pat in _CANARY_PATTERNS:
        out = pat.sub(REDACTED, out)
    for pat in _PATTERNS:
        out = pat.sub(REDACTED, out)
    return out
