from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config" / "format_profiles.json"
SCHEMA = "dio.document_studio.art_direction.v1"

ANTI_PATTERNS = [
    "four_quadrant_saas_card_grid",
    "repeated_photo_left_text_right",
    "body_paragraphs_on_video_frames",
    "tiny_governance_footer_text",
    "generic_white_grey_corporate_canvas",
    "default_gradient_wallpaper",
    "same_layout_on_adjacent_scenes",
    "fake_dashboard_ui_without_source_surface",
    "static_slide_deck_as_video",
    "decorative_diagram_without_visual_story_function",
]

ARCHETYPE_ART: dict[str, dict[str, Any]] = {
    "education_practitioner": {
        "style_profile": "caps_educator",
        "aesthetic": "human editorial warmth with tactile educator reality",
        "palette_behavior": "warm amber practical light, paper whites, ink blacks, selective cobalt accents; never grey SaaS wash",
        "photography": "observational documentary, real desks, hands, marked paper, imperfect working surfaces, shallow depth, human presence",
        "typography": "bold editorial display type with extreme hierarchy; one short thought per frame; generous negative space",
        "texture": "paper grain, pen marks, highlighter, subtle photocopy or notebook texture where semantically relevant",
        "proof_treatment": "macro crop of the actual evidence object, annotations or product surface; proof is photographed or isolated, not boxed into a dashboard",
        "rhythm": "alternate immersive human frames, tactile evidence closeups, spatial workflow moments and clean release frames",
        "layout_sequence": [
            "cinematic_full_bleed_human",
            "editorial_observation_collage",
            "tactile_process_reveal",
            "macro_deliverable_closeup",
            "evidence_annotation_frame",
            "human_authority_portrait",
            "single_statement_brand_release",
        ],
        "motion_sequence": [
            "slow_push_into_late_night_work",
            "lateral_observational_drift",
            "guided_process_pan",
            "macro_push_into_detail",
            "annotation_parallax",
            "restrained_portrait_push",
            "clean_resolve_with_subtle_scale",
        ],
    },
    "assurance": {
        "style_profile": "dio_professional",
        "aesthetic": "forensic editorial tension with evidence as the visual protagonist",
        "palette_behavior": "deep charcoal, paper white, restrained signal red and electric blue only for evidence state; no cheerful corporate gradient",
        "photography": "macro evidence, audit marks, controlled environments, hands tracing records, sparse human context",
        "typography": "condensed or bold editorial hierarchy, terse labels, high contrast, no explanatory paragraphs",
        "texture": "scan grain, document edge, timestamp, annotation, controlled signal noise",
        "proof_treatment": "evidence gap versus verified evidence shown through real objects, highlights, callouts and provenance marks",
        "rhythm": "tension, consequence, evidence gap, controlled reveal, proof closeup, human judgement, hard resolve",
        "layout_sequence": [
            "forensic_full_bleed_hook",
            "consequence_evidence_split",
            "missing_trace_negative_space",
            "controlled_workflow_map",
            "macro_proof_closeup",
            "authority_boundary_portrait",
            "hard_resolve_cta",
        ],
        "motion_sequence": [
            "slow_forensic_push",
            "hard_cut_then_micro_pan",
            "negative_space_hold_with_drift",
            "guided_line_trace",
            "macro_push_into_proof",
            "restrained_portrait_push",
            "hard_resolve",
        ],
    },
    "academic_research": {
        "style_profile": "institutional_academic",
        "aesthetic": "research documentary with source material, marginalia and method as visual structure",
        "palette_behavior": "paper neutrals, graphite, deep ink, one scholarly accent; avoid startup blue gradients",
        "photography": "books, manuscripts, source excerpts, researcher hands, screens only when they contain meaningful evidence",
        "typography": "serif/sans editorial contrast, restrained display headlines, source-like captions only where useful",
        "texture": "paper, marginalia, citation marks, archival grain",
        "proof_treatment": "sources and claim lineage shown as readable evidence fragments rather than abstract boxes",
        "rhythm": "provocation, source encounter, method, worked evidence, limitation, reviewer handoff",
        "layout_sequence": [
            "editorial_provocation",
            "source_material_full_bleed",
            "method_diagram_over_material",
            "worked_evidence_closeup",
            "limitation_negative_space",
            "reviewer_handoff_portrait",
            "quiet_scholarly_resolve",
        ],
        "motion_sequence": [
            "slow_editorial_push",
            "source_pan",
            "guided_method_trace",
            "macro_evidence_push",
            "restrained_hold",
            "portrait_push",
            "quiet_resolve",
        ],
    },
    "learner_support": {
        "style_profile": "caps_educator",
        "aesthetic": "bright human learning editorial, curious rather than childish",
        "palette_behavior": "warm daylight, saturated real-world colour and one clean accent; avoid sterile white cards",
        "photography": "hands-on learning, notebooks, diagrams, human reaction, simple objects and worked examples",
        "typography": "large friendly editorial display, tiny text budget, visual answer before explanation",
        "texture": "notebook, marker, simple physical materials",
        "proof_treatment": "worked example or result shown as the hero object",
        "rhythm": "question, relatable snag, tactile demo, result, human next step",
        "layout_sequence": [
            "curiosity_full_bleed",
            "relatable_object_scene",
            "hands_on_demo",
            "result_hero",
            "human_next_step",
            "bright_resolve",
        ],
        "motion_sequence": ["quick_push", "object_pan", "guided_demo", "result_pop", "human_push", "clean_resolve"],
    },
    "executive_operations": {
        "style_profile": "dio_professional",
        "aesthetic": "premium operating brief with real work surfaces and decisive information hierarchy",
        "palette_behavior": "dark ink, warm neutral material, restrained accent; no template-dashboard wallpaper",
        "photography": "operational environments, real documents, people making decisions, close details of work",
        "typography": "high-impact sparse headlines with disciplined numeric or proof callouts",
        "texture": "material surfaces, glass, paper, subtle grid only when data requires it",
        "proof_treatment": "one decision-relevant object or metric per frame",
        "rhythm": "cost, friction, transformation, proof, decision, resolve",
        "layout_sequence": ["operating_hook", "friction_environment", "process_reveal", "proof_hero", "decision_portrait", "premium_resolve"],
        "motion_sequence": ["slow_push", "lateral_drift", "guided_pan", "proof_push", "portrait_push", "resolve"],
    },
    "public_programme": {
        "style_profile": "dio_professional",
        "aesthetic": "public-interest documentary with human mission before administration",
        "palette_behavior": "natural location colour, warm skin tones, paper/evidence neutrals, restrained institutional accent",
        "photography": "people, places, programme activity, field evidence and reporting objects in context",
        "typography": "human documentary titling, sparse copy, evidence labels only when earned",
        "texture": "field material, paper, maps, environmental context",
        "proof_treatment": "show the trail from activity to evidence without turning it into a corporate dashboard",
        "rhythm": "mission, burden, route, evidence, trust boundary, next step",
        "layout_sequence": ["mission_full_bleed", "field_context", "evidence_route", "worked_proof", "trust_handoff", "human_resolve"],
        "motion_sequence": ["documentary_push", "context_pan", "route_trace", "proof_push", "human_hold", "resolve"],
    },
    "professional_services": {
        "style_profile": "dio_professional",
        "aesthetic": "modern client-work editorial with tactile before-and-after transformation",
        "palette_behavior": "warm neutral workspace, dark ink, one confident accent; no generic consultancy slideware",
        "photography": "client inputs, practitioner hands, messy source material becoming clean reviewable work",
        "typography": "confident editorial display, minimal supporting copy",
        "texture": "paper stacks, folders, screen details, marks and annotations",
        "proof_treatment": "show the prepared professional work as a tangible artifact",
        "rhythm": "arrival, mess, transformation, practitioner judgement, proof, next step",
        "layout_sequence": ["client_arrival_full_bleed", "mess_collage", "transformation_reveal", "practitioner_portrait", "proof_hero", "client_resolve"],
        "motion_sequence": ["push", "collage_drift", "reveal_pan", "portrait_push", "proof_push", "resolve"],
    },
    "general_professional": {
        "style_profile": "dio_professional",
        "aesthetic": "editorial human workflow, proof-led and non-template",
        "palette_behavior": "context-native colour with one controlled accent; avoid white-grey SaaS defaults",
        "photography": "real work, hands, objects, environment, evidence closeups",
        "typography": "large sparse editorial headlines, no paragraphs",
        "texture": "material and evidence native to the work",
        "proof_treatment": "one concrete proof object per proof scene",
        "rhythm": "problem, context, transformation, proof, human decision, resolve",
        "layout_sequence": ["full_bleed_hook", "context_observation", "process_reveal", "proof_closeup", "human_handoff", "clean_resolve"],
        "motion_sequence": ["push", "pan", "guided_reveal", "macro_push", "portrait_push", "resolve"],
    },
}


def _hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _load_format_profile(profile_id: str) -> tuple[dict[str, Any], str]:
    registry = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile = dict((registry.get("styles") or {}).get(profile_id) or {})
    if not profile:
        raise ValueError(f"Unknown Document Studio / Format Core style profile: {profile_id}")
    return profile, _hash(profile)


def _display_copy(value: str, max_words: int) -> str:
    words = " ".join(str(value or "").split()).split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(".,;:") + "…"


def build_art_direction(
    story: dict[str, Any],
    *,
    beast_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    direction = dict(story.get("creative_direction") or {})
    archetype = str(direction.get("audience_archetype") or "general_professional")
    profile = dict(ARCHETYPE_ART.get(archetype) or ARCHETYPE_ART["general_professional"])
    format_profile, format_profile_hash = _load_format_profile(str(profile["style_profile"]))
    scenes = list(story.get("scenes") or [])
    layouts = list(profile["layout_sequence"])
    motions = list(profile["motion_sequence"])
    scene_rows: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        layout = layouts[index % len(layouts)]
        motion = motions[index % len(motions)]
        max_words = 5 if story.get("surface") == "vertical_short" else 8
        role = str(scene.get("role") or "scene")
        scene_rows.append({
            "scene_id": str(scene.get("scene_id") or f"scene_{index + 1:02d}"),
            "role": role,
            "layout_family": layout,
            "motion_treatment": motion,
            "display_copy": _display_copy(str(scene.get("screen_text") or ""), max_words),
            "max_display_words": max_words,
            "visual_subject": str(scene.get("visual") or ""),
            "composition_rule": "one dominant visual idea; image first; typography supports rather than explains",
            "text_rule": "never render narration, semantic guardrails or governance prose on the frame",
        })

    memory = dict(beast_memory or {})
    core = {
        "schema": SCHEMA,
        "source_story_hash": story.get("story_hash"),
        "semantic_law_hash": story.get("semantic_law_hash"),
        "projection_hash": story.get("projection_hash"),
        "surface": story.get("surface"),
        "audience_archetype": archetype,
        "format_core_profile": profile["style_profile"],
        "format_core_profile_hash": format_profile_hash,
        "format_core_palette": format_profile.get("colours") or {},
        "art_language": {
            "aesthetic": profile["aesthetic"],
            "palette_behavior": profile["palette_behavior"],
            "photography": profile["photography"],
            "typography": profile["typography"],
            "texture": profile["texture"],
            "proof_treatment": profile["proof_treatment"],
            "rhythm": profile["rhythm"],
        },
        "anti_patterns": list(ANTI_PATTERNS),
        "scenes": scene_rows,
        "beast_visual_memory": {
            "state": str(memory.get("state") or "no_approved_visual_crystal"),
            "approved_crystal_refs": list(memory.get("approved_crystal_refs") or []),
            "negative_patterns": list(memory.get("negative_patterns") or []),
            "memory_hull_refs": list(memory.get("memory_hull_refs") or []),
            "authority": "representational_context_only",
        },
        "governance": {
            "semantic_meaning_may_change": False,
            "visual_representation_may_change": True,
            "beast_memory_can_mint_authority": False,
            "document_studio_role": "art_direction_compiler_local_compositor_and_visual_qa",
            "primary_visual_compositor": "document_studio_local_compositor",
            "gamma_role": "optional_visual_candidate_only",
            "gamma_required_for_media": False,
            "motion_and_media_executor": "nichefoundry",
            "human_visual_release": "NEEDS_YOU",
            "publication": "held",
            "spend": "disabled",
        },
    }
    return {**core, "art_direction_hash": _hash(core)}
