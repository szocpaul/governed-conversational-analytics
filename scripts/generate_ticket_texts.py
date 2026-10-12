#!/usr/bin/env python3
"""Generation CLI for synthetic ticket texts (feature 009, contract: generator-cli.md).

Offline, maintainer-run; NEVER part of the runtime query path and never
writes to the database. Reads the pinned data/raw/tickets.csv (SHA-256
verified against artifacts/import-manifest.json before any model call),
verifies the endpoint + exact pinned model ID (no fallback), generates the
three text fields per ticket in seeded batches of 5 via the typed DSPy
program in app/ai/text_generation.py, checkpoints after every accepted
batch (append-only JSONL, resume-by-default, --fresh to discard), and on
completion writes data/raw/tickets_texts.jsonl + data/raw/texts-manifest.json
(human_review.approved: false) and deletes the checkpoint.

Exit codes: 0 completed; 1 generation/validation failure; 2 endpoint/model
verification failure.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(REPO_ROOT, ".env"))

from app.ai.llm import LLMConfig, LLMEndpointError, configure_dspy, list_models  # noqa: E402
from app.ai.text_generation import PROMPT_VERSION, BatchGenerationError, TicketTextProgram  # noqa: E402

TICKETS_CSV = os.path.join(REPO_ROOT, "data", "raw", "tickets.csv")
IMPORT_MANIFEST = os.path.join(REPO_ROOT, "artifacts", "import-manifest.json")
DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "data", "raw", "tickets_texts.jsonl")
DEFAULT_MANIFEST_OUT = os.path.join(REPO_ROOT, "data", "raw", "texts-manifest.json")
CHECKPOINT_PATH = os.path.join(REPO_ROOT, "artifacts", "tickets_texts.checkpoint.jsonl")
PROGRAM_MODULE_PATH = os.path.join(REPO_ROOT, "app", "ai", "text_generation.py")

DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_RETRIES = 2
DEFAULT_SEED = 20261012
ARTIFACT_VERSION = "1"

ENTRY_KEYS = ("ticket_id", "short_description", "description", "resolution_notes")


class CheckpointError(RuntimeError):
    """Raised when the resume checkpoint is torn, corrupt, or inconsistent."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Checkpoint primitives (research R3)
# ---------------------------------------------------------------------------


def append_checkpoint(path: str, entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for entry in entries:
            obj = {key: entry[key] for key in ENTRY_KEYS}
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def load_checkpoint(path: str) -> dict[int, dict]:
    done: dict[int, dict] = {}
    if not os.path.exists(path):
        return done
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CheckpointError(
                    f"checkpoint {path}:{lineno} is torn or corrupt: {exc}") from exc
            if not isinstance(obj, dict) or any(k not in obj for k in ENTRY_KEYS):
                raise CheckpointError(
                    f"checkpoint {path}:{lineno} does not match the entry schema")
            tid = obj["ticket_id"]
            if not isinstance(tid, int) or isinstance(tid, bool):
                raise CheckpointError(
                    f"checkpoint {path}:{lineno}: ticket_id is not an integer")
            if tid in done:
                raise CheckpointError(
                    f"checkpoint {path}:{lineno}: duplicate ticket_id {tid}")
            done[tid] = obj
    return done


def discard_checkpoint(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def plan_remaining_batches(tickets: list[dict], done: dict[int, dict],
                           batch_size: int) -> list[list[dict]]:
    """Remaining batches in pinned tickets.csv order; unknown checkpoint ids fail."""
    known_ids = {int(t["ticket_id"]) for t in tickets}
    unknown = sorted(set(done) - known_ids)
    if unknown:
        raise CheckpointError(
            f"checkpoint contains ticket_ids absent from pinned tickets.csv: "
            f"{unknown[:5]}{'...' if len(unknown) > 5 else ''}")
    remaining = [t for t in tickets if int(t["ticket_id"]) not in done]
    return [remaining[i:i + batch_size] for i in range(0, len(remaining), batch_size)]


def finalize_artifact(output_path: str, entries: list[dict], *,
                      checkpoint_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        for entry in entries:
            obj = {key: entry[key] for key in ENTRY_KEYS}
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
    discard_checkpoint(checkpoint_path)


# ---------------------------------------------------------------------------
# Preflight + generation driver
# ---------------------------------------------------------------------------


def verify_pinned_tickets() -> None:
    with open(IMPORT_MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    expected = manifest["dataset"]["files"]["tickets.csv"]["sha256"]
    actual = sha256_file(TICKETS_CSV)
    if actual != expected:
        print(f"GENERATION FAILED: pinned tickets.csv SHA-256 mismatch "
              f"(expected {expected}, got {actual}); raw files are immutable",
              file=sys.stderr)
        raise SystemExit(1)


def verify_endpoint(config: LLMConfig) -> str:
    """Verify endpoint + exact pinned model ID; exit 2 on any failure."""
    try:
        ids = list_models(config)
    except LLMEndpointError as exc:
        print(f"ENDPOINT VERIFICATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if config.model not in ids:
        print(f"ENDPOINT VERIFICATION FAILED: requested model {config.model!r} "
              f"not present; available: {ids!r}. No fallback is allowed.",
              file=sys.stderr)
        raise SystemExit(2)
    return config.model


def load_tickets() -> list[dict]:
    with open(TICKETS_CSV, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--fresh", action="store_true",
                        help="discard any existing checkpoint and start over")
    parser.add_argument("--sample", type=int, default=None,
                        help="process only the first N tickets (dry-run support)")
    args = parser.parse_args(argv)

    if args.batch_size < 1:
        print("GENERATION FAILED: --batch-size must be >= 1", file=sys.stderr)
        return 1

    # 1. Pinned input verification BEFORE any model call.
    verify_pinned_tickets()

    # 2. Endpoint + exact pinned model ID verification (no fallback).
    config = LLMConfig.from_env()
    model_id = verify_endpoint(config)

    # 3. Seed acceptance probe: one seeded chat completion; a seed-parameter
    #    rejection stops the run loudly (exit 2).
    import httpx
    probe_payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
        "temperature": 0,
        "cache_prompt": False,
        "seed": args.seed,
    }
    try:
        resp = httpx.post(
            f"{config.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {config.api_key}",
                     "Content-Type": "application/json"},
            json=probe_payload, timeout=120.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"ENDPOINT VERIFICATION FAILED: seeded probe request failed: {exc}",
              file=sys.stderr)
        return 2
    print(f"endpoint verified: exact model ID loaded; seed {args.seed} accepted",
          file=sys.stderr)

    # 4. Checkpoint / resume setup.
    if args.fresh:
        if os.path.exists(CHECKPOINT_PATH):
            print("--fresh: discarding existing checkpoint", file=sys.stderr)
        discard_checkpoint(CHECKPOINT_PATH)
    try:
        done = load_checkpoint(CHECKPOINT_PATH)
    except CheckpointError as exc:
        print(f"GENERATION FAILED: {exc}", file=sys.stderr)
        return 1

    tickets = load_tickets()
    if args.sample is not None:
        tickets = tickets[: args.sample]
    try:
        batches = plan_remaining_batches(tickets, done, args.batch_size)
    except CheckpointError as exc:
        print(f"GENERATION FAILED: {exc}", file=sys.stderr)
        return 1
    total_batches = (len(tickets) + args.batch_size - 1) // args.batch_size
    if done:
        print(f"resuming: {len(done)} accepted ticket(s) loaded from checkpoint; "
              f"{len(batches)} of {total_batches} batches remaining", file=sys.stderr)

    # 5. Configure DSPy on the pinned endpoint and generate.
    import dspy
    lm = configure_dspy(config)
    lm.kwargs["seed"] = args.seed
    program = TicketTextProgram(max_retries=args.max_retries)

    accepted: dict[int, dict] = dict(done)
    retries_used = 0
    started = time.monotonic()
    completed_batches = total_batches - len(batches)
    for batch in batches:
        attempts = 1 + args.max_retries
        try:
            entries = program.generate_batch(batch)
        except BatchGenerationError as exc:
            print(f"GENERATION FAILED: {exc}", file=sys.stderr)
            print("checkpoint preserved for resume; artifact NOT written",
                  file=sys.stderr)
            return 1
        batch_entries = [
            {key: getattr(entry, key) for key in ENTRY_KEYS} for entry in entries
        ]
        append_checkpoint(CHECKPOINT_PATH, batch_entries)
        for entry in batch_entries:
            accepted[entry["ticket_id"]] = entry
        completed_batches += 1
        if completed_batches % 25 == 0 or completed_batches == total_batches:
            elapsed = time.monotonic() - started
            print(f"batch {completed_batches}/{total_batches} "
                  f"({len(accepted)}/{len(tickets)} tickets, {elapsed:.0f}s)",
                  file=sys.stderr)

    # 6. Finalize: artifact in pinned CSV order, then manifest, then delete checkpoint.
    ordered_entries = [accepted[int(t["ticket_id"])] for t in tickets]
    finalize_artifact(args.output, ordered_entries, checkpoint_path=CHECKPOINT_PATH)
    runtime_s = time.monotonic() - started
    print(f"artifact written: {args.output} ({len(ordered_entries)} entries, "
          f"{runtime_s:.0f}s)", file=sys.stderr)

    if args.sample is None:
        artifact_sha = sha256_file(args.output)
        manifest = {
            "artifact_version": ARTIFACT_VERSION,
            "artifact_path": os.path.relpath(args.output, REPO_ROOT),
            "artifact_sha256": artifact_sha,
            "row_count": len(ordered_entries),
            "model_id": model_id,
            "llama_cpp_version": "unreported",
            "temperature": 0,
            "seed": args.seed,
            "cache": False,
            "prompt_version": PROMPT_VERSION,
            "dspy_version": dspy.__version__,
            "generator": {
                "script": "scripts/generate_ticket_texts.py",
                "script_sha256": sha256_file(os.path.abspath(__file__)),
                "program_module": "app/ai/text_generation.py",
                "program_module_sha256": sha256_file(PROGRAM_MODULE_PATH),
            },
            "batch_config": {
                "batch_size": args.batch_size,
                "max_retries": args.max_retries,
                "batches": total_batches,
                "retries_used": retries_used,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "validation": {
                "suite_passed": False,
                "validated_at": None,
                "checks": [],
            },
            "human_review": {
                "approved": False,
                "reviewer": None,
                "reviewed_at": None,
                "sample_notes": None,
            },
        }
        with open(DEFAULT_MANIFEST_OUT, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        print(f"manifest written: {DEFAULT_MANIFEST_OUT} "
              f"(human_review.approved=false)", file=sys.stderr)
    else:
        print(f"sample run ({len(ordered_entries)} tickets): no manifest written",
              file=sys.stderr)
    print(f"retries used: {retries_used}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
