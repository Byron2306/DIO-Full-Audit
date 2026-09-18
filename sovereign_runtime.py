from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


OLLAMA_PROVIDER = "ollama"
OLLAMA_ALIASES = {"ollama", "local_ollama", "local"}

FORBIDDEN_CLOUD_LLM_PROVIDERS = {
    "auto",
    "huggingface",
    "hf",
    "gemini",
    "google",
    "google_gemini",
    "nim",
    "nvidia",
    "nvidia_nim",
    "openai",
    "anthropic",
    "claude",
}


class SovereignRuntimeError(RuntimeError):
    pass


def normalise_provider(value: str | None) -> str:
    return str(value or OLLAMA_PROVIDER).strip().casefold().replace("-", "_")


def require_ollama_provider(
    value: str | None,
    *,
    component: str,
) -> str:
    provider = normalise_provider(value)
    if provider not in OLLAMA_ALIASES:
        raise SovereignRuntimeError(
            f"{component} sovereign runtime permits only Ollama; "
            f"provider {provider!r} is disabled."
        )
    return OLLAMA_PROVIDER


def ollama_url(value: str | None = None) -> str:
    url = str(
        value
        or os.environ.get("OLLAMA_URL")
        or "http://127.0.0.1:11434"
    ).strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SovereignRuntimeError("OLLAMA_URL must be a valid HTTP(S) endpoint.")
    return url


def ollama_model(value: str | None = None) -> str:
    model = str(
        value
        or os.environ.get("OLLAMA_MODEL")
        or "qwen2.5:0.5b"
    ).strip()
    if not model:
        raise SovereignRuntimeError("Ollama model must be configured.")
    return model


@dataclass(frozen=True)
class SovereignLLMPolicy:
    provider: str
    model: str
    base_url: str
    cloud_fallback_allowed: bool
    hf_runtime_allowed: bool


def llm_policy(
    *,
    model: str | None = None,
    base_url: str | None = None,
) -> SovereignLLMPolicy:
    return SovereignLLMPolicy(
        provider=OLLAMA_PROVIDER,
        model=ollama_model(model),
        base_url=ollama_url(base_url),
        cloud_fallback_allowed=False,
        hf_runtime_allowed=False,
    )
