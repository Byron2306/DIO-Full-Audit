from __future__ import annotations

import json
from pathlib import Path

import products.premium_media_federation as federation


def _script() -> dict:
    return {
        "schema": "dio.product_explainer.script_package.v1",
        "product_id": "HOMS",
        "title": "HOMS",
        "target_seconds": 7,
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
            }
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
            ],
            "scene_grammar": {
                "problem": {
                    "visual_mode": "metaphor",
                    "direction": [
                        "Represent fragmented academic work inside a controlled DIO environment."
                    ],
                    "motion": "restrained cinematic push",
                }
            },
            "motion": {"default": "restrained cinematic push"},
            "end_card": {},
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


def test_prepare_episode_persists_global_brand_brief_for_nichefoundry(tmp_path: Path) -> None:
    niche = tmp_path / "niche"
    pack = niche / "studios/builtin/practical_open_source.json"
    pack.parent.mkdir(parents=True)
    pack.write_text(
        json.dumps({"studio": {"id": "practical_open_source"}, "samples": [{}]}),
        encoding="utf-8",
    )

    request = _request()
    episode = tmp_path / "episode"
    result = federation._prepare_episode(
        niche,
        episode,
        script_package=_script(),
        production_request=request,
    )

    written_brief = json.loads((episode / "brief.json").read_text(encoding="utf-8"))

    assert written_brief == result["brief"]
    assert written_brief["brand_render_brief"] == request["brand_render_brief"]
    assert written_brief["brand_profile_id"] == "DIO_CINEMATIC_BRAND_V1"
    assert "black glass" in written_brief["visual_direction"].lower()
    assert "generic blue AI glow" in written_brief["forbidden_motifs"]


def test_native_render_contract_uses_governed_scene_motion_cue(tmp_path: Path) -> None:
    script = _script()
    script["scenes"][0]["motion_cue"] = "measured architectural reveal"
    gamma = {
        "assets": [
            {
                "kind": "scene",
                "scene_id": "scene_01_problem",
                "relative_path": "premium_visuals/scene_01_problem.png",
                "sha256": "sha-scene",
            },
            {
                "kind": "thumbnail",
                "relative_path": "premium_visuals/thumbnail.png",
                "sha256": "sha-thumb",
            },
        ]
    }

    federation._prepare_native_render_contract(
        tmp_path,
        gamma,
        script_package=script,
    )

    visual_plan = json.loads((tmp_path / "visual_plan.json").read_text(encoding="utf-8"))
    scene = visual_plan["scene_plans"][0]

    assert scene["motion_cue"] == "measured architectural reveal"
