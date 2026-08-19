from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from adapters.document_studio.art_direction import build_art_direction
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


def _apply_approved_visual_crystals(art: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    """Apply only allow-listed representational fields from human-approved BEAST crystals."""
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
    updated.setdefault("beast_visual_memory", {})["applied_crystals"] = applied
    updated["beast_visual_memory"]["authority"] = "representational_context_only"
    core = {key: value for key, value in updated.items() if key != "art_direction_hash"}
    updated["art_direction_hash"] = _hash(core)
    return updated


def build_art_directed_gamma_request(story: dict[str, Any], directory: Path) -> dict[str, Any]:
    direction = dict(story.get("creative_direction") or {})
    archetype = str(direction.get("audience_archetype") or "general_professional")
    surface = str(story.get("surface") or "campaign_story")
    visual_grammar = str(direction.get("visual_grammar") or "")
    memory = resolve_visual_memory(
        audience_archetype=archetype,
        surface=surface,
        visual_grammar=visual_grammar,
    )
    art = _apply_approved_visual_crystals(build_art_direction(story, beast_memory=memory), memory)
    art_path = directory / f"DOCUMENT_STUDIO_ART_DIRECTION_{surface.upper()}.json"
    _write_json(art_path, art)

    # CRITICAL: Gamma receives display copy only. Narration remains an audio asset.
    # Visual instructions travel in structured creative_direction metadata where they
    # cannot be mistaken for body copy that must be painted onto the frame.
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
        },
        "semantic_guardrails": story["semantic_guardrails"],
        "output_dir": str((directory / "gamma" / surface).resolve()),
        "release": {"state": "held", "visual_review_required": True, "operator_approval_required": True},
    }
    payload["request_hash"] = _hash(payload)
    return payload


def run_art_directed_gamma(path: Path) -> tuple[str, str]:
    completed = subprocess.run(
        ["node", str(ROOT / "scripts" / "run_gamma_art_directed_story.js"), str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=540,
    )
    if completed.returncode != 0:
        return "failed", (completed.stderr or completed.stdout or "Art-directed Gamma campaign story failed").strip()[-2400:]
    return "ready", ""


def install_visual_spine(factory_module: Any) -> None:
    """Install the governed visual spine into the active v3 factory without forking it."""
    from scripts import build_campaign_media_v3 as media_v3

    factory_module.build_gamma_story_request = build_art_directed_gamma_request
    factory_module._run_gamma = run_art_directed_gamma
    media_v3._render_projected_format = render_cinematic_format
    factory_module.render_campaign_media_v3 = media_v3.render_campaign_media_v3
