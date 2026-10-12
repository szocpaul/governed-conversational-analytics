# Contract: Artifact Schemas (texts-manifest.json + import-manifest extension)

## 1. `data/raw/texts-manifest.json` (new, committed)

```json
{
  "artifact_version": "1",
  "artifact_path": "data/raw/tickets_texts.jsonl",
  "artifact_sha256": "<64-hex>",
  "row_count": 2057,
  "model_id": "<exact pinned API model ID>",
  "llama_cpp_version": "<server version or 'unreported'>",
  "temperature": 0,
  "seed": 20261012,
  "cache": false,
  "prompt_version": "1",
  "dspy_version": "3.4.0",
  "generator": {
    "script": "scripts/generate_ticket_texts.py",
    "script_sha256": "<64-hex>",
    "program_module": "app/ai/text_generation.py",
    "program_module_sha256": "<64-hex>"
  },
  "batch_config": {
    "batch_size": 5,
    "max_retries": 2,
    "batches": 412,
    "retries_used": 0
  },
  "created_at": "<ISO-8601 UTC>",
  "validation": {
    "suite_passed": true,
    "validated_at": "<ISO-8601 UTC>",
    "checks": ["schema+coverage", "non-empty", "lengths", "english-only",
               "secrets-pii-scan", "category-consistency", "null-rule"]
  },
  "human_review": {
    "approved": false,
    "reviewer": null,
    "reviewed_at": null,
    "sample_notes": null
  }
}
```

Rules:
- `human_review` is set to `approved: true` (with reviewer, reviewed_at,
  sample_notes) ONLY by the human reviewer after per-category sample review
  (MANUAL GATE). Agents/scripts must never set it.
- Any regeneration bumps `artifact_version`, regenerates ALL fields, and
  resets `human_review.approved` to `false`.

## 2. `artifacts/import-manifest.json` extension (additive)

One NEW top-level key; `dataset`, `import`, `notes` unchanged
(feature-001 tests keep passing, research R8):

```json
"generated_texts": {
  "artifact_path": "data/raw/tickets_texts.jsonl",
  "artifact_sha256": "<64-hex>",
  "texts_manifest_path": "data/raw/texts-manifest.json",
  "texts_manifest_sha256": "<64-hex>",
  "artifact_version": "1",
  "row_count": 2057,
  "human_review": {"approved": true, "reviewer": "<name>",
                   "reviewed_at": "<ISO-8601>"},
  "imported_at": "<ISO-8601 UTC>"
}
```

Import preconditions enforced by `scripts/import_dataset.py`:
artifact SHA-256 == manifest record; coverage == pinned 2057;
`human_review.approved == true`; NULL rule holds. Failure = full rollback,
non-zero exit.

## 3. Artifact line schema (`tickets_texts.jsonl` and checkpoint)

```json
{"ticket_id": 847201,
 "short_description": "<1 sentence, <=100 chars>",
 "description": "<2-4 sentences, <=600 chars>",
 "resolution_notes": "<1-3 sentences, <=450 chars> or null"}
```

All four keys always present; `resolution_notes` is JSON `null` exactly for
open tickets.
