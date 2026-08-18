from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_voice_profiles(root: Path) -> dict[str, Any]:
    path = Path(root) / "config" / "vesper_voice_profiles.json"
    if not path.is_file():
        return {"schema": "dio.vesper.voice_profiles.v1", "default_public_profile": None, "profiles": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "dio.vesper.voice_profiles.v1":
        raise ValueError("unsupported Vesper voice profile schema")
    return value


def build_voice_plan(
    *,
    root: Path,
    language: str,
    interaction: dict[str, Any] | None,
    requested_profile: str | None = None,
) -> dict[str, Any]:
    registry = load_voice_profiles(root)
    profile_id = requested_profile or os.getenv("DIO_VESPER_VOICE_PROFILE") or registry.get("default_public_profile")
    profile = (registry.get("profiles") or {}).get(profile_id) if profile_id else None
    policy = (interaction or {}).get("delivery_policy") or {}
    voice_policy = policy.get("voice") or {}
    supported = bool(profile and profile.get("model") and profile.get("language") == language)
    state = "ready_for_internal_render" if supported else "not_renderable"
    reasons: list[str] = []
    if not profile_id:
        reasons.append("no_voice_profile_selected")
    elif not profile:
        reasons.append("voice_profile_not_found")
    else:
        if not profile.get("model"):
            reasons.append("voice_model_not_assigned")
        if profile.get("language") != language:
            reasons.append("voice_language_mismatch")
        if profile.get("public_brand_state") != "approved":
            reasons.append("voice_profile_not_publicly_promoted")
    return {
        "schema": "dio.vesper.voice_render_plan.v1",
        "profile_id": profile_id,
        "backend": (profile or {}).get("backend"),
        "model": (profile or {}).get("model"),
        "language": language,
        "state": state,
        "reasons": reasons,
        "piper": {
            "length_scale": float(voice_policy.get("piper_length_scale", 1.0)),
            "noise_scale": float(os.getenv("DIO_VESPER_PIPER_NOISE_SCALE", "0.667")),
            "noise_w_scale": float(os.getenv("DIO_VESPER_PIPER_NOISE_W_SCALE", "0.8")),
        },
        "delivery_mode": policy.get("mode", "warm_professional"),
        "identity_locked": True,
        "send_authority_created": False,
        "public_default_authorized": bool(profile and profile.get("public_brand_state") == "approved"),
    }


def synthesize_piper_http(
    *,
    text: str,
    output_path: Path,
    plan: dict[str, Any],
    base_url: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Render a local WAV through Piper. This is an internal render only, never a send action."""
    if plan.get("state") != "ready_for_internal_render":
        raise RuntimeError("voice plan is not renderable")
    if plan.get("backend") != "piper_http":
        raise RuntimeError("unsupported voice backend")
    text = str(text or "").strip()
    if not text:
        raise ValueError("voice render requires text")
    endpoint = (base_url or os.getenv("DIO_VESPER_PIPER_URL") or "http://127.0.0.1:5000").rstrip("/") + "/synthesize"
    piper = plan.get("piper") or {}
    payload = {
        "text": text,
        "voice": plan.get("model"),
        "length_scale": piper.get("length_scale", 1.0),
        "noise_scale": piper.get("noise_scale", 0.667),
        "noise_w_scale": piper.get("noise_w_scale", 0.8),
    }
    response = httpx.post(endpoint, json=payload, timeout=timeout)
    response.raise_for_status()
    audio = bytes(response.content)
    if len(audio) < 44 or not audio.startswith(b"RIFF"):
        raise RuntimeError("Piper response is not a WAV payload")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio)
    return {
        "schema": "dio.vesper.voice_render_receipt.v1",
        "rendered_at": _now(),
        "profile_id": plan.get("profile_id"),
        "backend": "piper_http",
        "model": plan.get("model"),
        "language": plan.get("language"),
        "delivery_mode": plan.get("delivery_mode"),
        "audio_path": str(output_path),
        "audio_sha256": _sha256_bytes(audio),
        "audio_bytes": len(audio),
        "external_action_executed": False,
        "send_authorized": False,
        "identity_authority_created": False,
        "translation_authority_created": False,
    }
