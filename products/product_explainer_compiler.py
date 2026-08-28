from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class ProductExplainerError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _fingerprint(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_media_style_profile(
    profile_id: str,
    *,
    root: Path = ROOT,
    require_assets: bool = True,
) -> tuple[dict[str, Any], str]:
    registry_path = Path(root) / "config" / "media_style_profiles.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            f"invalid media style profile registry: {registry_path}",
        ) from exc

    if registry.get("schema") != "dio.media.style_profile_registry.v1":
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "unsupported media style profile registry schema",
        )

    source_profile = (registry.get("profiles") or {}).get(profile_id)
    if not isinstance(source_profile, dict) or source_profile.get("schema") != "dio.media.style_profile.v1":
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            f"unknown or invalid media style profile: {profile_id}",
        )

    profile = json.loads(json.dumps(source_profile))
    release = profile.get("release") or {}
    if (
        release.get("automatic_external_publication") is not False
        or release.get("automatic_media_spend") is not False
    ):
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "style profile may not create publication or spend authority",
        )

    typography = profile.get("typography") or {}
    if typography.get("silent_font_fallback") is not False:
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "silent font fallback must remain disabled",
        )

    if require_assets:
        try:
            required = [
                profile["golden_reference"]["master"],
                typography["wordmark"],
                typography["sigil"],
            ]
        except (KeyError, TypeError) as exc:
            raise ProductExplainerError(
                "STYLE_PROFILE_INVALID",
                "style profile is missing required asset bindings",
            ) from exc
        missing = [value for value in required if not (Path(root) / value).is_file()]
        if missing:
            raise ProductExplainerError(
                "STYLE_ASSET_MISSING",
                "required DIO brand assets are missing",
                {"missing": missing},
            )
        master_path = Path(root) / profile["golden_reference"]["master"]
        actual_master_sha = "sha256:" + hashlib.sha256(master_path.read_bytes()).hexdigest()
        declared_master_sha = profile["golden_reference"].get("sha256")
        if declared_master_sha in {None, "", "BOUND_AT_RUNTIME"}:
            profile["golden_reference"]["sha256"] = actual_master_sha
        elif declared_master_sha != actual_master_sha:
            raise ProductExplainerError(
                "STYLE_ASSET_HASH_MISMATCH",
                "golden reference master hash does not match the bound asset",
                {"expected": declared_master_sha, "actual": actual_master_sha},
            )

    return profile, _fingerprint(profile)
