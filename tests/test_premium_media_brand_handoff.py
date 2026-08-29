from __future__ import annotations

import json
from pathlib import Path

import products.premium_media_federation as federation


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
            },
        ],
    }


def _request() -> dict:
    return {
        "schema": "dio.media.production_request.v2",
        "product_id": "HOMS",
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
        "voice": {
            "role": "vesper_public",
            "profile": "vera_pocket_public",
            "render_mode": "disabled_for_test",
            "pronunciation": {"DIO": "Dio"},
        },
        "release": {
            "local_render": "ALLOW",
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }


def test_prepare_episode_hands_enriched_renderer_script_to_nichefoundry(tmp_path: Path) -> None:
    niche = tmp_path / "niche"
    pack = niche / "studios/builtin/practical_open_source.json"
    pack.parent.mkdir(parents=True)
    pack.write_text(
        json.dumps({"studio": {"id": "practical_open_source"}, "samples": [{}]}),
        encoding="utf-8",
    )

    script = _script()
    original = json.loads(json.dumps(script))
    episode = tmp_path / "episode"

    result = federation._prepare_episode(
        niche,
        episode,
        script_package=script,
        production_request=_request(),
    )

    written = json.loads((episode / "script_package.json").read_text(encoding="utf-8"))

    assert script == original
    assert written == result["script"]
    assert written["brand_profile_id"] == "DIO_CINEMATIC_BRAND_V1"
    assert written["scenes"][0]["visual_mode"] == "metaphor"
    assert written["scenes"][1]["visual_mode"] == "proof"
    assert written["scenes"][2]["visual_mode"] == "brand_end_card"
    assert "black glass" in " ".join(written["scenes"][0]["visual_requirements"]).lower()
    assert written["scenes"][1]["motion_cue"] == "deliberate hold with minimal parallax"
    assert written["scenes"][2]["end_card"]["require_wordmark"] is True
    assert written["scenes"][2]["end_card"]["require_sigil"] is True
