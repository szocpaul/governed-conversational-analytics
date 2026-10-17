---
type: C4 Component
title: Cross-version report (component)
status: stable
groma:
  id: cross-version-report
  parent: script-cross-version-report
  code:
    - scanner: python
      file: evaluation/cross_version_report.py
  group: Evaluation & tuning
description: Cross-version comparison report generator.
---

evaluation/cross_version_report.py. Compares pre-upgrade and post-upgrade evaluation artifacts. Used for the feature 006 gate.
