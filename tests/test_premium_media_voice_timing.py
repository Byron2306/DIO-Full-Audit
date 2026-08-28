from __future__ import annotations

import json
from pathlib import Path

import products.premium_media_federation as federation


def _script() -> dict:
    durations = [7, 7, 11, 11, 9, 7, 3]
    beats = [
        "problem",
        "product_definition",
        "mechanism",
        "proof",
        "differentiation",
        "result",
        "call_to_action",
    ]
    return {
        "schema": "dio.product_explainer.script_package.v1",
        "title": "HOMS",
        "target_seconds": 55,
        "scenes": [
            {
                "scene_id": f"scene_{index:02d}_{beat}",
                "story_beat": beat,
                "narration": f"Scene {index}",
                "target_duration_seconds": duration,
                "claim_ids": [],
                "source_ids": [],
            }
            for index, (beat, duration) in enumerate(zip(beats, durations), 1)
        ],
    }


def _niche_root(root: Path) -> Path:
    pack = root / "studios/builtin/practical_open_source.json"
    pack.parent.mkdir(parents=True)
    pack.write_text(json.dumps({"studio": {"id": "practical_open_source"}, "samples": [{}]}), encoding="utf-8")
    return root


def test_prepare_episode_reallocates_fixed_story_budget_to_measured_voice(monkeypatch, tmp_path: Path):
    # Measured Pocket TTS / Vera durations from the first real HOMS render.
    measured = [6.44, 6.12, 7.40, 5.16, 12.44, 10.36, 2.20]
    script = _script()

    def fake_voice_imports(episode_dir, script_package, production_request):
        return {
            "schema": "dio.vesper.media_voice_import.v1",
            "voice_profile": "vera_pocket_public",
            "backend": "pocket_tts",
            "scene_count": len(measured),
            "assets": [
                {
                    "scene_id": scene["scene_id"],
                    "relative_path": f"imports/audio/{index:02d}.wav",
                    "duration_seconds": duration,
                }
                for index, (scene, duration) in enumerate(zip(script_package["scenes"], measured), 1)
            ],
            "external_action_executed": False,
            "send_authorized": False,
            "identity_authority_created": False,
            "translation_authority_created": False,
        }

    monkeypatch.setattr(federation, "_prepare_presence_core_voice_imports", fake_voice_imports)

    result = federation._prepare_episode(
        _niche_root(tmp_path / "nf"),
        tmp_path / "episode",
        script_package=script,
        production_request={"voice": {"render_mode": "presence_core_imported_audio"}},
    )

    targets = {
        row["scene_id"]: float(row["target_duration_seconds"])
        for row in result["timing"]["scenes"]
    }

    assert round(sum(targets.values()), 2) == 55.00
    for scene, duration in zip(script["scenes"], measured):
        assert targets[scene["scene_id"]] >= duration + 0.45

    assert targets["scene_05_differentiation"] > 9
    assert targets["scene_06_result"] > 7
    assert result["timing"]["reconciliation"]["state"] == "VOICE_FIT_REBALANCED"
    assert result["timing"]["reconciliation"]["voice_profile"] == "vera_pocket_public"
