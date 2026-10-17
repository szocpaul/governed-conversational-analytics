---
type: C4 Container
title: Evaluation toolkit
status: draft
groma:
  id: evaluation
  parent: governed-conversational-analytics
description: Held-out evaluation runner, deterministic metrics, and regression comparison gate for measuring pipeline quality and security.
---

The evaluation toolkit (evaluation/) measures the live governed pipeline over physically separated dev and held-out case sets. The runner (evaluation/run.py) executes every held-out case with temperature 0 and cache disabled, takes a PostgreSQL snapshot before and after each case to detect prohibited effects, and writes a versioned artifact with per-case results and separately computed deterministic metrics. The metrics module (evaluation/metrics.py) computes structural validity, execution accuracy, routing accuracy, count accuracy, and security metrics — all deterministic and model-free. The comparison gate (evaluation/compare.py) returns a non-zero exit code on quality-threshold failure, execution-accuracy degradation, any prohibited effect, or any unauthorized disclosure; latency is observational only.
