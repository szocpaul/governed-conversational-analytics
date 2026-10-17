---
type: C4 Container
title: Validate ticket texts
status: stable
groma:
  id: script-validate-ticket-texts
  parent: governed-conversational-analytics
description: Deterministic offline validation suite for the generated ticket texts.
---

Validates the pinned ticket-texts artifact: schema (required fields, types), coverage (every ticket present), length limits (short_description <= 100, description <= 600, resolution_notes <= 450), language (English), category consistency, and the NULL rule (resolution_notes is null exactly for open tickets). Human data-quality review is performed per category before import.
