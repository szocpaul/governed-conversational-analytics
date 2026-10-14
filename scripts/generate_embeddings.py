#!/usr/bin/env python3
"""Embedding generator CLI (feature 010, contract: embedder-cli.md).

Offline, maintainer-run; NEVER part of the runtime query path and never
writes to the database. Verifies the pinned inputs BEFORE any embedding call
(data/raw/tickets_texts.jsonl SHA-256 against data/raw/texts-manifest.json;
data/raw/tickets.csv SHA-256 against artifacts/import-manifest.json), verifies
the embedding endpoint + exact pinned model ID (no fallback), embeds tickets
in pinned tickets.csv order with bounded retries, checkpoints after every
accepted ticket (append-only JSONL, resume-by-default, --fresh to discard),
and on completion writes data/raw/tickets_embeddings.jsonl +
data/raw/embeddings-manifest.json and deletes the checkpoint.

Exit codes: 0 completed; 1 embedding/validation failure; 2 endpoint/model
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

from app.ai.embeddings import (  # noqa: E402
    EMBEDDING_DIMENSION,
    EmbeddingConfig,
    EmbeddingError,
    EmbeddingProgram,
    PINNED_MODEL_ID,
)

TICKETS_CSV = os.path.join(REPO_ROOT, "data", "raw", "tickets.csv")
TEXTS_ARTIFACT = os.path.join(REPO_ROOT, "data", "raw", "tickets_texts.jsonl")
TEXTS_MANIFEST = os.path.join(REPO_ROOT, "data", "raw", "texts-manifest.json")
IMPORT_MANIFEST = os.path.join(REPO_ROOT, "artifacts", "import-manifest.json")
DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "data", "raw", "tickets_embeddings.jsonl")
DEFAULT_MANIFEST_OUT = os.path.join(REPO_ROOT, "data", "raw", "embeddings-manifest.json")
CHECKPOINT_PATH = os.path.join(REPO_ROOT, "artifacts", "tickets_embeddings.checkpoint.jsonl")
PROGRAM_MODULE_PATH = os.path.join(REPO_ROOT, "app", "ai", "embeddings.py")

DEFAULT_MAX_RETRIES = 2
ARTIFACT_VERSION = "1"
QUANTIZATION = "Q8_0"
SOURCE_GGUF = "ggml-org/embeddinggemma-2-GGUF"
LICENSE = "Apache-2.0"

ENTRY_KEYS = ("ticket_id", "embedding")


class CheckpointError(RuntimeError):
    """Raised when the resume checkpoint is torn, corrupt, or inconsistent."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Checkpoint primitives (research R4)
# ---------------------------------------------------------------------------


def append_checkpoint(path: str, entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for entry in entries:
            obj = {key: entry[key] for key in ENTRY_KEYS}
            fh.write(json.dumps(obj) + "\n")
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


def plan_remaining(tickets: list[dict], done: dict[int, dict]) -> list[dict]:
    """Remaining tickets in pinned tickets.csv order; unknown ids fail loudly."""
    known_ids = {int(t["ticket_id"]) for t in tickets}
    unknown = sorted(set(done) - known_ids)
    if unknown:
        raise CheckpointError(
            f"checkpoint contains ticket_ids absent from pinned tickets.csv: "
            f"{unknown[:5]}{'...' if len(unknown) > 5 else ''}")
    return [t for t in tickets if int(t["ticket_id"]) not in done]


def finalize_artifact(output_path: str, entries: list[dict], *,
                      checkpoint_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        for entry in entries:
            obj = {key: entry[key] for key in ENTRY_KEYS}
            fh.write(json.dumps(obj) + "\n")
    discard_checkpoint(checkpoint_path)


# ---------------------------------------------------------------------------
# Pinned-input + endpoint verification
# ---------------------------------------------------------------------------


def verify_pinned_inputs() -> None:
    """Verify pinned tickets.csv and tickets_texts.jsonl SHA-256 (exit 1)."""
    with open(IMPORT_MANIFEST, encoding="utf-8") as fh:
        import_manifest = json.load(fh)
    expected_csv = import_manifest["dataset"]["files"]["tickets.csv"]["sha256"]
    actual_csv = sha256_file(TICKETS_CSV)
    if actual_csv != expected_csv:
        print(f"GENERATION FAILED: pinned tickets.csv SHA-256 mismatch "
              f"(expected {expected_csv}, got {actual_csv}); raw files are immutable",
              file=sys.stderr)
        raise SystemExit(1)
    with open(TEXTS_MANIFEST, encoding="utf-8") as fh:
        texts_manifest = json.load(fh)
    expected_texts = texts_manifest["artifact_sha256"]
    actual_texts = sha256_file(TEXTS_ARTIFACT)
    if actual_texts != expected_texts:
        print(f"GENERATION FAILED: pinned tickets_texts.jsonl SHA-256 mismatch "
              f"(expected {expected_texts}, got {actual_texts}); the pinned text "
              f"artifact is immutable", file=sys.stderr)
        raise SystemExit(1)


def verify_endpoint(config: EmbeddingConfig) -> str:
    """Verify endpoint + exact pinned model ID + embeddings route (exit 2)."""
    import httpx
    if not config.base_url:
        print("ENDPOINT VERIFICATION FAILED: EMBED_BASE_URL is not configured",
              file=sys.stderr)
        raise SystemExit(2)
    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        resp = httpx.get(f"{config.base_url}/models", headers=headers, timeout=30.0)
        resp.raise_for_status()
        ids = [m.get("id") for m in resp.json().get("data", []) if m.get("id")]
    except Exception as exc:  # noqa: BLE001
        print(f"ENDPOINT VERIFICATION FAILED: /models request failed: {exc}",
              file=sys.stderr)
        raise SystemExit(2)
    if config.model not in ids:
        print(f"ENDPOINT VERIFICATION FAILED: requested model {config.model!r} "
              f"not present; available: {ids!r}. No fallback is allowed.",
              file=sys.stderr)
        raise SystemExit(2)
    # Embeddings route support: one deterministic smoke request.
    try:
        resp = httpx.post(
            f"{config.base_url}/embeddings",
            headers={**headers, "Content-Type": "application/json"},
            json={"model": config.model, "input": "endpoint verification"},
            timeout=60.0)
        resp.raise_for_status()
        vec = resp.json()["data"][0]["embedding"]
        if len(vec) != EMBEDDING_DIMENSION:
            raise ValueError(f"dimension {len(vec)} != {EMBEDDING_DIMENSION}")
    except Exception as exc:  # noqa: BLE001
        print(f"ENDPOINT VERIFICATION FAILED: embeddings route unsupported or "
              f"invalid response: {exc}", file=sys.stderr)
        raise SystemExit(2)
    return config.model


def load_tickets() -> list[dict]:
    with open(TICKETS_CSV, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_texts() -> dict[int, dict]:
    entries = {}
    with open(TEXTS_ARTIFACT, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            obj = json.loads(line)
            entries[int(obj["ticket_id"])] = obj
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--fresh", action="store_true",
                        help="discard any existing checkpoint and start over")
    parser.add_argument("--sample", type=int, default=None,
                        help="embed only the first N tickets (dry-run support)")
    args = parser.parse_args(argv)

    # 1. Pinned input verification BEFORE any embedding call.
    verify_pinned_inputs()

    # 2. Endpoint + exact pinned model ID + route verification (no fallback).
    config = EmbeddingConfig.from_env()
    model_id = verify_endpoint(config)
    print("endpoint verified: exact pinned embedding model ID loaded; "
          "embeddings route supported", file=sys.stderr)

    # 3. Checkpoint / resume setup.
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
    texts = load_texts()
    try:
        remaining = plan_remaining(tickets, done)
    except CheckpointError as exc:
        print(f"GENERATION FAILED: {exc}", file=sys.stderr)
        return 1
    if done:
        print(f"resuming: {len(done)} accepted ticket(s) loaded from checkpoint; "
              f"{len(remaining)} of {len(tickets)} tickets remaining", file=sys.stderr)

    # 4. Embed the remaining tickets in pinned order.
    program = EmbeddingProgram(model=model_id, config=config,
                               max_retries=args.max_retries)
    accepted: dict[int, dict] = dict(done)
    retries_used = 0
    started = time.monotonic()
    completed = len(tickets) - len(remaining)
    for ticket in remaining:
        tid = int(ticket["ticket_id"])
        text_entry = texts.get(tid)
        if text_entry is None:
            print(f"GENERATION FAILED: ticket {tid} has no pinned text entry",
                  file=sys.stderr)
            return 1
        try:
            vector = program.embed_ticket(text_entry)
        except EmbeddingError as exc:
            print(f"GENERATION FAILED: {exc}", file=sys.stderr)
            print("checkpoint preserved for resume; artifact NOT written",
                  file=sys.stderr)
            return 1
        entry = {"ticket_id": tid, "embedding": vector}
        append_checkpoint(CHECKPOINT_PATH, [entry])
        accepted[tid] = entry
        completed += 1
        if completed % 100 == 0 or completed == len(tickets):
            elapsed = time.monotonic() - started
            print(f"ticket {completed}/{len(tickets)} ({elapsed:.0f}s)",
                  file=sys.stderr)

    # 5. Finalize: artifact in pinned CSV order, then manifest, then delete checkpoint.
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
            "quantization": QUANTIZATION,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "source_gguf": SOURCE_GGUF,
            "source_gguf_sha256": os.environ.get("EMBED_SOURCE_GGUF_SHA256", "unrecorded"),
            "license": LICENSE,
            "generator": {
                "script": "scripts/generate_embeddings.py",
                "script_sha256": sha256_file(os.path.abspath(__file__)),
                "program_module": "app/ai/embeddings.py",
                "program_module_sha256": sha256_file(PROGRAM_MODULE_PATH),
            },
            "run_config": {
                "max_retries": args.max_retries,
                "checkpoint_path": os.path.relpath(CHECKPOINT_PATH, REPO_ROOT),
                "retries_used": retries_used,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "validation": {
                "suite_passed": False,
                "validated_at": None,
                "checks": [],
            },
        }
        with open(DEFAULT_MANIFEST_OUT, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        print(f"manifest written: {DEFAULT_MANIFEST_OUT}", file=sys.stderr)
    else:
        print(f"sample run ({len(ordered_entries)} tickets): no manifest written",
              file=sys.stderr)
    print(f"retries used: {retries_used}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
