from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from lingua.semantic_law import PROJECTION_INVARIANTS

PROJECTION_SCHEMA = "dio.lingua.product_projection.v1"

ARCHETYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("learner_support", ("parent", "learner", "school learner")),
    ("education_practitioner", ("teacher", "lecturer", "tutor", "education publisher", "school", "assessment coordinator")),
    ("academic_research", ("postgraduate", "research supervisor", "research office", "research group", "writing centre", "academic librar")),
    ("assurance", ("audit", "compliance", "monitoring", "evaluation", "grant manager", "evidence", "assurance")),
    ("executive_operations", ("hr", "performance administrator", "line manager", "hod", "institution leader", "organisation leader")),
    ("public_programme", ("ngo", "npo", "public programme", "government", "public-facing", "donor")),
    ("professional_services", ("consultant", "professional firm", "sme", "independent reporting")),
]

CHANNEL_STYLE = {
    "LINKEDIN_ORGANIC": {"tone": "credible_peer", "cta_style": "professional_next_step", "density": "medium"},
    "FACEBOOK_PAGE": {"tone": "human_practical", "cta_style": "low_friction", "density": "medium_low"},
    "META_ADS": {"tone": "clear_benefit", "cta_style": "direct", "density": "low"},
    "INSTAGRAM_ORGANIC": {"tone": "visual_human", "cta_style": "soft_direct", "density": "low"},
    "TIKTOK_ORGANIC": {"tone": "fast_conversational", "cta_style": "single_action", "density": "very_low"},
    "TIKTOK_ADS": {"tone": "fast_problem_solution", "cta_style": "single_action", "density": "very_low"},
    "REDDIT_ORGANIC": {"tone": "candid_specific", "cta_style": "discussion_first", "density": "medium"},
    "REDDIT_ADS": {"tone": "transparent_proof", "cta_style": "proof_first", "density": "medium"},
    "GOOGLE_ADS": {"tone": "high_intent_literal", "cta_style": "search_action", "density": "compressed"},
    "YOUTUBE_ORGANIC": {"tone": "documentary_explainer", "cta_style": "earned_next_step", "density": "medium"},
}

VERTICAL_PROFILES: dict[str, dict[str, Any]] = {
    "learner_support": {
        "arc_family": "question_to_clarity",
        "roles": ["question", "relatable_problem", "simple_demo", "result", "cta"],
        "tone": ["friendly", "clear", "encouraging"],
        "pacing": "fast_but_breathable",
        "visual_grammar": "bright_learning_editorial",
        "motion_grammar": "quick_punch_ins_and_clean_cuts",
        "voice": {"provider": "edge_tts", "voice": "en-ZA-LeahNeural", "presentation": "warm_peer", "remote_tts_allowed": True},
        "music": {"family": "bright_warm_learning", "keywords": ["warm", "bright", "learning", "optimistic"], "allow_silence": True, "volume": 0.09},
    },
    "education_practitioner": {
        "arc_family": "recognition_then_relief",
        "roles": ["cold_open", "recognition", "transformation", "proof", "human_gate", "cta"],
        "tone": ["warm", "quick", "slightly_playful", "respectful"],
        "pacing": "brisk",
        "visual_grammar": "energetic_education_editorial",
        "motion_grammar": "fast_cuts_punch_ins_and_screen_moments",
        "voice": {"provider": "edge_tts", "voice": "en-ZA-LeahNeural", "presentation": "trusted_colleague", "remote_tts_allowed": True},
        "music": {"family": "warm_upbeat", "keywords": ["warm", "sunset", "upbeat", "education"], "allow_silence": True, "volume": 0.10},
    },
    "academic_research": {
        "arc_family": "provocation_to_method",
        "roles": ["provocation", "source_problem", "method", "evidence", "limitation", "cta"],
        "tone": ["intelligent", "calm", "specific"],
        "pacing": "measured",
        "visual_grammar": "editorial_research_documentary",
        "motion_grammar": "measured_pushes_and_source_closeups",
        "voice": {"provider": "piper_local", "voice": "configured_local_model", "presentation": "calm_explainer", "remote_tts_allowed": False},
        "music": {"family": "minimal_documentary", "keywords": ["documentary", "minimal", "ambient", "research"], "allow_silence": True, "volume": 0.06},
    },
    "assurance": {
        "arc_family": "risk_reveal",
        "roles": ["red_flag", "consequence", "evidence_gap", "control_view", "human_gate", "cta"],
        "tone": ["precise", "restrained", "serious"],
        "pacing": "deliberate",
        "visual_grammar": "assurance_signal_noir",
        "motion_grammar": "slow_pushes_evidence_highlights_and_hard_cuts",
        "voice": {"provider": "edge_tts", "voice": "en-ZA-LukeNeural", "presentation": "restrained_authority", "remote_tts_allowed": True},
        "music": {"family": "restrained_investigative", "keywords": ["investigative", "technology", "restrained", "corporate"], "allow_silence": True, "volume": 0.055},
    },
    "executive_operations": {
        "arc_family": "cost_to_decision",
        "roles": ["cost_of_friction", "before", "after", "proof", "decision", "cta"],
        "tone": ["executive", "economical", "confident"],
        "pacing": "crisp",
        "visual_grammar": "executive_operating_brief",
        "motion_grammar": "clean_diagram_moves_and_selective_punch_ins",
        "voice": {"provider": "edge_tts", "voice": "en-ZA-LukeNeural", "presentation": "executive_briefing", "remote_tts_allowed": True},
        "music": {"family": "modern_low_key", "keywords": ["modern", "technology", "low key", "business"], "allow_silence": True, "volume": 0.05},
    },
    "public_programme": {
        "arc_family": "mission_to_trust",
        "roles": ["mission", "evidence_problem", "route", "proof", "trust_boundary", "cta"],
        "tone": ["human", "credible", "public_interest"],
        "pacing": "steady",
        "visual_grammar": "public_interest_documentary",
        "motion_grammar": "human_context_then_evidence_closeups",
        "voice": {"provider": "edge_tts", "voice": "en-ZA-LeahNeural", "presentation": "warm_public_service", "remote_tts_allowed": True},
        "music": {"family": "warm_documentary", "keywords": ["warm", "documentary", "hopeful", "community"], "allow_silence": True, "volume": 0.07},
    },
    "professional_services": {
        "arc_family": "client_moment",
        "roles": ["client_arrives", "mess", "first_pass", "professional_authority", "proof", "cta"],
        "tone": ["direct", "human", "capable"],
        "pacing": "brisk",
        "visual_grammar": "modern_client_workflow",
        "motion_grammar": "before_after_cuts_and_workflow_reveals",
        "voice": {"provider": "edge_tts", "voice": "en-ZA-LeahNeural", "presentation": "confident_peer", "remote_tts_allowed": True},
        "music": {"family": "clean_modern", "keywords": ["clean", "modern", "creative", "business"], "allow_silence": True, "volume": 0.075},
    },
    "general_professional": {
        "arc_family": "problem_to_proof",
        "roles": ["hook", "pain", "workflow", "proof", "human_gate", "cta"],
        "tone": ["clear", "professional", "human"],
        "pacing": "medium",
        "visual_grammar": "clean_professional_editorial",
        "motion_grammar": "simple_pushes_and_proof_closeups",
        "voice": {"provider": "piper_local", "voice": "configured_local_model", "presentation": "neutral_explainer", "remote_tts_allowed": False},
        "music": {"family": "minimal_neutral", "keywords": ["minimal", "ambient", "technology"], "allow_silence": True, "volume": 0.05},
    },
}

LANDSCAPE_ROLES: dict[str, list[str]] = {
    "learner_support": ["opening_question", "context", "simple_demo", "worked_example", "result", "human_role", "cta"],
    "education_practitioner": ["opening_problem", "day_in_the_life", "workflow_demo", "deliverable", "proof", "educator_authority", "cta"],
    "academic_research": ["research_question", "source_problem", "method", "worked_example", "evidence", "limitations", "reviewer_role", "cta"],
    "assurance": ["control_question", "evidence_state", "workflow_demo", "exception", "proof", "authority_boundary", "cta"],
    "executive_operations": ["operating_problem", "cost", "workflow_demo", "management_view", "proof", "decision_boundary", "cta"],
    "public_programme": ["mission_context", "reporting_problem", "evidence_route", "worked_example", "proof", "trust_boundary", "cta"],
    "professional_services": ["client_context", "intake_problem", "first_pass", "professional_workflow", "proof", "authority_boundary", "cta"],
    "general_professional": ["question", "problem", "workflow_demo", "proof", "boundary", "cta"],
}


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def audience_archetype(audience: dict[str, Any]) -> str:
    haystack = " ".join(str(audience.get(key) or "").casefold() for key in ("id", "name", "pain", "outcome"))
    for archetype, needles in ARCHETYPE_RULES:
        if any(needle in haystack for needle in needles):
            return archetype
    return "general_professional"


def _landscape_profile(vertical: dict[str, Any], archetype: str) -> dict[str, Any]:
    voice = dict(vertical["voice"])
    music = dict(vertical["music"])
    if archetype in {"academic_research", "assurance", "executive_operations"}:
        music["volume"] = max(0.035, float(music["volume"]) - 0.015)
    return {
        "arc_family": f"{archetype}_explainer",
        "roles": list(LANDSCAPE_ROLES[archetype]),
        "tone": list(vertical["tone"]),
        "pacing": "measured" if archetype in {"academic_research", "assurance"} else "steady",
        "visual_grammar": vertical["visual_grammar"],
        "motion_grammar": "documentary_pushes_diagrams_and_evidence_closeups",
        "voice": voice,
        "music": music,
    }


def build_projection_plan(law: dict[str, Any], product: dict[str, Any], audience: dict[str, Any], channels: dict[str, Any]) -> dict[str, Any]:
    archetype = audience_archetype(audience)
    vertical = dict(VERTICAL_PROFILES[archetype])
    vertical["roles"] = list(vertical["roles"])
    vertical["tone"] = list(vertical["tone"])
    vertical["voice"] = dict(vertical["voice"])
    vertical["music"] = dict(vertical["music"])
    landscape = _landscape_profile(vertical, archetype)
    channel_projections = {
        channel_id: {**CHANNEL_STYLE.get(channel_id, {"tone": "clear_professional", "cta_style": "direct", "density": "medium"}), "format": str(channel.get("format") or "")}
        for channel_id, channel in channels.items()
    }
    plan_core = {
        "schema": PROJECTION_SCHEMA,
        "semantic_law_hash": law["semantic_law_hash"],
        "source_hash": law["source_hash"],
        "product_id": str(product.get("id") or ""),
        "audience_id": str(audience.get("id") or ""),
        "audience_archetype": archetype,
        "preserves": list(PROJECTION_INVARIANTS),
        "surfaces": {"vertical_short": vertical, "landscape_explainer": landscape},
        "channel_projections": channel_projections,
        "governance": {
            "publication": "held",
            "spend": "disabled",
            "market_validation_claimed": False,
            "authority_created": False,
            "creative_adaptation_is_market_validation": False,
        },
    }
    fingerprint_core = {
        "archetype": archetype,
        "vertical": {"arc": vertical["arc_family"], "roles": vertical["roles"], "voice": vertical["voice"], "music_family": vertical["music"]["family"], "visual": vertical["visual_grammar"], "pacing": vertical["pacing"]},
        "landscape": {"arc": landscape["arc_family"], "roles": landscape["roles"], "voice": landscape["voice"], "music_family": landscape["music"]["family"], "visual": landscape["visual_grammar"], "pacing": landscape["pacing"]},
    }
    plan_core["creative_fingerprint"] = _canonical_hash(fingerprint_core)
    return {**plan_core, "projection_hash": _canonical_hash(plan_core)}


def creative_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    dimensions: list[tuple[Any, Any]] = [
        (left.get("audience_archetype"), right.get("audience_archetype")),
        (left.get("surfaces", {}).get("vertical_short", {}).get("arc_family"), right.get("surfaces", {}).get("vertical_short", {}).get("arc_family")),
        (left.get("surfaces", {}).get("vertical_short", {}).get("roles"), right.get("surfaces", {}).get("vertical_short", {}).get("roles")),
        (left.get("surfaces", {}).get("vertical_short", {}).get("voice"), right.get("surfaces", {}).get("vertical_short", {}).get("voice")),
        (left.get("surfaces", {}).get("vertical_short", {}).get("music", {}).get("family"), right.get("surfaces", {}).get("vertical_short", {}).get("music", {}).get("family")),
        (left.get("surfaces", {}).get("vertical_short", {}).get("visual_grammar"), right.get("surfaces", {}).get("vertical_short", {}).get("visual_grammar")),
        (left.get("surfaces", {}).get("landscape_explainer", {}).get("roles"), right.get("surfaces", {}).get("landscape_explainer", {}).get("roles")),
        (left.get("surfaces", {}).get("landscape_explainer", {}).get("pacing"), right.get("surfaces", {}).get("landscape_explainer", {}).get("pacing")),
    ]
    return round(sum(a != b for a, b in dimensions) / len(dimensions), 3)


def _shorten(value: str, limit: int) -> str:
    clean = " ".join(str(value or "").split())
    if len(clean) <= limit:
        return clean
    clipped = clean[: max(1, limit - 1)].rsplit(" ", 1)[0]
    return (clipped or clean[: limit - 1]).rstrip(".,;:") + "…"


def _scene_content(role: str, product: dict[str, Any], audience: dict[str, Any], *, long_form: bool) -> tuple[str, str, str]:
    name = str(product.get("short_name") or product.get("name") or "DIO")
    pain = str(audience.get("pain") or "")
    outcome = str(audience.get("outcome") or "")
    promise = str(product.get("promise") or "")
    proof = str(product.get("proof") or "")
    cta = str(product.get("cta") or "")
    audience_name = str(audience.get("name") or "this audience")
    mapping: dict[str, tuple[str, str, str]] = {
        "cold_open": ("Still doing this by hand?", pain, "Start inside the real working moment, not with a logo or product diagram."),
        "recognition": ("That friction is the job", f"For {audience_name}, this is not a lack-of-effort problem. It is a workflow problem that keeps consuming specialist time.", "Use recognisable work fragments, inboxes, documents, marking, evidence or handoffs."),
        "transformation": ("What changes?", f"{name} is designed to {promise[:1].lower() + promise[1:] if promise else outcome.lower()}", "Reveal the transformation through action, not an abstract architecture slide."),
        "proof": ("Show the proof", proof, "Use the actual proof object, bounded evidence state or real product surface. No fictional customer outcome."),
        "human_gate": ("You still decide", "The system prepares the work for review. Human authority stays intact, and publication or spend remains held.", "Show the human decision point without turning governance into a corporate disclaimer slide."),
        "cta": (_shorten(cta, 72), f"If that is the job you need solved, {cta.rstrip('.').lower()}.", "End with one concrete next action, visually simple and uncluttered."),
        "question": (_shorten(outcome, 72), f"What would it change if {outcome[:1].lower() + outcome[1:] if outcome else 'this workflow became easier to review'}?", "Open with a human question and an outcome image."),
        "relatable_problem": ("Here is the snag", pain, "Show a familiar everyday obstacle rather than a systems diagram."),
        "simple_demo": ("Watch the workflow", f"Here is the simple move: {promise}", "Use one clear before-to-after demonstration."),
        "result": ("What you get", outcome, "Show the bounded finished state and keep the reviewer or educator visible."),
        "provocation": ("More sources ≠ stronger work", pain, "Open with an intellectually provocative but source-safe statement."),
        "source_problem": ("Where does the claim come from?", pain, "Use manuscript, citation and source-detail imagery."),
        "method": ("Trace it, then judge it", f"{name} separates source checking, structure and human judgement. {promise}", "Show a method unfolding step by step."),
        "evidence": ("Evidence, not vibes", proof, "Put the source-bound proof on screen with readable highlights."),
        "limitation": ("The author stays the author", "Review can surface gaps and inconsistencies, but it does not replace authorship, supervision or academic judgement.", "Use restrained visual language and an explicit human handoff."),
        "red_flag": ("Can you prove that control claim?", pain, "Open on a specific exception, missing trace or evidence question."),
        "consequence": ("Review time disappears here", f"When {pain[:1].lower() + pain[1:] if pain else 'evidence cannot be traced'}, teams spend review time reconstructing the story instead of judging it.", "Use a tight evidence-to-review visual sequence."),
        "evidence_gap": ("Make the gap visible", f"{name} is designed to {promise[:1].lower() + promise[1:] if promise else outcome.lower()}", "Show missing evidence and matched evidence as distinct states."),
        "control_view": ("One reviewable control view", outcome, "Use structured evidence views, exceptions and provenance rather than generic business graphics."),
        "cost_of_friction": ("How much management time goes here?", pain, "Lead with operational drag and decision delay."),
        "before": ("Before", pain, "Show the fragmented operating state with minimal text."),
        "after": ("After", outcome, "Show the concise review state and decision surface."),
        "decision": ("Prepare the decision. Do not automate it.", "The workflow can prepare evidence and options, but the manager keeps consequential judgement.", "Make the manager or reviewer the final visual anchor."),
        "mission": ("The mission is not the paperwork", outcome, "Open with the human or programme outcome, then reveal the reporting burden."),
        "evidence_problem": ("The evidence is everywhere", pain, "Use field, programme and document context together."),
        "route": ("Turn activity into a trace", f"{name} is designed to {promise[:1].lower() + promise[1:] if promise else outcome.lower()}", "Show evidence moving into a traceable route."),
        "trust_boundary": ("Trust needs a trail", "The pack can make evidence reviewable. It does not certify the programme, invent donor acceptance or publish anything by itself.", "Show provenance and human approval as trust signals."),
        "client_arrives": ("The client sends… everything", pain, "Open with an authentic client-intake moment."),
        "mess": ("First, tame the mess", "The first job is not magic. It is turning the input into something a professional can actually inspect.", "Use a fast before-to-structure reveal."),
        "first_pass": ("A serious first pass", f"{name} is designed to {promise[:1].lower() + promise[1:] if promise else outcome.lower()}", "Show the prepared work, not fake finished-client success."),
        "professional_authority": ("Your judgement stays yours", "The workflow prepares and traces the work. The professional remains responsible for the consequential decision.", "Keep the practitioner visibly in control."),
    }
    aliases = {
        "opening_question": "question", "context": "relatable_problem", "worked_example": "simple_demo", "human_role": "human_gate",
        "opening_problem": "cold_open", "day_in_the_life": "recognition", "workflow_demo": "method", "deliverable": "result", "educator_authority": "human_gate",
        "research_question": "provocation", "limitations": "limitation", "reviewer_role": "human_gate", "control_question": "red_flag", "evidence_state": "evidence_gap",
        "exception": "consequence", "authority_boundary": "human_gate", "operating_problem": "cost_of_friction", "cost": "consequence", "management_view": "result",
        "decision_boundary": "decision", "mission_context": "mission", "reporting_problem": "evidence_problem", "evidence_route": "route", "client_context": "client_arrives",
        "intake_problem": "mess", "professional_workflow": "first_pass", "hook": "cold_open", "pain": "relatable_problem", "workflow": "method", "boundary": "human_gate",
    }
    key = aliases.get(role, role)
    screen, narration, visual = mapping.get(key, (_shorten(outcome or name, 72), promise or pain or outcome, "Use one audience-specific visual idea with minimal display text."))
    if long_form and role not in {"cta", "human_gate", "authority_boundary", "decision_boundary"}:
        narration = narration.rstrip(".") + f". The bounded outcome is: {outcome.rstrip('.')}."
    return _shorten(screen, 78), narration, visual


def project_story(law: dict[str, Any], projection: dict[str, Any], product: dict[str, Any], audience: dict[str, Any], surface: str) -> dict[str, Any]:
    surface_plan = dict((projection.get("surfaces") or {}).get(surface) or {})
    if not surface_plan:
        raise ValueError(f"Projection surface not defined: {surface}")
    roles = list(surface_plan.get("roles") or [])
    if len(roles) < 3:
        raise ValueError(f"Projection surface {surface} must contain at least three story roles")
    scenes = []
    long_form = surface == "landscape_explainer"
    for index, role in enumerate(roles, 1):
        screen_text, narration, visual = _scene_content(role, product, audience, long_form=long_form)
        scenes.append({"scene_id": f"{surface}_{index:02d}_{role}", "role": role, "screen_text": screen_text, "narration": narration, "visual": visual})
    core = {
        "schema": "dio.marketing.campaign_story.v2",
        "family_id": f"{product['id']}--{audience['id']}",
        "surface": surface,
        "title": f"{product['short_name']} for {audience['name']} · {surface.replace('_', ' ')}",
        "product": product["id"],
        "audience": audience["name"],
        "semantic_law_hash": law["semantic_law_hash"],
        "projection_hash": projection["projection_hash"],
        "arc_family": surface_plan["arc_family"],
        "arc": [scene["role"] for scene in scenes],
        "scenes": scenes,
        "creative_direction": {
            "audience_archetype": projection["audience_archetype"],
            "tone": surface_plan["tone"],
            "pacing": surface_plan["pacing"],
            "visual_grammar": surface_plan["visual_grammar"],
            "motion_grammar": surface_plan["motion_grammar"],
            "voice": surface_plan["voice"],
            "music": surface_plan["music"],
        },
        "semantic_guardrails": {"must_preserve": list(PROJECTION_INVARIANTS), "do_not_invent": list((law.get("prohibition") or {}).get("rules") or [])},
        "governance": {"publication": "held", "spend": "disabled", "operator_approval_required": True, "market_validation_claimed": False, "authority_created": False},
    }
    return {**core, "story_hash": _canonical_hash(core)}
