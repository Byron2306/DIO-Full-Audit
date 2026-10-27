from __future__ import annotations

import ipaddress
import os
import sys
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


LOCAL_OLLAMA_HOST_ALIASES = frozenset({
    "localhost",
    "ollama",
    "seraph-ollama",
    "host.docker.internal",
})


def ollama_url(value: str | None = None) -> str:
    """Resolve an Ollama endpoint while refusing arbitrary remote hosts.

    The hostname aliases are limited to local loopback and the explicit local
    Docker/host aliases used by DIO's sovereign deployment. This is a policy
    boundary, not a claim that DNS or the network namespace is independently
    attested.
    """
    url = str(
        value
        or _sovereign_setting("OLLAMA_URL")
        or "http://127.0.0.1:11434"
    ).strip().rstrip("/")
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise SovereignRuntimeError("OLLAMA_URL has invalid authority or port syntax.") from exc

    if (
        parsed.scheme != "http"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or port is None
        or not (1 <= port <= 65535)
    ):
        raise SovereignRuntimeError(
            "OLLAMA_URL must be a plain local HTTP endpoint with an explicit valid port."
        )

    try:
        is_local = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_local = hostname in LOCAL_OLLAMA_HOST_ALIASES
    if not is_local:
        raise SovereignRuntimeError(
            "OLLAMA_URL remote hosts are disabled; use loopback or an approved local-container alias."
        )
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
    """Resolve only the DIO-owned Evidex source, independently of its venv."""
    root = Path(__file__).resolve().parent
    bundled = root / "cross_folder_variants" / "Evidex" / "A_CODE"
    resolved = bundled.resolve()
    if not resolved.is_relative_to(root):
        raise SovereignRuntimeError("Canonical Evidex source escapes DIO root.")
    configured = _sovereign_setting("DIO_EVIDEX_ROOT")
    if configured and Path(configured).expanduser().resolve() != resolved:
        raise SovereignRuntimeError("Evidex source must be the canonical embedded DIO engine.")
    return resolved


def evidex_python() -> Path:
    """Return an executable that can run the embedded Evidex engine.

    Production installations normally give the embedded engine its own virtual
    environment.  A source checkout used for controlled execution may instead
    run it with the active interpreter; ``evidex_environment`` supplies the
    canonical import roots in either case.  The fallback never changes the
    engine source root or permits an external Evidex checkout.
    """
    managed = evidex_root() / ".venv" / "bin" / "python"
    return managed if managed.is_file() else Path(sys.executable).resolve()


def evidex_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    """Bind engine and shared DIO imports without alternate checkout roots."""
    root = Path(__file__).resolve().parent
    env = dict(os.environ if base is None else base)
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in (
        evidex_root() / "src", root, root / "products"
    ))
    for key in ("DIO_ROOT", "DIO_REPO_ROOT", "DIO_FULL_AUDIT_ROOT"):
        env[key] = str(root)
    return env


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
