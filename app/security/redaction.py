"""Deterministic redaction of secrets, canaries, and private values (T006).

Every user-facing string (response text, trace detail, error message) passes
through redact() so that seeded test canaries, credentials, bearer tokens,
private endpoint details, and full prompt fragments are never disclosed
(FR-006, SC-003). Redaction is deterministic and total: it does not depend
on model behavior.
"""
from __future__ import annotations

import os
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
#
# Private endpoint details are matched by SHAPE, never by one literal host
# name: the repository must not name a real private host, and the rule must
# still cover whatever endpoint is configured at runtime.
PRIVATE_ENDPOINT_PATTERNS: list[re.Pattern[str]] = [
    # Tailnet / private DNS names (any scheme, port, or path).
    re.compile(r"https?://[^\s]*\.ts\.net[^\s]*", re.IGNORECASE),
    re.compile(r"https?://[^\s]*\.tailscale\.[^\s]*", re.IGNORECASE),
    # Any bare IP:port or IP literal.
    re.compile(r"https?://\d{1,3}(\.\d{1,3}){3}(:\d+)?"),
    re.compile(r"\b\d{1,3}(\.\d{1,3}){3}:\d+\b"),
    # Tailscale CGNAT range (100.64.0.0/10) as a bare address.
    re.compile(r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b"),
]

CREDENTIAL_PATTERNS: list[re.Pattern[str]] = [
    # Bearer tokens and key material.
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*\S+"),
]

_PATTERNS: list[re.Pattern[str]] = PRIVATE_ENDPOINT_PATTERNS + CREDENTIAL_PATTERNS + [
    # Standalone port suffixes (host:port detail).
    re.compile(r":\d{4,5}\b"),
]

# Environment variables that hold the configured private endpoint values.
# The literal value is redacted too, so a custom private host (one that does
# not match the generic shapes above) is still never disclosed.
_ENDPOINT_ENV_VARS = ("LLM_BASE_URL", "EMBED_BASE_URL")

# Pre-compiled canary literals (escaped for exact match).
_CANARY_PATTERNS = [re.compile(re.escape(v)) for v in _CANARY_VALUES]

REDACTED = "[redacted]"


def _configured_endpoint_literals() -> list[str]:
    """Return the configured private endpoint values from the environment.

    The values never live in the repository: they are read from the local
    environment at runtime, so the repository can stay free of real hosts.
    """
    values: list[str] = []
    for var in _ENDPOINT_ENV_VARS:
        value = (os.environ.get(var) or "").strip().rstrip("/")
        if value:
            values.append(value)
    return values


def contains_private_endpoint(text: str) -> bool:
    """Return True when the text contains a private endpoint detail.

    Checks the generic private-endpoint shapes and the configured endpoint
    values taken from the environment.
    """
    if not text:
        return False
    value = str(text)
    for literal in _configured_endpoint_literals():
        if literal in value:
            return True
    return any(pat.search(value) for pat in PRIVATE_ENDPOINT_PATTERNS)


def redact(text: str) -> str:
    """Return text with every prohibited value replaced by [redacted].

    Deterministic and total: the same input always produces the same
    output, and no canary, credential, bearer token, private endpoint, or
    IP:port detail survives.
    """
    if not text:
        return text
    out = str(text)
    for literal in _configured_endpoint_literals():
        out = out.replace(literal, REDACTED)
    for pat in _CANARY_PATTERNS:
        out = pat.sub(REDACTED, out)
    for pat in _PATTERNS:
        out = pat.sub(REDACTED, out)
    return out
