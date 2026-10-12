"""Typed DSPy program for governed synthetic ticket-text generation (feature 009).

Offline build-time module ONLY — never imported by the runtime query path.
The pinned local model generates three synthetic text fields per ITSM ticket
(short_description, description, resolution_notes) from the ticket's
structured columns, in batches, as strict JSON validated by pydantic.

House discipline (app/ai/signatures.py): the instruction lives in the
Signature docstring; PROMPT_VERSION is bumped on any instruction/field
change and recorded in the provenance manifest. No hard-coded prompt
strings outside the signature.

Zero-tolerance acceptance per batch (research R4): the adapter/pydantic
parse must succeed, the entry ticket_id set must equal the input set
exactly (no missing, no extra, no duplicates), and per-entry rules must
hold (non-empty strings, resolution_notes null iff the ticket is open).
Failures get bounded identical-request retries, then BatchGenerationError.
"""
from __future__ import annotations

import json

import dspy
import pydantic

# Versioned prompt asset: bump on ANY change to the GenerateTicketTexts
# docstring or field descriptions. Recorded in data/raw/texts-manifest.json.
PROMPT_VERSION = "1"


class TicketTextEntry(pydantic.BaseModel):
    """One generated text record for one ticket (strict schema)."""

    model_config = pydantic.ConfigDict(strict=True)

    ticket_id: int
    short_description: str
    description: str
    resolution_notes: str | None  # key always present; null for open tickets


class GenerateTicketTexts(dspy.Signature):
    """Generate synthetic English free-text fields for a batch of ITSM tickets.

    You receive tickets_json: a JSON array of ticket context objects, each
    with the ticket's structured columns (ticket_id, category, sub_category,
    priority, created_at, is_legacy, sla breach flags, resolution time,
    reopened flags, csat_score, and is_open). Write realistic synthetic
    helpdesk text for EACH ticket, built ONLY from these structured fields.
    Never invent personal names, email addresses, phone numbers, IP
    addresses, credentials, or real company names.

    Output entries: a JSON array with EXACTLY one entry per input ticket, in
    the SAME order, with the SAME ticket_id. Each entry has exactly these
    four keys:

    - ticket_id: the input ticket's id (integer, copied exactly).
    - short_description: exactly ONE complete sentence, at most 100
      characters (target about 80), naming the problem and its key detail,
      consistent with the ticket's category and sub_category. Write a full
      sentence with articles (the/a/an), never a headline-style fragment:
      e.g. "The sync job fails every night after the update."
    - description: 2-4 sentences, at most 600 characters total, giving
      reporter context, scope, trigger, and impact, with wording
      appropriate to the ticket's priority (urgent and business-critical
      for P1, calm and minor for P4).
    - resolution_notes: null when the ticket is open (is_open true);
      otherwise 1-3 sentences, at most 450 characters total, stating the
      root cause, the fix applied, and the verification performed.

    Write plain English sentences only: no abbreviations containing
    periods, no bullet lists, no markdown, no placeholders, no template
    braces. Every sentence ends with '.', '!' or '?'.
    """

    tickets_json: str = dspy.InputField(
        desc="JSON array of ticket context objects (ticket_id, category, "
             "sub_category, priority, sla flags, resolution time, reopened, "
             "is_open, ...)")
    entries: list[TicketTextEntry] = dspy.OutputField(
        desc="JSON array with exactly one entry per input ticket, same "
             "order, same ticket_ids; resolution_notes is null exactly for "
             "open tickets")


class BatchGenerationError(RuntimeError):
    """Raised when a batch fails validation after all bounded retries."""


def ticket_context(ticket: dict) -> dict:
    """Build the compact prompt-context object for one tickets.csv row.

    Only structured columns are used (FR-008); never free text.
    """
    if "is_open" in ticket:
        is_open = bool(ticket["is_open"])
    else:
        is_open = not str(ticket.get("closed_at", "")).strip()
    context = {"ticket_id": int(ticket["ticket_id"]), "is_open": is_open}
    for key in ("category", "sub_category", "priority", "created_at", "is_legacy",
                "category_mismatch", "ttfr_hours", "resolution_hours",
                "response_breached", "resolution_breached", "is_reopened",
                "is_reopen_child", "is_incident_ticket", "csat_score"):
        if key in ticket:
            context[key] = ticket[key]
    return context


class TicketTextProgram(dspy.Module):
    """Batch text-generation program with zero-tolerance acceptance.

    Runs dspy.Predict(GenerateTicketTexts) under an explicit
    dspy.JSONAdapter() so the typed pydantic output is requested as strict
    JSON. Per batch: parse must succeed, the ticket_id set must match the
    input exactly, and per-entry rules must hold; otherwise the identical
    request is retried up to max_retries times, then BatchGenerationError.
    """

    def __init__(self, max_retries: int = 2):
        super().__init__()
        self.max_retries = max_retries
        self.generate = dspy.Predict(GenerateTicketTexts)

    def _accept(self, batch: list[dict], entries: list[TicketTextEntry]) -> list[TicketTextEntry]:
        """Zero-tolerance per-batch acceptance (research R4). Raises ValueError."""
        expected_ids = [int(t["ticket_id"]) for t in batch]
        got_ids = [e.ticket_id for e in entries]
        if sorted(got_ids) != sorted(expected_ids):
            missing = sorted(set(expected_ids) - set(got_ids))
            extra = sorted(set(got_ids) - set(expected_ids))
            raise ValueError(
                f"ticket_id set mismatch: missing={missing} extra={extra}")
        if len(set(got_ids)) != len(got_ids):
            raise ValueError("duplicate ticket_id in model output")
        open_by_id = {
            int(t["ticket_id"]): (bool(t["is_open"]) if "is_open" in t
                                  else not str(t.get("closed_at", "")).strip())
            for t in batch
        }
        for entry in entries:
            for field in ("short_description", "description"):
                value = getattr(entry, field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"ticket {entry.ticket_id}: empty {field}")
            if entry.resolution_notes is not None and not entry.resolution_notes.strip():
                raise ValueError(
                    f"ticket {entry.ticket_id}: empty resolution_notes")
            if open_by_id[entry.ticket_id] and entry.resolution_notes is not None:
                raise ValueError(
                    f"ticket {entry.ticket_id}: resolution_notes present for open ticket")
            if not open_by_id[entry.ticket_id] and entry.resolution_notes is None:
                raise ValueError(
                    f"ticket {entry.ticket_id}: resolution_notes null for closed ticket")
        by_id = {e.ticket_id: e for e in entries}
        return [by_id[tid] for tid in expected_ids]

    def generate_batch(self, batch: list[dict]) -> list[TicketTextEntry]:
        """Generate and strictly validate one batch. Retries, then raises."""
        tickets_json = json.dumps([ticket_context(t) for t in batch])
        last_error: Exception | None = None
        for attempt in range(1 + self.max_retries):
            try:
                with dspy.context(adapter=dspy.JSONAdapter()):
                    pred = self.generate(tickets_json=tickets_json)
                return self._accept(batch, list(pred.entries))
            except Exception as exc:  # noqa: BLE001 - normalized below
                last_error = exc
        ids = [int(t["ticket_id"]) for t in batch]
        raise BatchGenerationError(
            f"batch {ids} failed after {1 + self.max_retries} attempts: "
            f"{type(last_error).__name__}: {last_error}") from last_error

    def forward(self, batch: list[dict]) -> dspy.Prediction:
        return dspy.Prediction(entries=self.generate_batch(batch))
