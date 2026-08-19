from __future__ import annotations

from pathlib import Path

import operator_production
from lingua.product_projection import build_projection_plan, creative_distance, project_story
from lingua.semantic_law import build_semantic_law, validate_projection

ROOT = Path(__file__).resolve().parents[1]


def _product() -> dict[str, str]:
    return {
        "id": "HOMS_ASSESS",
        "name": "HOMS Assessment Desk",
        "short_name": "HOMS",
        "offer": "assessment_desk",
        "promise": "Prepare marking, feedback and assessment material for educator review.",
        "proof": "A controlled route produces reviewable marking while the educator remains final authority.",
        "cta": "Send one controlled assessment batch",
    }


def _channels() -> dict[str, dict[str, str]]:
    return {
        "TIKTOK_ORGANIC": {"format": "vertical_reel"},
        "YOUTUBE_ORGANIC": {"format": "short_and_explainer"},
        "LINKEDIN_ORGANIC": {"format": "professional_post"},
    }


def _teacher() -> dict[str, str]:
    return {
        "id": "teachers_lecturers",
        "name": "Teachers and lecturers",
        "pain": "Marking, feedback and paper preparation consume evenings and weekends.",
        "outcome": "Structured drafts and learner feedback ready for educator review.",
    }


def _auditor() -> dict[str, str]:
    return {
        "id": "compliance_audit",
        "name": "Compliance and audit teams",
        "pain": "Review preparation consumes hours of manual searching and cross-checking.",
        "outcome": "A bounded evidence index with gaps made visible before review.",
    }


def test_m1_semantic_law_binds_four_dimensions_and_never_mints_authority() -> None:
    law = build_semantic_law(_product(), _teacher())
    assert set(("denotation", "affordance", "prohibition", "projection")) <= set(law)
    assert law["projection"]["law"] == "same meaning, different lawful skin"
    assert law["prohibition"]["publication_authorized"] is False
    assert law["prohibition"]["spend_authorized"] is False
    assert law["prohibition"]["market_validation_claimed"] is False
    assert law["prohibition"]["authority_created"] is False
    assert "claim_stronger_than_source_bound_product_promise" in law["prohibition"]["rules"]


def test_teacher_and_auditor_receive_materially_different_creative_projections() -> None:
    product = _product()
    teacher_law = build_semantic_law(product, _teacher())
    auditor_law = build_semantic_law(product, _auditor())
    teacher = build_projection_plan(teacher_law, product, _teacher(), _channels())
    auditor = build_projection_plan(auditor_law, product, _auditor(), _channels())

    assert validate_projection(teacher_law, teacher) == []
    assert validate_projection(auditor_law, auditor) == []
    assert teacher["audience_archetype"] == "education_practitioner"
    assert auditor["audience_archetype"] == "assurance"
    assert teacher["creative_fingerprint"] != auditor["creative_fingerprint"]
    assert teacher["surfaces"]["vertical_short"]["arc_family"] == "recognition_then_relief"
    assert auditor["surfaces"]["vertical_short"]["arc_family"] == "risk_reveal"
    assert teacher["surfaces"]["vertical_short"]["voice"]["voice"] == "en-ZA-LeahNeural"
    assert auditor["surfaces"]["vertical_short"]["voice"]["voice"] == "en-ZA-LukeNeural"
    assert teacher["surfaces"]["vertical_short"]["music"]["family"] != auditor["surfaces"]["vertical_short"]["music"]["family"]
    assert teacher["surfaces"]["vertical_short"]["visual_grammar"] != auditor["surfaces"]["vertical_short"]["visual_grammar"]
    assert creative_distance(teacher, auditor) >= 0.75


def test_short_form_and_explainer_are_distinct_lawful_projections() -> None:
    product = _product()
    audience = _teacher()
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, _channels())
    short_story = project_story(law, projection, product, audience, "vertical_short")
    long_story = project_story(law, projection, product, audience, "landscape_explainer")

    assert short_story["semantic_law_hash"] == long_story["semantic_law_hash"] == law["semantic_law_hash"]
    assert short_story["projection_hash"] == long_story["projection_hash"] == projection["projection_hash"]
    assert short_story["arc_family"] != long_story["arc_family"]
    assert short_story["arc"] != long_story["arc"]
    assert len(short_story["scenes"]) != len(long_story["scenes"])
    for story in (short_story, long_story):
        assert story["governance"]["publication"] == "held"
        assert story["governance"]["spend"] == "disabled"
        assert story["governance"]["market_validation_claimed"] is False
        assert story["governance"]["authority_created"] is False
        assert "source_bound_proof" in story["semantic_guardrails"]["must_preserve"]


def test_active_campaign_factory_routes_to_v3_through_visual_spine() -> None:
    active = (ROOT / "scripts" / "build_multichannel_campaign_factory.py").read_text(encoding="utf-8")
    v3 = (ROOT / "scripts" / "build_multichannel_campaign_factory_v3.py").read_text(encoding="utf-8")
    spine = (ROOT / "scripts" / "nichefoundry_visual_spine.py").read_text(encoding="utf-8")
    assert "build_multichannel_campaign_factory_v3 import *" in active
    assert "install_visual_spine(_v3)" in active
    assert operator_production.build_family.__module__ == "scripts.nichefoundry_visual_spine"
    assert getattr(operator_production.build_family, "_dio_visual_spine_wrapper", False) is True
    assert "MUSIC = FOUNDRY /" not in active
    assert "MUSIC = FOUNDRY /" not in v3
    assert "_music_catalog" in v3
    assert "LINGUA_SEMANTIC_LAW.json" in v3
    assert "LINGUA_PROJECTION_PLAN.json" in v3
    assert '"vertical_short"' in v3
    assert '"landscape_explainer"' in v3
    assert "cross_archetype_collisions" in v3
    assert '"primary_compositor": "document_studio_local_compositor"' in spine
    assert '"gamma_required_for_media": False' in spine


def test_visual_and_media_executors_consume_projection_without_gamma_dependency() -> None:
    gamma = (ROOT / "scripts" / "run_gamma_art_directed_story.js").read_text(encoding="utf-8")
    local = (ROOT / "adapters" / "document_studio" / "local_media_compositor.py").read_text(encoding="utf-8")
    spine = (ROOT / "scripts" / "nichefoundry_visual_spine.py").read_text(encoding="utf-8")
    media = (ROOT / "scripts" / "build_campaign_media_v3.py").read_text(encoding="utf-8")
    assert "MAX_ADDITIONAL_INSTRUCTIONS = 4800" in gamma
    assert "optional_visual_candidate" in gamma
    assert "render_story_frames" in local
    assert "document_studio_local_compositor" in local
    assert '"gamma_required_for_media": False' in spine
    assert "DIO_GAMMA_VISUAL_CANDIDATE" in spine
    assert "render_cinematic_format" in spine
    assert "edge_tts" in media
    assert "piper_local" in media
    assert "nichefoundry.dio_campaign_production_request.v3" in media


def test_projection_preflight_is_directly_invokable_and_checks_historical_voice() -> None:
    source = (ROOT / "scripts" / "check_lingua_nichefoundry_projection_runtime.py").read_text(encoding="utf-8")
    assert "sys.path.insert(0, str(ROOT))" in source
    assert '"historical_teacher_voice": "en-ZA-LeahNeural"' in source
    assert '"ready_for_teacher_projection"' in source
    assert '"music_selection": "RIGHTS_RECORDED_CATALOG_OR_INTENTIONAL_SILENCE"' in source
