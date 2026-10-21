---
type: C4 Component
title: Cross-version report
status: stable
groma:
  id: cross-version-report
  parent: evaluation
  code:
    - scanner: python
      file: evaluation/cross_version_report.py
  group: Evaluation commands
description: Cross-version comparison report used by the DSPy upgrade gate.
---

`evaluation/cross_version_report.py` compares the pre-upgrade and post-upgrade evaluation artifacts and writes artifacts/cross-version-006.json. It reports whether the DSPy version change moved any quality metric, which is what the upgrade gate reads to show that the new version is not a quality regression.
