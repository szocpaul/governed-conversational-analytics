# Contract: Artifact Schemas (embeddings-manifest.json + import-manifest extension)

## 1. `data/raw/embeddings-manifest.json` (new, committed)

```json
{
  "artifact_version": "1",
  "artifact_path": "data/raw/tickets_embeddings.jsonl",
  "artifact_sha256": "<64-hex>",
  "row_count": 2057,
  "model_id": "models\\embeddinggemma-2-Q8_0.gguf",
  "quantization": "Q8_0",
  "embedding_dimension": 768,
  "source_gguf": "ggml-org/embeddinggemma-2-GGUF",
  "source_gguf_sha256": "<64-hex>",
  "license": "Apache-2.0",
  "generator": {
    "script": "scripts/generate_embeddings.py",
    "script_sha256": "<64-hex>",
    "program_module": "app/ai/embeddings.py",
    "program_module_sha256": "<64-hex>"
  },
  "run_config": {
    "max_retries": 2,
    "checkpoint_path": "artifacts/tickets_embeddings.checkpoint.jsonl",
    "retries_used": 0
  },
  "created_at": "<ISO-8601 UTC>",
  "validation": {
    "suite_passed": true,
    "validated_at": "<ISO-8601 UTC>",
    "checks": ["schema+coverage", "dimension", "finite-values"]
  }
}
```

Rules:
- The manifest records non-secret metadata and hashes only; it NEVER records
  the endpoint URL, credentials, or prompts (private-endpoint discipline).
- Any regeneration bumps `artifact_version`, regenerates ALL fields, and
  produces a new `artifact_sha256`.

## 2. `artifacts/import-manifest.json` extension (additive)

One NEW top-level key; `dataset`, `import`, `notes`, `generated_texts`
unchanged (feature 001/009 tests keep passing):

```json
"ticket_embeddings": {
  "artifact_path": "data/raw/tickets_embeddings.jsonl",
  "artifact_sha256": "<64-hex>",
  "embeddings_manifest_path": "data/raw/embeddings-manifest.json",
  "embeddings_manifest_sha256": "<64-hex>",
  "artifact_version": "1",
  "row_count": 2057,
  "embedding_dimension": 768,
  "imported_at": "<ISO-8601 UTC>"
}
```

Import preconditions enforced by `scripts/import_dataset.py`: artifact
SHA-256 == manifest record; coverage == pinned 2057; every vector dimension
== 768. Failure = full rollback, non-zero exit.

## 3. Artifact line schema (`tickets_embeddings.jsonl` and checkpoint)

```json
{"ticket_id": 847201, "embedding": [<768 finite floats>]}
```

Both keys always present; `embedding` has exactly 768 finite numeric values.
