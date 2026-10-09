"""LLM configuration and OpenAI-compatible client for the pinned local model.

The runtime query path uses ONLY the configured local llama.cpp endpoint.
There is no provider or model fallback. Model identity is verified at
preflight and startup; any mismatch or endpoint failure stops processing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

# Requested model artifact (approved). The exact API model ID is discovered
# from GET /v1/models and pinned; preflight records it in artifacts/.
REQUESTED_MODEL_ARTIFACT = "openai/models\\Qwen3.8-27B-UD-Q4_K_M.gguf"


@dataclass(frozen=True)
class LLMConfig:
    """Immutable LLM runtime configuration loaded from the environment."""

    provider: str
    base_url: str
    model: str
    api_key: str
    temperature: float
    cache: bool

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            provider=os.environ.get("LLM_PROVIDER", "openai-compatible"),
            base_url=os.environ.get("LLM_BASE_URL", "").rstrip("/"),
            model=os.environ.get("LLM_MODEL", ""),
            api_key=os.environ.get("LLM_API_KEY", "local-not-required"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0")),
            cache=os.environ.get("LLM_CACHE", "false").lower() == "true",
        )


class LLMEndpointError(RuntimeError):
    """Raised when the configured LLM endpoint or model cannot be reached."""


def list_models(config: LLMConfig, timeout: float = 30.0) -> list[str]:
    """Return the exact API model IDs exposed by the configured endpoint."""
    if not config.base_url:
        raise LLMEndpointError("LLM_BASE_URL is not configured")
    url = f"{config.base_url}/models"
    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - normalized below
        raise LLMEndpointError(f"LLM endpoint /models request failed: {exc}") from exc
    data = resp.json()
    ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
    if not ids:
        # llama.cpp also returns a "models" array; fall back to it.
        ids = [m.get("model") for m in data.get("models", []) if m.get("model")]
    return ids


def verify_model(config: LLMConfig, timeout: float = 30.0) -> str:
    """Verify the requested model is loaded and return its exact API ID.

    Raises LLMEndpointError if the endpoint or exact model cannot be verified.
    """
    ids = list_models(config, timeout=timeout)
    if config.model and config.model in ids:
        return config.model
    raise LLMEndpointError(
        f"Requested model {config.model!r} not present on endpoint; "
        f"available: {ids!r}"
    )


def chat_completion(
    config: LLMConfig,
    messages: list[dict],
    timeout: float = 120.0,
) -> dict:
    """Run one deterministic chat completion against the pinned local model."""
    model = verify_model(config, timeout=timeout)
    url = f"{config.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": config.temperature,
        "cache_prompt": config.cache,
    }
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise LLMEndpointError(f"chat completion failed: {exc}") from exc
    return resp.json()


def configure_dspy(config: LLMConfig):
    """Configure DSPy to use the pinned local model. No fallback is set."""
    import dspy

    model = verify_model(config)
    lm = dspy.LM(
        model=f"openai/{model}",
        api_base=config.base_url,
        api_key=config.api_key,
        temperature=config.temperature,
        cache=config.cache,
        model_type="chat",
    )
    dspy.configure(lm=lm)
    return lm
