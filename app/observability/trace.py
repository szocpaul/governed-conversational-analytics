"""Sanitized execution tracing (T006).

Records pipeline events with sanitized details. Private endpoint URLs,
credentials, bearer tokens, and IP:port pairs are redacted before storage so
traces are safe to surface to users.
"""
from __future__ import annotations

import re
import time

from app.api.schemas import TraceEvent

_PATTERNS = [
    re.compile(r"https?://[^\s]*tailee6bc1[^\s]*", re.IGNORECASE),
    re.compile(r"https?://\d{1,3}(\.\d{1,3}){3}(:\d+)?"),
    re.compile(r":\d{4,5}\b"),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
]


def _sanitize(text: str) -> str:
    out = text
    for pat in _PATTERNS:
        out = pat.sub("[redacted]", out)
    return out


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
