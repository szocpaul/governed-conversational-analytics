"""Evaluation runner metadata tests (feature 006, T010).

The baseline/evaluation artifact metadata must record the DSPy version and
the Python version so a measured run proves which runtime produced it
(contract: artifacts/baseline.json records DSPy 3.4.0 and Python version).
"""
from __future__ import annotations

import platform

import dspy

from evaluation import run


def test_collect_metadata_records_dspy_and_python_version():
    md = run.collect_metadata(cache=False)
    assert md["dspy_version"] == dspy.__version__
    assert md["python_version"] == platform.python_version()
