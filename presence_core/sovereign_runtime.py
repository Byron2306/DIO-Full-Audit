from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse
from typing import Any


POLICY_SCHEMA = "dio.phase9.sovereign_runtime_policy.v1"
OLLAMA_PROVIDERS = frozenset({"ollama", "local_ollama", "local"})
FORBIDDEN_REMOTE_LLM_PROVIDERS = frozenset({
    "huggingface",
    "hf",
    "gemini",
    "google",
    "google_gemini",
    "nvidia",
    "nim",
    "nvidia_nim",
    "openai",
    "anthropic",
    "groq",
})


def canonical_llm_provider(value: Any) -> str:
    provider = str(value or "ollama").strip().casefold().replace("-", "_")
    if provider not in OLLAMA_PROVIDERS:
        raise ValueError(
            "Phase 9 sovereign runtime permits Ollama only; "
            f"remote/cloud LLM provider refused: {provider or '(missing)'}"
        )
    return "ollama"


def ollama_url_is_local(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").strip().casefold()
    if not host:
        return False
    if host in {"localhost", "host.docker.internal"}:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
    )


def require_local_ollama_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not ollama_url_is_local(raw):
        raise ValueError(
            "Phase 9 Ollama endpoint must be loopback or private/local network; "
            "remote public inference endpoints are refused."
        )
    return raw.rstrip("/")


def sovereign_runtime_status(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    provider = str(source.get("DIO_PRESENCE_LLM_PROVIDER") or "ollama")
    ollama_url = str(source.get("OLLAMA_URL") or "http://127.0.0.1:11434")
    try:
        canonical_provider = canonical_llm_provider(provider)
        provider_ok = True
    except ValueError:
        canonical_provider = provider
        provider_ok = False

    status = {
        "schema": POLICY_SCHEMA,
        "llm_provider": canonical_provider,
        "llm_provider_ok": provider_ok,
        "ollama_url": ollama_url,
        "ollama_endpoint_local": ollama_url_is_local(ollama_url),
        "cloud_llm_fallback_allowed": False,
        "huggingface_runtime_required": False,
        "cloudflare_runtime_required_for_s0": False,
        "canonical_asr_provider": "faster-whisper-local",
        "authority_created": False,
        "external_effects": False,
    }
    status["ready"] = (
        status["llm_provider_ok"]
        and status["ollama_endpoint_local"]
        and not status["cloud_llm_fallback_allowed"]
    )
    return status
