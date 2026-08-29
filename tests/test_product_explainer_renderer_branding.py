from __future__ import annotations

import json

from products.product_explainer_branding import enrich_renderer_script


def _script() -> dict:
    return {
        "schema": "dio.product_explainer.script_package.v1",
        "product_id": "HOMS",
        "title": "HOMS",
        "target_seconds": 21,
        "scenes": [
            {
                "scene_id": "scene_01_problem",
                "story_beat": "problem",
                "title": "The problem",
                "narration": "Assessment work is fragmented.",
                "screen_anchor": "THE WORK IS FRAGMENTED",
                "target_duration_seconds": 7,
                "claim_ids": ["CLM-PROBLEM"],
                "source_ids": ["portfolio.json"],
                "asset_preference": ["generated_cinematic_metaphor"],
                "asset_provenance": "unresolved",
                "asset_representation": "planned",
            },
            {
                "scene_id": "scene_02_proof",
                "story_beat": "proof",
                "title": "Show the product",
                "narration": "A bound proof package preserves reviewable evidence.",
                "screen_anchor": "BOUND PRODUCT EVIDENCE",
                "target_duration_seconds": 11,
                "claim_ids": ["CLM-PROOF"],
                "source_ids": ["proof/homs.md"],
                "asset_preference": ["real_product_output", "generated_cinematic_metaphor"],
                "asset_provenance": "unresolved",
                "asset_representation": "planned",
            },
            {
                "scene_id": "scene_03_call_to_action",
                "story_beat": "call_to_action",
                "title": "Next action",
                "narration": "See how HOMS fits your workflow.",
                "screen_anchor": "EXPLORE HOMS",
                "target_duration_seconds": 3,
                "claim_ids": [],
                "source_ids": [],
                "asset_preference": ["generated_cinematic_metaphor"],
                "asset_provenance": "unresolved",
                "asset_representation": "planned",
            },
        ],
    }


def _request() -> dict:
    return {
        "schema": "dio.media.production_request.v2",
        "product_id": "HOMS",
        "style_profile": {"id": "DIO_CINEMATIC_BRAND_V1", "sha256": "sha256:style"},
        "brand_render_brief": {
            "schema": "dio.brand_render_brief.v1",
            "profile_id": "DIO_CINEMATIC_BRAND_V1",
            "product_id": "HOMS",
            "visual_direction": (
                "Render every scene inside the governed DIO cinematic world: black glass; "
                "obsidian metal; monumental technological scale; controlled gold pathways."
            ),
            "forbidden_motifs": [
                "generic blue AI glow",
                "humanoid robots",
                "fake product interfaces",
                "generated scenes presented as proof",
            ],
            "scene_grammar": {
                "problem": {
                    "visual_mode": "metaphor",
                    "direction": [
                        "Represent assessment overload as fragmented academic work entering a controlled DIO environment."
                    ],
                    "motion": "restrained cinematic push",
                },
                "proof": {
                    "visual_mode": "proof",
                    "direction": [
                        "Prioritize bound real HOMS outputs, screenshots, or evidence artifacts before generated abstraction."
                    ],
                    "motion": "deliberate hold with minimal parallax",
                },
                "call_to_action": {
                    "visual_mode": "brand_end_card",
                    "direction": [
                        "Use the canonical DIO sigil and wordmark on black with restrained gold and cream typography."
                    ],
                    "motion": "fade through black into locked brand end card",
                },
            },
            "end_card": {
                "visual_mode": "brand_end_card",
                "background": "black",
                "accent": "restrained gold",
                "require_wordmark": True,
                "require_sigil": True,
                "require_url": True,
                "wordmark": "brand/dio-wordmark.svg",
                "sigil": "brand/dio-sigil.webp",
            },
        },
        "release": {
            "local_render": "ALLOW",
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }


def test_renderer_enrichment_is_brand_bound_and_semantically_immutable() -> None:
    script = _script()
    request = _request()
    before = json.loads(json.dumps(script))

    rendered = enrich_renderer_script(script, request)

    assert script == before
    assert rendered is not script
    assert rendered["brand_profile_id"] == "DIO_CINEMATIC_BRAND_V1"

    protected = (
        "narration",
        "claim_ids",
        "source_ids",
        "story_beat",
        "screen_anchor",
        "target_duration_seconds",
    )
    for source, scene in zip(script["scenes"], rendered["scenes"]):
        for key in protected:
            assert scene[key] == source[key]
        assert scene["brand_profile_id"] == "DIO_CINEMATIC_BRAND_V1"
        assert scene["visual_requirements"]
        assert "black glass" in " ".join(scene["visual_requirements"]).lower()
        assert "generic blue ai glow" in [
            value.lower() for value in scene["forbidden_motifs"]
        ]

    problem = rendered["scenes"][0]
    proof = rendered["scenes"][1]
    cta = rendered["scenes"][2]

    assert problem["visual_mode"] == "metaphor"
    assert "fragmented academic work" in " ".join(problem["visual_requirements"]).lower()
    assert problem["motion_cue"] == "restrained cinematic push"

    assert proof["visual_mode"] == "proof"
    assert proof["motion_cue"] == "deliberate hold with minimal parallax"
    assert "real homs outputs" in " ".join(proof["visual_requirements"]).lower()

    assert cta["visual_mode"] == "brand_end_card"
    assert cta["motion_cue"] == "fade through black into locked brand end card"
    assert cta["end_card"]["require_wordmark"] is True
    assert cta["end_card"]["require_sigil"] is True
    assert cta["end_card"]["require_url"] is True
