from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .openvoice2 import convert_tone_color


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def verified_vera_runtime_inventory(root: Path, *, base_url: str | None = None) -> dict[str, Any]:
    """Recheck observed local runtime evidence, without claiming HTTP or hardware attestation.

    This optional evidence is for production media provenance. It grants no render or send authority.
    """
    path = Path(os.getenv("DIO_VESPER_RUNTIME_INVENTORY") or (
        Path(root) / "state/presence/voice_verification/vera_runtime_inventory.json"
    ))
    if not path.is_file():
        raise RuntimeError("verified local Vera runtime inventory is missing")
    raw = path.read_bytes()
    inventory = json.loads(raw)
    evidence_class = "LOCAL_VERIFIED_RUNTIME_INVENTORY"
    if inventory.get("schema") != "dio.vesper.local_verified_runtime_inventory.v1" or inventory.get("evidence_class") != evidence_class:
        raise RuntimeError("unsupported local Vera runtime inventory")
    endpoint = (base_url or os.getenv("DIO_VESPER_POCKET_TTS_URL") or "http://127.0.0.1:8000").rstrip("/") + "/tts"
    service = inventory.get("service") or {}
    if service.get("endpoint") != endpoint:
        raise RuntimeError("local Vera runtime inventory endpoint mismatch")
    try:
        command = Path(f"/proc/{int(service['pid'])}/cmdline").read_bytes().decode().strip("\0").split("\0")
    except (OSError, KeyError, ValueError) as exc:
        raise RuntimeError("observed local Vera service is unavailable") from exc
    if command != service.get("command"):
        raise RuntimeError("observed local Vera service command changed")
    files = inventory.get("files") or []
    roles = {row.get("role"): row for row in files}
    provenance = inventory.get("model_provenance") or {}
    required = ("model_id", "model_revision", "model_sha256", "voice_revision", "voice_sha256", "runtime_source")
    if provenance.get("voice_id") != "vera" or any(not provenance.get(key) for key in required):
        raise RuntimeError("local Vera model provenance is incomplete")
    for role, key in (("model", "model_sha256"), ("voice", "voice_sha256")):
        if (roles.get(role) or {}).get("sha256") != provenance[key]:
            raise RuntimeError("local Vera model provenance does not match observed files")
    for row in files:
        try:
            with Path(row["path"]).open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
        except (OSError, KeyError) as exc:
            raise RuntimeError("observed local Vera runtime file is unavailable") from exc
        if digest != row.get("sha256"):
            raise RuntimeError("local Vera runtime file hash mismatch: " + str(row.get("role")))
    return {
        "model_provenance": provenance,
        "runtime_inventory": {"path": str(path), "sha256": _sha256_bytes(raw), "evidence_class": evidence_class},
    }


def load_voice_profiles(root: Path) -> dict[str, Any]:
    path = Path(root) / "config" / "vesper_voice_profiles.json"
    if not path.is_file():
        return {"schema": "dio.vesper.voice_profiles.v1", "default_public_profile": None, "profiles": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "dio.vesper.voice_profiles.v1":
        raise ValueError("unsupported Vesper voice profile schema")
    return value


def _resolved_path(root: Path, value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = Path(root) / path
    return str(path)


def build_voice_plan(
    *,
    root: Path,
    language: str,
    interaction: dict[str, Any] | None,
    requested_profile: str | None = None,
    public_default_only: bool = False,
) -> dict[str, Any]:
    registry = load_voice_profiles(root)
    # Live Vesper speech follows the promoted identity. Audition overrides are internal only.
    profile_id = registry.get("default_public_profile") if public_default_only else (
        requested_profile or os.getenv("DIO_VESPER_VOICE_PROFILE") or registry.get("default_public_profile")
    )
    profile = (registry.get("profiles") or {}).get(profile_id) if profile_id else None
    policy = (interaction or {}).get("delivery_policy") or {}
    voice_policy = policy.get("voice") or {}
    reasons: list[str] = []
    state = "not_renderable"
    backend = (profile or {}).get("backend")

    if not profile_id:
        reasons.append("no_voice_profile_selected")
    elif not profile:
        reasons.append("voice_profile_not_found")
    else:
        if profile.get("language") != language:
            reasons.append("voice_language_mismatch")
        elif backend == "pocket_tts":
            if not (profile.get("voice_url") or profile.get("model")):
                reasons.append("pocket_voice_not_assigned")
            else:
                state = "ready_for_internal_render"
        elif backend == "piper_http":
            if not profile.get("model"):
                reasons.append("voice_model_not_assigned")
            else:
                state = "ready_for_internal_render"
        elif backend == "openvoice2_piper":
            if not profile.get("source_model"):
                reasons.append("piper_source_model_not_assigned")
            if not profile.get("target_embedding"):
                reasons.append("openvoice_target_embedding_not_assigned")
            if not profile.get("converter_dir"):
                reasons.append("openvoice_converter_not_assigned")
            if not profile.get("reference_consent_verified"):
                reasons.append("voice_reference_consent_not_verified")
            if not profile.get("reference_provenance"):
                reasons.append("voice_reference_provenance_missing")
            if not reasons:
                state = "ready_for_internal_render"
        else:
            reasons.append("unsupported_voice_backend")
        if profile.get("public_brand_state") != "approved":
            reasons.append("voice_profile_not_publicly_promoted")
            if public_default_only:
                state = "not_renderable"

    return {
        "schema": "dio.vesper.voice_render_plan.v1",
        "profile_id": profile_id,
        "backend": backend,
        "model": (profile or {}).get("model"),
        "voice_url": (profile or {}).get("voice_url"),
        "source_model": (profile or {}).get("source_model"),
        "language": language,
        "state": state,
        "reasons": reasons,
        "piper": {
            "length_scale": float(voice_policy.get("piper_length_scale", 1.0)),
            "noise_scale": float(os.getenv("DIO_VESPER_PIPER_NOISE_SCALE", "0.667")),
            "noise_w_scale": float(os.getenv("DIO_VESPER_PIPER_NOISE_W_SCALE", "0.8")),
        },
        "openvoice2": {
            "target_embedding": _resolved_path(root, (profile or {}).get("target_embedding")),
            "converter_dir": _resolved_path(root, (profile or {}).get("converter_dir")),
            "reference_provenance": (profile or {}).get("reference_provenance"),
            "reference_consent_verified": bool((profile or {}).get("reference_consent_verified")),
        },
        "delivery_mode": policy.get("mode", "warm_professional"),
        "identity_locked": True,
        "send_authority_created": False,
        "public_default_authorized": bool(profile and profile.get("public_brand_state") == "approved"),
    }


def synthesize_pocket_tts(
    *,
    text: str,
    output_path: Path,
    plan: dict[str, Any],
    base_url: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Render a local WAV through Pocket TTS. Rendering never creates send authority."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("voice render requires text")
    voice_url = str(plan.get("voice_url") or plan.get("model") or "").strip()
    if not voice_url:
        raise RuntimeError("Pocket TTS voice is not assigned")
    endpoint = (base_url or os.getenv("DIO_VESPER_POCKET_TTS_URL") or "http://127.0.0.1:8000").rstrip("/") + "/tts"
    response = httpx.post(endpoint, data={"text": text, "voice_url": voice_url}, timeout=timeout)
    response.raise_for_status()
    audio = bytes(response.content)
    if len(audio) < 44 or not audio.startswith(b"RIFF"):
        raise RuntimeError("Pocket TTS response is not a WAV payload")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio)
    return {
        "schema": "dio.vesper.voice_render_receipt.v1",
        "rendered_at": _now(),
        "profile_id": plan.get("profile_id"),
        "backend": "pocket_tts",
        "voice_url": voice_url,
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


def synthesize_piper_http(
    *,
    text: str,
    output_path: Path,
    plan: dict[str, Any],
    base_url: str | None = None,
    timeout: float = 30.0,
    voice_model: str | None = None,
) -> dict[str, Any]:
    """Render a local WAV through Piper. This is an internal render only, never a send action."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("voice render requires text")
    model = voice_model or plan.get("model") or plan.get("source_model")
    if not model:
        raise RuntimeError("Piper voice model is not assigned")
    endpoint = (base_url or os.getenv("DIO_VESPER_PIPER_URL") or "http://127.0.0.1:5000").rstrip("/") + "/synthesize"
    piper = plan.get("piper") or {}
    payload = {
        "text": text,
        "voice": model,
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
        "model": model,
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


def synthesize_voice(
    *,
    text: str,
    output_path: Path,
    plan: dict[str, Any],
    piper_url: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Render the approved Vesper text using the selected internal voice backend."""
    if plan.get("state") != "ready_for_internal_render":
        raise RuntimeError("voice plan is not renderable: " + ",".join(plan.get("reasons") or []))
    backend = plan.get("backend")
    if backend == "pocket_tts":
        return synthesize_pocket_tts(text=text, output_path=output_path, plan=plan, timeout=timeout)
    if backend == "piper_http":
        return synthesize_piper_http(text=text, output_path=output_path, plan=plan, base_url=piper_url, timeout=timeout)
    if backend != "openvoice2_piper":
        raise RuntimeError(f"unsupported voice backend: {backend}")

    output_path = Path(output_path)
    base_path = output_path.with_name(output_path.stem + ".piper-base.wav")
    base_receipt = synthesize_piper_http(
        text=text,
        output_path=base_path,
        plan=plan,
        base_url=piper_url,
        timeout=timeout,
        voice_model=str(plan.get("source_model") or ""),
    )
    ov = plan.get("openvoice2") or {}
    tone_receipt = convert_tone_color(
        source_wav=base_path,
        output_wav=output_path,
        converter_dir=Path(str(ov.get("converter_dir"))),
        target_embedding=Path(str(ov.get("target_embedding"))),
    )
    try:
        base_path.unlink()
    except OSError:
        pass
    return {
        "schema": "dio.vesper.voice_render_receipt.v2",
        "rendered_at": _now(),
        "profile_id": plan.get("profile_id"),
        "backend": "openvoice2_piper",
        "source_model": plan.get("source_model"),
        "language": plan.get("language"),
        "delivery_mode": plan.get("delivery_mode"),
        "audio_path": str(output_path),
        "audio_sha256": tone_receipt.get("output_audio_sha256"),
        "audio_bytes": tone_receipt.get("output_bytes"),
        "base_renderer": base_receipt,
        "tone_identity_renderer": tone_receipt,
        "semantic_text_changed": False,
        "external_action_executed": False,
        "send_authorized": False,
        "identity_authority_created": False,
        "translation_authority_created": False,
    }
