from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


OLLAMA_PROVIDER = "ollama"
OLLAMA_ALIASES = {"ollama", "local_ollama", "local"}
DEFAULT_OLLAMA_MODEL = "granite3.2:2b"

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


def _sovereign_setting(name: str) -> str:
    configured = os.environ.get(name)
    if configured:
        return configured.strip()
    env_path = Path(
        os.environ.get("DIO_SOVEREIGN_ENV_FILE")
        or Path.home() / ".config" / "dio" / "sovereign.env"
    ).expanduser()
    if not env_path.is_file():
        return ""
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip("\"'")
    return ""


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
        or _sovereign_setting("OLLAMA_URL")
        or "http://127.0.0.1:11434"
    ).strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SovereignRuntimeError("OLLAMA_URL must be a valid HTTP(S) endpoint.")
    return url


def ollama_model(value: str | None = None) -> str:
    model = str(
        value
        or _sovereign_setting("OLLAMA_MODEL")
        or DEFAULT_OLLAMA_MODEL
    ).strip()
    if not model:
        raise SovereignRuntimeError("Ollama model must be configured.")
    return model


def evidex_root() -> Path:
    configured = _sovereign_setting("DIO_EVIDEX_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()

    bundled = Path(__file__).resolve().parent / "cross_folder_variants" / "Evidex" / "A_CODE"
    if (bundled / ".venv" / "bin" / "python").is_file():
        return bundled

    return Path("/home/byron/Evidex").expanduser().resolve()


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
