from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .product_explainer_compiler import ROOT, ProductExplainerError
from .product_visual_asset_pack import load_visual_asset_pack, resolve_scene_asset_recipe


REGISTRY_SCHEMA = "dio.product_media_profile_registry.v1"
PROFILE_SCHEMA = "dio.product_media_profile.v1"
REQUIRED_SCENE_BEATS = (
    "problem",
    "product_definition",
    "mechanism",
    "proof",
    "differentiation",
    "result",
    "call_to_action",
)
FORBIDDEN_AUTHORITY_KEYS = {
    "claims",
    "claim_envelope",
    "capabilities",
    "outputs",
    "product_truth",
    "semantic_truth",
    "publication_authority",
    "media_spend_authority",
}


def _fingerprint(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_product_media_profile(
    product_id: str,
    *,
    root: Path = ROOT,
) -> tuple[dict[str, Any], str]:
    registry_path = Path(root) / "config" / "product_media_profiles.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductExplainerError(
            "PRODUCT_MEDIA_PROFILE_INVALID",
            f"invalid product media profile registry: {registry_path}",
        ) from exc

    if registry.get("schema") != REGISTRY_SCHEMA:
        raise ProductExplainerError(
            "PRODUCT_MEDIA_PROFILE_INVALID",
            "unsupported product media profile registry schema",
        )

    normalized_id = str(product_id or "").strip().upper()
    source_profile = (registry.get("profiles") or {}).get(normalized_id)
    if not isinstance(source_profile, dict) or source_profile.get("schema") != PROFILE_SCHEMA:
        raise ProductExplainerError(
            "PRODUCT_MEDIA_PROFILE_INVALID",
            f"unknown or invalid product media profile: {product_id}",
        )

    profile = json.loads(json.dumps(source_profile))
    if FORBIDDEN_AUTHORITY_KEYS.intersection(profile):
        raise ProductExplainerError(
            "PRODUCT_MEDIA_PROFILE_INVALID",
            "product media profiles may describe representation but may not create semantic or release authority",
        )

    scene_grammar = profile.get("scene_grammar")
    if not isinstance(scene_grammar, dict) or tuple(scene_grammar.keys()) != REQUIRED_SCENE_BEATS:
        raise ProductExplainerError(
            "PRODUCT_MEDIA_PROFILE_INVALID",
            "product media profile must define the canonical seven-beat scene grammar",
        )
    for beat, scene in scene_grammar.items():
        if not isinstance(scene, dict) or not scene.get("visual_mode") or not scene.get("direction"):
            raise ProductExplainerError(
                "PRODUCT_MEDIA_PROFILE_INVALID",
                f"product media scene grammar is incomplete: {beat}",
            )

    score = profile.get("score") or {}
    if (
        score.get("inherits") != "DIO_SONIC_IDENTITY_V1"
        or not score.get("variant")
        or not score.get("source_path")
        or not isinstance(score.get("recipe"), dict)
    ):
        raise ProductExplainerError(
            "PRODUCT_MEDIA_PROFILE_INVALID",
            "product media profile must inherit the governed DIO sonic identity",
        )

    return profile, _fingerprint(profile)


def compile_brand_render_brief(
    style_profile: dict[str, Any],
    product_profile: dict[str, Any],
    *,
    product_id: str,
) -> dict[str, Any]:
    profile_id = str(style_profile.get("profile_id") or "").strip()
    if not profile_id:
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "style profile is missing profile_id",
        )

    visual = style_profile.get("visual") or {}
    grammar = [str(value).strip() for value in visual.get("grammar") or [] if str(value).strip()]
    if not grammar:
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "style profile is missing executable visual grammar",
        )

    forbidden = [
        str(value).strip()
        for value in visual.get("forbidden") or []
        if str(value).strip()
    ]
    motion = style_profile.get("motion") or {}
    typography = style_profile.get("typography") or {}
    score = product_profile.get("score") or {}
    visual_asset_pack = product_profile.get("visual_asset_pack") or {}
    if visual_asset_pack and not isinstance(visual_asset_pack, dict):
        raise ProductExplainerError(
            "PRODUCT_MEDIA_PROFILE_INVALID",
            "product media visual asset pack binding must be an object",
        )

    visual_direction = (
        "Render every scene inside the governed DIO cinematic world: "
        + "; ".join(grammar)
        + ". Preserve product truth and use generated imagery only as representation, never as observed proof."
    )

    brief: dict[str, Any] = {
        "schema": "dio.brand_render_brief.v1",
        "profile_id": profile_id,
        "product_id": str(product_id or "").strip().upper(),
        "visual_direction": visual_direction,
        "forbidden_motifs": forbidden,
        "scene_grammar": json.loads(json.dumps(product_profile.get("scene_grammar") or {})),
        "typography": {
            "brand_face": typography.get("brand_face"),
            "body_face": typography.get("body_face"),
            "technical_face": typography.get("technical_face"),
            "wordmark": typography.get("wordmark"),
            "sigil": typography.get("sigil"),
            "silent_font_fallback": typography.get("silent_font_fallback"),
        },
        "motion": json.loads(json.dumps(motion)),
        "end_card": {
            "visual_mode": "brand_end_card",
            "background": "black",
            "accent": "restrained gold",
            "require_wordmark": True,
            "require_sigil": True,
            "require_url": True,
            "wordmark": typography.get("wordmark"),
            "sigil": typography.get("sigil"),
        },
        "music_direction": {
            "inherits": score.get("inherits"),
            "variant": score.get("variant"),
            "source_path": score.get("source_path"),
            "recipe": json.loads(json.dumps(score.get("recipe") or {})),
            "policy": (style_profile.get("sound") or {}).get("music_policy"),
            "forbidden": list((style_profile.get("sound") or {}).get("forbidden") or []),
        },
        "authority": {
            "changes_product_truth": False,
            "creates_claim_authority": False,
            "creates_publication_authority": False,
            "creates_media_spend_authority": False,
        },
    }
    if visual_asset_pack:
        brief["visual_asset_pack"] = json.loads(json.dumps(visual_asset_pack))
    return brief


def enrich_renderer_script(
    script_package: dict[str, Any],
    production_request: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Create a renderer-facing copy without mutating semantic script truth."""
    brand = production_request.get("brand_render_brief") or {}
    if not isinstance(brand, dict):
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "renderer enrichment requires a valid brand render brief",
        )

    profile_id = str(brand.get("profile_id") or "").strip()
    visual_direction = str(brand.get("visual_direction") or "").strip()
    scene_grammar = brand.get("scene_grammar") or {}
    if not profile_id or not visual_direction or not isinstance(scene_grammar, dict):
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "brand render brief is incomplete for renderer enrichment",
        )

    pack: dict[str, Any] | None = None
    pack_profile: dict[str, Any] | None = None
    requested_pack = production_request.get("visual_asset_pack")
    if requested_pack:
        if not isinstance(requested_pack, dict):
            raise ProductExplainerError(
                "VISUAL_ASSET_PACK_INVALID",
                "media production visual asset pack binding must be an object",
            )
        pack_id = str(requested_pack.get("id") or "").strip().upper()
        expected_sha = str(requested_pack.get("sha256") or "").strip()
        if not pack_id or not expected_sha or requested_pack.get("fallback") != "REFUSE":
            raise ProductExplainerError(
                "VISUAL_ASSET_PACK_INVALID",
                "media production visual asset pack binding is incomplete",
            )
        pack, actual_sha = load_visual_asset_pack(pack_id, root=Path(root))
        if actual_sha != expected_sha:
            raise ProductExplainerError(
                "VISUAL_ASSET_PACK_INVALID",
                "media production visual asset pack fingerprint mismatch",
                {"expected": expected_sha, "actual": actual_sha},
            )
        brand_pack = brand.get("visual_asset_pack") or {}
        if not isinstance(brand_pack, dict):
            raise ProductExplainerError(
                "VISUAL_ASSET_PACK_INVALID",
                "brand render brief visual asset pack binding must be an object",
            )
        pack_profile = {"visual_asset_pack": json.loads(json.dumps(brand_pack))}

    rendered = json.loads(json.dumps(script_package))
    rendered["brand_profile_id"] = profile_id
    rendered["representation_only"] = True

    forbidden_motifs = [
        str(value).strip()
        for value in brand.get("forbidden_motifs") or []
        if str(value).strip()
    ]
    default_motion = str((brand.get("motion") or {}).get("default") or "").strip()

    for scene in rendered.get("scenes") or []:
        beat = str(scene.get("story_beat") or "").strip()
        grammar = scene_grammar.get(beat)
        if not isinstance(grammar, dict):
            raise ProductExplainerError(
                "PRODUCT_MEDIA_PROFILE_INVALID",
                f"no renderer scene grammar found for story beat: {beat}",
            )

        directions = [
            str(value).strip()
            for value in grammar.get("direction") or []
            if str(value).strip()
        ]
        if not directions:
            raise ProductExplainerError(
                "PRODUCT_MEDIA_PROFILE_INVALID",
                f"renderer scene grammar has no visual direction: {beat}",
            )

        scene["brand_profile_id"] = profile_id
        scene["visual_mode"] = str(grammar.get("visual_mode") or "").strip()
        scene["visual_requirements"] = [visual_direction, *directions]
        scene["forbidden_motifs"] = list(forbidden_motifs)
        scene["motion_cue"] = str(grammar.get("motion") or default_motion).strip()

        if pack is not None and pack_profile is not None:
            scene["visual_asset_recipe"] = resolve_scene_asset_recipe(
                pack,
                pack_profile,
                beat,
            )

        if scene["visual_mode"] == "brand_end_card" or beat == "call_to_action":
            scene["end_card"] = json.loads(json.dumps(brand.get("end_card") or {}))

    return rendered
