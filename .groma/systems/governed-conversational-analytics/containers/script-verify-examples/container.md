---
type: C4 Container
title: Example verification
status: stable
groma:
  id: script-verify-examples
  parent: governed-conversational-analytics
description: Verifies that the curated demo UI example questions produce correct, grounded answers.
---

Runs each of the 26 curated example questions (from app/web/examples.json) through the live governed pipeline and checks that the answer is correct and grounded. Writes a verification artifact (artifacts/examples-verification.json). Used for the feature 008 (Query Discovery UI) gate.
