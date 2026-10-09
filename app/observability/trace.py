"""Sanitized execution tracing (T006).

Records pipeline events with sanitized details. All sanitization delegates
to app.security.redaction.redact so that canaries, credentials, private
endpoint URLs, bearer tokens, and IP:port pairs are redacted before storage
and traces are safe to surface to users (FR-006).
"""
from __future__ import annotations

import time

from app.api.schemas import TraceEvent
from app.security.redaction import redact as _sanitize


class Trace:
    """A sanitized, ordered execution trace with latency."""

    def __init__(self) -> None:
        self._start = time.monotonic()
        self._events: list[TraceEvent] = []

    def add(self, event: str, detail: str | None = None) -> None:
        self._events.append(
            TraceEvent(event=event,
                       detail=_sanitize(detail) if detail else None))

    @property
    def events(self) -> list[TraceEvent]:
        return list(self._events)

    def latency_ms(self) -> float:
        return round((time.monotonic() - self._start) * 1000, 2)
