from __future__ import annotations

import json
import wave
from pathlib import Path

import products.premium_media_federation as federation


def _script() -> dict:
    return {
        "schema": "dio.product_explainer.script_package.v1",
        "title": "HOMS",
        "scenes": [
            {
                "scene_id": "scene_01_problem",
                "story_beat": "problem",
                "title": "The problem",
                "narration": "Assessment work is fragmented.",
                "target_duration_seconds": 7,
                "claim_ids": [],
                "source_ids": ["portfolio.json"],
            },
            {
                "scene_id": "scene_02_product_definition",
                "story_beat": "product_definition",
                "title": "What HOMS is",
                "narration": "DIO HOMS creates reviewable assessment outputs.",
                "target_duration_seconds": 7,
                "claim_ids": [],
                "source_ids": ["portfolio.json"],
            },
        ],
    }


def _production_request() -> dict:
    return {
        "schema": "dio.media.production_request.v2",
        "voice": {
            "role": "vesper_public",
            "profile": "vera_pocket_public",
            "render_mode": "presence_core_imported_audio",
            "pronunciation": {"DIO": "Dio"},
        },
        "release": {
            "local_render": "ALLOW",
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }


def _fake_niche_result(episode: Path, script: dict) -> dict:
    episode.mkdir(parents=True, exist_ok=True)
    for name, payload in {
        "audio_manifest.json": {"provider": "imported"},
        "audio_asset_hashes.json": {"complete": True},
        "loudness_report.json": {"episode": {}},
        "sound_design_plan.json": {"music_identity": {"family": "test"}, "rights": {"status": "cleared"}},
        "render_manifest_v2.json": {"output": "final.mp4"},
        "render_qa_report.json": {"passed": True},
    }.items():
        (episode / name).write_text(json.dumps(payload), encoding="utf-8")
    final = episode / "final.mp4"
    thumb = episode / "thumbnail.png"
    final.write_bytes(b"\x00\x00\x00\x18ftyp-test")
    thumb.write_bytes(b"png")
    return {
        "providers": ["imported"],
        "probe": {"streams": [{"sample_rate": "48000", "channels": 2}]},
        "sound_design": {"music_identity": {"family": "test"}, "rights": {"status": "cleared"}, "scenes": [{"music_cue": "bed"} for _ in script["scenes"]]},
        "music_quality": {"hiss_detection": "PASS"},
        "gamma": {"native_engine_invoked": True, "scene_coverage": len(script["scenes"]), "assets": []},
        "music_rights": {"commercial_friendly_licence": True},
        "premium_assets": {},
        "performance": {"passed": True},
        "loudness": {"episode": {}},
        "manifest": {"provider": "imported"},
        "preview": episode / "audio/episode_audio_preview.wav",
        "native_render": {
            "final": final,
            "thumbnail": thumb,
            "qa": {"passed": True},
            "manifest": {"output": "final.mp4"},
            "hashes": {"complete": True},
            "command": [],
            "stdout": "",
        },
        "source_ref": "Byron2306/NicheFoundry",
        "source_root": "/fake/nichefoundry",
        "native_engine_invoked": True,
    }


def test_build_premium_media_forwards_supplied_script_to_native_and_document_layers(monkeypatch, tmp_path: Path):
    seen: dict[str, object] = {}
    script = _script()
    request = _production_request()

    monkeypatch.setattr(federation, "resolve_nichefoundry_root", lambda value: tmp_path / "nichefoundry")
    monkeypatch.setattr(federation, "build_media_incarnation", lambda **kwargs: {"state": "base"})

    def fake_run_nichefoundry(niche_root, episode_dir, provider, *, script_package=None, production_request=None):
        seen["native_script"] = script_package
        seen["production_request"] = production_request
        return _fake_niche_result(episode_dir, script_package)

    def fake_document_studio(*, gamma_dir, script_package, output_dir, style_profile):
        seen["document_script"] = script_package
        return {
            "native_engine_invoked": False,
            "binding_state": "CONTROL_SURFACE_BOUND",
            "gamma_composition_preserved": "PASS",
            "destructive_crop": "REFUSE",
        }

    monkeypatch.setattr(federation, "_run_nichefoundry", fake_run_nichefoundry)
    monkeypatch.setattr(federation, "render_media_control_surface", fake_document_studio)

    result = federation.build_premium_media(
        output_dir=tmp_path / "out",
        nichefoundry_root=tmp_path / "ignored",
        script_package=script,
        production_request=request,
    )

    assert seen["native_script"] is script
    assert seen["document_script"] is script
    assert seen["production_request"] is request
    assert result["receipt"]["explainer_contract_binding"] == "PASS"
    assert result["receipt"]["external_publication"] == "REFUSE"
    assert result["receipt"]["media_spend"] == "REFUSE"
    assert result["receipt"]["human_gate"] == "NEEDS_YOU"


def test_legacy_phase16_path_keeps_fixed_script_as_compatibility_fallback(monkeypatch, tmp_path: Path):
    seen: dict[str, object] = {}
    monkeypatch.setattr(federation, "resolve_nichefoundry_root", lambda value: tmp_path / "nichefoundry")
    monkeypatch.setattr(federation, "build_media_incarnation", lambda **kwargs: {"state": "base"})

    def fake_run_nichefoundry(niche_root, episode_dir, provider, *, script_package=None, production_request=None):
        seen["script"] = script_package
        return _fake_niche_result(episode_dir, script_package)

    monkeypatch.setattr(federation, "_run_nichefoundry", fake_run_nichefoundry)
    monkeypatch.setattr(
        federation,
        "render_media_control_surface",
        lambda **kwargs: {
            "native_engine_invoked": False,
            "binding_state": "CONTROL_SURFACE_BOUND",
            "gamma_composition_preserved": "PASS",
            "destructive_crop": "REFUSE",
        },
    )

    result = federation.build_premium_media(output_dir=tmp_path / "out")

    assert len(seen["script"]["scenes"]) == 6
    assert result["receipt"]["explainer_contract_binding"] == "NOT_REQUESTED"


def test_prepare_episode_uses_supplied_scene_timing_and_dio_pronunciation(monkeypatch, tmp_path: Path):
    niche = tmp_path / "nf"
    pack = niche / "studios/builtin/practical_open_source.json"
    pack.parent.mkdir(parents=True)
    pack.write_text(json.dumps({"studio": {"id": "practical_open_source"}, "samples": [{}]}), encoding="utf-8")
    monkeypatch.setattr(federation, "_prepare_presence_core_voice_imports", lambda *args, **kwargs: None)

    episode = tmp_path / "episode"
    result = federation._prepare_episode(
        niche,
        episode,
        script_package=_script(),
        production_request=_production_request(),
    )

    assert [row["scene_id"] for row in result["timing"]["scenes"]] == [
        "scene_01_problem",
        "scene_02_product_definition",
    ]
    assert [row["target_duration_seconds"] for row in result["timing"]["scenes"]] == [7, 7]
    assert result["brief"]["pronunciation_overrides"] == [
        {"term": "DIO", "spoken_form": "Dio", "review_required": False}
    ]


def test_presence_core_voice_import_writes_nichefoundry_registry_and_preserves_authority(monkeypatch, tmp_path: Path):
    def fake_build_voice_plan(**kwargs):
        return {
            "profile_id": "vera_pocket_public",
            "backend": "pocket_tts",
            "state": "ready_for_internal_render",
            "reasons": [],
        }

    def fake_synthesize_voice(*, text, output_path, plan):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(b"\x00\x00" * 16000)
        return {
            "profile_id": plan["profile_id"],
            "backend": plan["backend"],
            "external_action_executed": False,
            "send_authorized": False,
            "identity_authority_created": False,
            "translation_authority_created": False,
        }

    monkeypatch.setattr(
        federation,
        "_presence_voice_functions",
        lambda: (fake_build_voice_plan, fake_synthesize_voice),
    )
    episode = tmp_path / "episode"
    receipt = federation._prepare_presence_core_voice_imports(
        episode,
        _script(),
        _production_request(),
    )

    registry = json.loads((episode / "audio_imports.json").read_text(encoding="utf-8"))
    assert receipt["voice_profile"] == "vera_pocket_public"
    assert receipt["backend"] == "pocket_tts"
    assert receipt["scene_count"] == 2
    assert all(row["relative_path"].startswith("imports/audio/") for row in registry["assets"])
    assert all(row["rights_status"] == "cleared" for row in registry["assets"])
    assert receipt["external_action_executed"] is False
    assert receipt["send_authorized"] is False
    assert receipt["identity_authority_created"] is False
    assert receipt["translation_authority_created"] is False


def test_native_render_contract_uses_injected_scene_set(tmp_path: Path):
    script = _script()
    gamma_assets = [
        {
            "kind": "scene",
            "scene_id": scene["scene_id"],
            "relative_path": f"premium_visuals/{scene['scene_id']}.png",
            "sha256": f"sha-{index}",
        }
        for index, scene in enumerate(script["scenes"], 1)
    ]
    gamma_assets.append(
        {
            "kind": "thumbnail",
            "relative_path": "premium_visuals/thumbnail.png",
            "sha256": "sha-thumb",
        }
    )
    federation._prepare_native_render_contract(
        tmp_path,
        {"assets": gamma_assets},
        script_package=script,
    )

    visual_plan = json.loads((tmp_path / "visual_plan.json").read_text(encoding="utf-8"))
    episode = json.loads((tmp_path / "episode.json").read_text(encoding="utf-8"))
    assert episode["title"] == "HOMS"
    assert [row["scene_id"] for row in visual_plan["scene_plans"]] == [
        scene["scene_id"] for scene in script["scenes"]
    ]
