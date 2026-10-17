---
type: C4 Container
title: BootstrapFewShot optimization
status: stable
groma:
  id: script-optimization
  parent: governed-conversational-analytics
description: Bounded DSPy BootstrapFewShot optimization on development cases only.
---

Runs the approved dspy.BootstrapFewShot optimizer with the bounded configuration (metric_threshold 1.0, max_bootstrapped_demos 4, max_labeled_demos 4, max_rounds 1, max_errors 3). Consumes ONLY development case IDs; held-out IDs are guarded against leakage. The binary metric returns 1.0 only when every mandatory check passes (structured output validates, request is read-only and policy-allowed, execution succeeds, normalized result matches, no prohibited effect or disclosure). Saves the optimized program and a run artifact with provenance. GEPA, MIPROv2, SIMBA, and fine-tuning are prohibited.
