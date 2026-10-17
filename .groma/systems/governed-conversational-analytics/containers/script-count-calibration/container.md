---
type: C4 Container
title: Count threshold calibration
status: stable
groma:
  id: script-count-calibration
  parent: governed-conversational-analytics
description: Deterministic calibration of the semantic-match threshold for count over content.
---

Runs calibrate_threshold() (app/ai/count_calibration.py): a deterministic distance sweep over the development count cases only. For a grid of candidate cosine-distance thresholds, each dev count question is embedded and the governed hybrid count is computed; the threshold maximizing dev exact-count accuracy is chosen. Writes a versioned count-threshold.json artifact with provenance. Consumes development cases only (zero held-out leakage).
