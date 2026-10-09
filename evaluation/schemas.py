"""Versioned evaluation dataset loading and case schema (spec 004, T001).

Loads the physically separate development and held-out case files and
validates their structure deterministically. Development cases are the only
cases the optimizer may consume; held-out cases are never loaded for
optimization (FR-001, FR-009, SC-007).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_CASES_PATH = os.path.join(_DIR, "dev_cases.json")
CASES_PATH = os.path.join(_DIR, "cases.json")

SECURITY_PREFIX = "security"


@dataclass(frozen=True)
class EvalCase:
    """One labeled evaluation case with a stable unique ID."""

    id: str
    category: str
    question: str
    expected: dict = field(default_factory=dict)

    @property
    def is_security(self) -> bool:
        return self.category.startswith(SECURITY_PREFIX)


@dataclass(frozen=True)
class Dataset:
    """A versioned evaluation dataset."""

    version: int
    kind: str
    cases: tuple[EvalCase, ...]
    canary_values: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.cases)


def _load(path: str) -> Dataset:
    with open(path) as f:
        doc = json.load(f)
    cases = tuple(
        EvalCase(
            id=c["id"],
            category=c["category"],
            question=c["question"],
            expected=c.get("expected", {}),
        )
        for c in doc["cases"]
    )
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate case IDs in {path}")
    canaries = tuple((doc.get("canary_values") or {}).values())
    return Dataset(
        version=int(doc.get("version", 1)),
        kind=doc.get("kind", "unknown"),
        cases=cases,
        canary_values=canaries,
    )


def load_dev_cases(path: str = DEV_CASES_PATH) -> Dataset:
    """Load the development set (the only optimizer-eligible set)."""
    return _load(path)


def load_held_out_cases(path: str = CASES_PATH) -> Dataset:
    """Load the held-out evaluation set (never used for optimization)."""
    return _load(path)
