from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from adapters.document_studio.art_direction import build_art_direction
from adapters.document_studio.local_media_compositor import render_story_frames
from adapters.document_studio.visual_qa import validate_visual_contract
from scripts.beast_visual_memory import resolve_visual_memory
from scripts.cinematic_motion_renderer import render_cinematic_format

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_MEMORY_FIELDS = {
    "aesthetic",
    "palette_behavior",
    "photography",
    "typography",
    "texture",
    "proof_treatment",
    "rhythm",
}


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _negative_design_text(row: Any) -> str:
    if isinstance(row, dict):
        for key in ("detail", "failure_category", "pattern", "failure_code", "reason"):
            value = str(row.get(key) or "").strip()
            if value:
                return value
        return json.dumps(row, sort_keys=True, ensure_ascii=True)
    return str(row).strip()


def _apply_visual_memory(art: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    """Apply human-approved BEAST style fields and active negative patterns only."""
    updated = json.loads(json.dumps(art))
    language = dict(updated.get("art_language") or {})
    applied: list[dict[str, Any]] = []
    for row in memory.get("approved_patterns") or []:
        pattern = dict(row.get("design_pattern") or {})
        accepted = {key: pattern[key] for key in ALLOWED_MEMORY_FIELDS if key in pattern and pattern[key]}
        if accepted:
            language.update(accepted)
            applied.append({"credit_id": row.get("credit_id"), "fields": sorted(accepted)})
    updated["art_language"] = language

    anti_patterns = list(updated.get("anti_patterns") or [])
    memory_negatives: list[str] = []
    for row in memory.get("negative_patterns") or []:
        text = _negative_design_text(row)
        if text and text not in anti_patterns:
            anti_patterns.append(text)
            memory_negatives.append(text)
    updated["anti_patterns"] = anti_patterns

    updated.setdefault("beast_visual_memory", {})["applied_crystals"] = applied
    updated["beast_visual_memory"]["applied_negative_patterns"] = memory_negatives
    updated["beast_visual_memory"]["authority"] = "representational_context_only"
    core = {key: value for key, value in updated.items() if key != "art_direction_hash"}
    updated["art_direction_hash"] = _hash(core)
    return updated


def build_art_directed_gamma_request(story: dict[str, Any], directory: Path) -> dict[str, Any]:
    """Compile Document Studio art direction and render the governed local frames.

    The returned Gamma request is an OPTIONAL candidate request. The local compositor
    is the primary composition path and is rendered here so that media production does
    not depend on Gamma availability or Gamma's presentation-layout priors.
    """
    direction = dict(story.get("creative_direction") or {})
    archetype = str(direction.get("audience_archetype") or "general_professional")
    surface = str(story.get("surface") or "campaign_story")
    visual_grammar = str(direction.get("visual_grammar") or "")
    memory = resolve_visual_memory(
        audience_archetype=archetype,
        surface=surface,
        visual_grammar=visual_grammar,
    )
    art = _apply_visual_memory(build_art_direction(story, beast_memory=memory), memory)
    art_path = directory / f"DOCUMENT_STUDIO_ART_DIRECTION_{surface.upper()}.json"
    _write_json(art_path, art)

    local_composition = render_story_frames(story=story, art_direction=art, directory=directory)

    # Gamma receives only the short display copy. Narration stays with the voice lane.
    blocks = [f"# {scene['display_copy']}" for scene in art["scenes"]]
    payload = {
        "schema": "dio.gamma.campaign_story_request.v1",
        "family_id": story["family_id"],
        "surface": surface,
        "title": story["title"],
        "story_hash": story["story_hash"],
        "semantic_law_hash": story["semantic_law_hash"],
        "projection_hash": story["projection_hash"],
        "art_direction_hash": art["art_direction_hash"],
        "num_cards": len(story["scenes"]),
        "input_text": "\n\n---\n\n".join(blocks),
        "creative_direction": {
            "audience_archetype": archetype,
            "tone": direction.get("tone") or [],
            "pacing": direction.get("pacing"),
            "visual_grammar": visual_grammar,
            "motion_grammar": direction.get("motion_grammar"),
            "surface": surface,
            "document_studio_art_language": art["art_language"],
            "scene_directions": art["scenes"],
            "anti_patterns": art["anti_patterns"],
            "format_core_profile": art["format_core_profile"],
            "format_core_profile_hash": art["format_core_profile_hash"],
            "beast_visual_memory": art["beast_visual_memory"],
            "local_composition_receipt": local_composition["receipt"],
        },
        "semantic_guardrails": story["semantic_guardrails"],
        "output_dir": str((directory / "gamma" / surface).resolve()),
        "release": {"state": "held", "visual_review_required": True, "operator_approval_required": True},
        "visual_source_policy": {
            "primary": "document_studio_local_compositor",
            "gamma": "optional_candidate_only",
            "gamma_required_for_media": False,
        },
    }
    payload["request_hash"] = _hash(payload)
    return payload


def run_art_directed_gamma(path: Path) -> tuple[str, str]:
    """Generate an optional Gamma candidate. Failure is evidence, not a media blocker."""
    completed = subprocess.run(
        ["node", str(ROOT / "scripts" / "run_gamma_art_directed_story.js"), str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=540,
    )
    if completed.returncode != 0:
        return "failed_optional", (completed.stderr or completed.stdout or "Art-directed Gamma campaign story failed").strip()[-2400:]
    return "ready_optional", ""


def _gamma_candidate_state(variant: dict[str, Any]) -> dict[str, Any]:
    gamma_spec = dict(variant.get("gamma") or {})
    receipt_path = Path(str(gamma_spec.get("receipt") or "")).expanduser()
    if not receipt_path.is_file():
        return {"state": "not_generated", "required": False, "selected": False, "receipt": ""}
    try:
        receipt = _read_json(receipt_path)
    except (OSError, json.JSONDecodeError):
        return {"state": "invalid_receipt", "required": False, "selected": False, "receipt": str(receipt_path)}
    ready = receipt.get("state") == "ready" and receipt.get("request_hash") == gamma_spec.get("request_hash")
    return {
        "state": "ready_optional" if ready else "stale_or_failed",
        "required": False,
        "selected": False,
        "receipt": str(receipt_path.resolve()),
        "generation_id": receipt.get("generation_id") if ready else None,
    }


def _local_scene_images(variant: dict[str, Any], scene_count: int) -> list[Path]:
    rows = [Path(str(value)).expanduser().resolve() for value in (variant.get("scene_images_fallback") or [])]
    if len(rows) != scene_count or not rows:
        raise RuntimeError(f"Document Studio local compositor did not provide one frame per scene: {len(rows)} != {scene_count}")
    missing = [str(path) for path in rows if not path.is_file()]
    if missing:
        raise RuntimeError("Document Studio local scene frame(s) missing: " + ", ".join(missing))
    return rows


def render_art_directed_campaign_media(
    request_path: Path,
    *,
    nichefoundry_root: Path | None = None,
) -> dict[str, Any]:
    """Render media from Document Studio local frames; Gamma is optional evidence only."""
    from scripts import build_campaign_media_v3 as media_v3

    request = _read_json(request_path)
    if request.get("schema") != "nichefoundry.dio_campaign_production_request.v3":
        raise media_v3.CampaignMediaError("Expected a nichefoundry.dio_campaign_production_request.v3 request.")
    variants = dict(request.get("variants") or {})
    if set(variants) != {"vertical_short", "landscape_explainer"}:
        raise media_v3.CampaignMediaError("Visual spine requires vertical_short and landscape_explainer variants.")
    release = dict(request.get("release") or {})
    if release.get("state") != "held" or release.get("spend") != "disabled":
        raise media_v3.CampaignMediaError("Visual spine requires publication held and spend disabled.")

    nfr = nichefoundry_root or media_v3.DEFAULT_NICHEFOUNDRY_ROOT
    variant_receipts: dict[str, Any] = {}
    gamma_requests: list[dict[str, Any]] = []
    art_hashes: dict[str, str] = {}

    for surface, variant in variants.items():
        story = dict(variant.get("story") or {})
        scenes = list(story.get("scenes") or [])
        if not scenes:
            raise media_v3.CampaignMediaError(f"Projected story is empty for {surface}.")
        images = _local_scene_images(variant, len(scenes))

        gamma_request_path = Path(str((variant.get("gamma") or {}).get("request") or "")).expanduser().resolve()
        if not gamma_request_path.is_file():
            raise media_v3.CampaignMediaError(f"Document Studio art-direction request is missing for {surface}: {gamma_request_path}")
        gamma_request = _read_json(gamma_request_path)
        gamma_requests.append(gamma_request)
        art_hash = str(gamma_request.get("art_direction_hash") or "")
        if not art_hash:
            raise media_v3.CampaignMediaError(f"Document Studio art direction is not bound for {surface}.")
        art_hashes[surface] = art_hash

        variant_dir = request_path.parent / "media" / surface
        voice_receipt = media_v3.synthesize_projected_story(
            scenes,
            variant_dir,
            dict(variant.get("voice") or {}),
            nichefoundry_root=nfr,
        )

        music_spec = dict(variant.get("music") or {})
        music: Path | None = None
        attribution = ""
        if music_spec.get("mode") == "rights_recorded":
            music = Path(str(music_spec.get("path") or "")).expanduser().resolve()
            attribution_path = Path(str(music_spec.get("attribution") or "")).expanduser().resolve()
            if not music.is_file() or not attribution_path.is_file():
                raise media_v3.CampaignMediaError(f"Rights-recorded music or attribution is missing for {surface}.")
            attribution = str(attribution_path)
        elif music_spec.get("mode") != "none":
            raise media_v3.CampaignMediaError(f"Projected music mode is invalid for {surface}: {music_spec.get('mode')}")

        output_spec = dict(variant.get("output") or {})
        output = Path(str(output_spec.get("path") or "")).expanduser().resolve()
        width = int(output_spec.get("width") or 0)
        height = int(output_spec.get("height") or 0)
        if width < 320 or height < 320:
            raise media_v3.CampaignMediaError(f"Projected output dimensions are invalid for {surface}.")

        rendered = render_cinematic_format(
            scene_images=images,
            narration=list(voice_receipt["scenes"]),
            music=music,
            music_volume=float(music_spec.get("volume") or 0.0),
            output=output,
            width=width,
            height=height,
        )
        variant_receipts[surface] = {
            "surface": surface,
            "story_hash": story.get("story_hash"),
            "art_direction_hash": art_hash,
            "visual_source": {
                "selected": "document_studio_local_compositor",
                "scene_count": len(images),
                "gamma_candidate": _gamma_candidate_state(variant),
            },
            "gamma": _gamma_candidate_state(variant),
            "voice": {
                "provider": voice_receipt["provider"],
                "voice": voice_receipt.get("voice") or voice_receipt.get("model"),
                "remote_tts_used": bool(voice_receipt.get("remote_tts_used")),
                "receipt": voice_receipt["receipt"],
            },
            "music": {**music_spec, "path": str(music) if music else "", "attribution": attribution},
            "output": rendered,
        }

    receipt = {
        "schema": "dio.campaign_media_receipt.v3",
        "family_id": request.get("family_id"),
        "request_hash": request.get("request_hash"),
        "semantic_law_hash": (request.get("semantic_law") or {}).get("semantic_law_hash"),
        "projection_hash": (request.get("projection") or {}).get("projection_hash"),
        "creative_fingerprint": (request.get("projection") or {}).get("creative_fingerprint"),
        "audience_archetype": (request.get("projection") or {}).get("audience_archetype"),
        "art_direction_hash": _hash(art_hashes),
        "art_direction_hashes": art_hashes,
        "created_at": media_v3.legacy.utc_now(),
        "state": "ready",
        "variants": variant_receipts,
        "outputs": {
            "vertical_reel": variant_receipts["vertical_short"]["output"],
            "long_form_explainer": variant_receipts["landscape_explainer"]["output"],
        },
        "governance": {
            "publication": "held_for_operator_approval",
            "spend": "disabled",
            "synthetic_media_review_required": True,
            "market_validation_claimed": False,
            "authority_created": False,
            "semantic_law_preserved": True,
            "document_studio_art_direction_bound": True,
            "document_studio_local_compositor_primary": True,
            "beast_visual_memory_bound": True,
            "gamma_required_for_media": False,
            "human_visual_release": "NEEDS_YOU",
        },
    }

    errors: list[str] = []
    for gamma_request in gamma_requests:
        errors.extend(validate_visual_contract(gamma_request, receipt))
    errors = sorted(set(errors))
    if errors:
        raise media_v3.CampaignMediaError(
            "Document Studio visual QA refused projected media: " + "; ".join(errors)
        )

    receipt["document_studio_visual_qa"] = {
        "state": "PASS",
        "errors": [],
        "art_direction_hash": receipt["art_direction_hash"],
        "layout_diversity": "PASS",
        "visible_copy_budget": "PASS",
        "narration_as_card_copy": "REFUSE",
        "static_slide_deck": "REFUSE",
        "motion_execution": "PASS",
        "local_compositor_primary": True,
        "gamma_required_for_media": False,
        "human_visual_release": "NEEDS_YOU",
    }
    output_path = request_path.parent / "media" / "CAMPAIGN_MEDIA_RECEIPT.json"
    _write_json(output_path, receipt)
    return receipt


def _install_build_family_wrapper(factory_module: Any) -> None:
    original = getattr(factory_module, "build_family")
    if getattr(original, "_dio_visual_spine_wrapper", False):
        return

    def build_family(product: dict[str, Any], audience: dict[str, Any], channels: dict[str, Any], output_root: Path, render_reels: bool) -> dict[str, Any]:
        # First build all semantic, copy, story, Document Studio art direction and local frames
        # without invoking the old Gamma-required media branch.
        family = original(product, audience, channels, output_root, False)
        if not render_reels:
            family.setdefault("gamma", {})["required_for_media"] = False
            family["gamma"]["state"] = "optional_not_requested"
            family["gamma"]["role"] = "optional_visual_candidate_provider"
            return family

        directory = output_root / factory_module.slug(product["id"]) / factory_module.slug(audience["id"])
        request_path = directory / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
        request = _read_json(request_path)

        gamma_enabled = str(os.environ.get("DIO_GAMMA_VISUAL_CANDIDATE") or "0").strip().casefold() in {"1", "true", "yes", "on"}
        gamma_states: dict[str, str] = {}
        gamma_errors: dict[str, str] = {}
        for surface, variant in (request.get("variants") or {}).items():
            gamma_request_path = Path(str((variant.get("gamma") or {}).get("request") or "")).expanduser().resolve()
            if gamma_enabled:
                state, error = run_art_directed_gamma(gamma_request_path)
            else:
                state, error = "optional_skipped", ""
            gamma_states[surface] = state
            gamma_errors[surface] = error

        media_error = ""
        media_receipt: dict[str, Any] = {}
        try:
            media_receipt = render_art_directed_campaign_media(request_path, nichefoundry_root=factory_module.FOUNDRY)
            media_state = str(media_receipt.get("state") or "ready")
        except Exception as exc:  # preserve exact failure truth at this top-level integration seam
            media_state = "failed"
            media_error = str(exc)[-2400:]

        family.setdefault("gamma", {})["required_for_media"] = False
        family["gamma"]["role"] = "optional_visual_candidate_provider"
        family["gamma"]["state"] = (
            "optional_ready" if gamma_enabled and all(state == "ready_optional" for state in gamma_states.values())
            else "optional_failed_nonblocking" if gamma_enabled and any(state == "failed_optional" for state in gamma_states.values())
            else "optional_skipped"
        )
        family["gamma"]["variants"] = {
            surface: {
                "state": gamma_states[surface],
                "request": factory_module.relative(Path((request["variants"][surface]["gamma"] or {})["request"])),
                "receipt": factory_module.relative(Path((request["variants"][surface]["gamma"] or {})["receipt"])) if Path((request["variants"][surface]["gamma"] or {})["receipt"]).is_file() else "",
                "error": gamma_errors[surface],
            }
            for surface in request.get("variants") or {}
        }
        family["gamma"]["error"] = " | ".join(error for error in gamma_errors.values() if error)

        voice_variants = media_receipt.get("variants") or {}
        family.setdefault("voice", {})["state"] = "ready" if media_state == "ready" else "failed"
        family["voice"]["providers"] = sorted({
            str((row.get("voice") or {}).get("provider") or "")
            for row in voice_variants.values()
            if (row.get("voice") or {}).get("provider")
        }) or family["voice"].get("providers", [])
        family["voice"]["receipts"] = {
            surface: str((row.get("voice") or {}).get("receipt") or "")
            for surface, row in voice_variants.items()
        }
        family.setdefault("piper", {})["state"] = family["voice"]["state"]

        family.setdefault("nichefoundry", {})["reel_state"] = media_state
        family["nichefoundry"]["long_form_state"] = media_state
        family["nichefoundry"]["reel_error"] = media_error
        media_receipt_path = directory / "media" / "CAMPAIGN_MEDIA_RECEIPT.json"
        family["nichefoundry"]["media_receipt"] = factory_module.relative(media_receipt_path) if media_receipt_path.is_file() else ""

        if media_state == "ready":
            for surface, variant in (request.get("variants") or {}).items():
                output = Path(str((variant.get("output") or {}).get("path") or "")).resolve()
                if surface == "vertical_short":
                    family.setdefault("assets", {})["reel_1080x1920"] = factory_module.relative(output)
                elif surface == "landscape_explainer":
                    family.setdefault("assets", {})["explainer_1920x1080"] = factory_module.relative(output)

        previous_errors = [
            error for error in (family.get("validation") or {}).get("errors") or []
            if "Gamma" not in str(error) and "gamma" not in str(error)
        ]
        validation_errors = previous_errors + ([media_error] if media_error else [])
        family["validation"] = {
            "state": "passed" if media_state == "ready" and not previous_errors else "failed",
            "errors": validation_errors,
            "warnings": [error for error in gamma_errors.values() if error],
        }
        family["visual_pipeline"] = {
            "primary_compositor": "document_studio_local_compositor",
            "art_direction": "document_studio",
            "visual_memory": "beast_representational_context_only",
            "motion_executor": "nichefoundry_ffmpeg_cinematic",
            "gamma": family["gamma"]["state"],
            "gamma_required_for_media": False,
            "human_visual_release": "NEEDS_YOU",
        }
        family.setdefault("governance", {})["document_studio_local_compositor_primary"] = True
        family["governance"]["gamma_required_for_media"] = False
        family["governance"]["beast_visual_memory_bound"] = True
        family["governance"]["human_visual_release"] = "NEEDS_YOU"

        factory_module.write_json(directory / "FAMILY.json", family)
        return family

    build_family._dio_visual_spine_wrapper = True  # type: ignore[attr-defined]
    factory_module.build_family = build_family


def install_visual_spine(factory_module: Any) -> None:
    """Install the governed visual spine into the active v3 factory without forking it."""
    if getattr(factory_module, "_dio_visual_spine_installed", False):
        return
    factory_module.build_gamma_story_request = build_art_directed_gamma_request
    # Gamma is optional; the factory wrapper decides whether to audition it.
    factory_module._run_gamma = run_art_directed_gamma
    factory_module.render_campaign_media_v3 = render_art_directed_campaign_media
    _install_build_family_wrapper(factory_module)
    factory_module._dio_visual_spine_installed = True
