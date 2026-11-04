"""Explain how a music bed supports a narrated video or ad brief.

The direction is about editorial function. Rights and byte verification remain
the responsibility of the media catalog selector.
"""
from __future__ import annotations

from typing import Any, Mapping


FAMILY_DIRECTION = {
    "bright_warm_learning": ("warm", "hopeful", 2),
    "warm_upbeat": ("warm", "hopeful", 2),
    "minimal_documentary": ("calm", "reflective", 1),
    "restrained_investigative": ("serious", "tense", 1),
    "modern_low_key": ("confident", "restrained", 1),
    "warm_documentary": ("warm", "hopeful", 1),
    "clean_modern": ("confident", "hopeful", 2),
    "minimal_neutral": ("calm", "restrained", 1),
}


def direction_for_video(surface_plan: Mapping[str, Any]) -> dict[str, Any]:
    music = surface_plan.get("music") or {}
    family = str(music.get("family") or "minimal_neutral")
    mood, arc, energy = FAMILY_DIRECTION.get(family, ("calm", "restrained", 1))
    pacing = str(surface_plan.get("pacing") or "medium")
    if pacing in {"brisk", "fast_but_breathable"}:
        energy = max(energy, 2)
    if pacing in {"measured", "deliberate"}:
        energy = min(energy, 1)
    return {
        "schema": "dio.sonoris.video_music_direction.v1",
        "family": family,
        "role": "support_narration_and_scene_transitions",
        "mood": mood,
        "arc": arc,
        "energy": energy,
        "pacing": pacing,
        "voice_first": bool(surface_plan.get("voice", {}).get("required", True)),
        "musical_function": {
            "composition": "follow the scene arc and leave space at proof and call-to-action beats",
            "genre": "chosen for message and audience, never copied from an unrelated composition",
            "timbre": "prefer sparse layers beneath narration",
            "tone": mood,
            "rhythm": "reinforce edit cadence without masking words",
            "tempo": "match perceived edit pace; exact BPM requires track analysis",
            "beat": "use accents at scene changes when the arrangement supports them",
            "attack": "keep transients below speech emphasis",
            "gain": float(music.get("volume", .10)),
            "tuning": "no pitch or tuning requirement unless the brief supplies one",
        },
        "avoid": ["dense_lead_over_voice", "abrupt_unmotivated_transitions"],
        "source": "lingua_surface_music_and_edit_pacing",
    }


def score_track(direction: Mapping[str, Any], track: Mapping[str, Any]) -> dict[str, Any]:
    """Score declared musical traits; unknown traits never become measured facts."""
    traits = track.get("music_traits") or {}
    mood = str(direction["mood"])
    arc = str(direction["arc"])
    energy = int(direction["energy"])
    moods = set(traits.get("moods") or [])
    arcs = set(traits.get("arcs") or [])
    track_energy = traits.get("energy")
    voice_space = traits.get("voice_space")
    components: dict[str, int] = {}
    components["mood"] = 4 if mood in moods else 0
    components["arc"] = 3 if arc in arcs else 0
    components["energy"] = max(0, 3 - 2 * abs(energy - int(track_energy))) if track_energy is not None else 0
    components["narration_space"] = 3 if direction["voice_first"] and voice_space == "high" else (1 if voice_space == "medium" else 0)
    reasons = [name for name, points in components.items() if points]
    score = sum(components.values())
    return {
        "score": score,
        "components": components,
        "reasons": reasons,
        "fit_state": "EDITORIAL_REVIEW_REQUIRED" if score < 8 or (direction["voice_first"] and voice_space == "low") else "PLAUSIBLE_BED_REVIEW_REQUIRED",
        "traits_source": "curated_catalog_declaration" if traits else "unknown",
    }
