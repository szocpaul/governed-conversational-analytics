"""Stable error categories for the conversational pipeline (T004).

Each error carries a stable machine-readable `code` and a `sanitized` message
that is safe to show to users: it never contains the private LLM endpoint,
credentials, full prompts, or internal host details.
"""
from __future__ import annotations

from app.security.redaction import redact as _sanitize


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
