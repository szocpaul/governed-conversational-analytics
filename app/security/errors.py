"""Stable error categories for the conversational pipeline (T004).

Each error carries a stable machine-readable `code` and a `sanitized` message
that is safe to show to users: it never contains the private LLM endpoint,
credentials, full prompts, or internal host details.
"""
from __future__ import annotations

import re

# Patterns that must never appear in user-facing output.
_PRIVATE_PATTERNS = [
    re.compile(r"https?://[^\s]*tailee6bc1[^\s]*", re.IGNORECASE),
    re.compile(r"https?://\d{1,3}(\.\d{1,3}){3}(:\d+)?"),
    re.compile(r":\d{4,5}\b"),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
]


def _sanitize(message: str) -> str:
    out = message
    for pat in _PRIVATE_PATTERNS:
        out = pat.sub("[redacted]", out)
    return out


class PipelineError(Exception):
    """Base class for stable pipeline errors."""

    code = "error"

    def __init__(self, message: str):
        super().__init__(message)
        self.raw = message
        self.sanitized = _sanitize(message)


class AmbiguousQuestionError(PipelineError):
    code = "ambiguous"


class UnsupportedQuestionError(PipelineError):
    code = "unsupported"


class MalformedPlanError(PipelineError):
    code = "malformed_plan"


class ValidationError(PipelineError):
    code = "validation_error"


class DependencyError(PipelineError):
    code = "dependency_error"
