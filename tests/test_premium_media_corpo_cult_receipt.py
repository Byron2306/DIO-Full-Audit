from __future__ import annotations

import json
from pathlib import Path

import products.premium_media_federation as federation


def _script() -> dict:
    return {
        "schema": "dio.product_explainer.script_package.v1",
        "title": "HOMS",
        "product_id": "HOMS",
        "scenes": [
            {
                "scene_id": "scene_01_problem",
                "story_beat": "problem",
                "title": "Problem",
                "narration": "Assessment work is fragmented.",
                "target_duration_seconds": 7,
                "claim_ids": [],
                "source_ids": [],
            }
        ],
    }


def _request() -> dict:
    return {
        "schema": "dio.media.production_request.v2",
        "product_id": "HOMS",
        "visual_asset_pack": {
            "id": "HOMS_CORPO_CULT_V1",
            "sha256": "sha256:pack",
            "fallback": "REFUSE",
        },
        "release": {
            "local_render": "ALLOW",
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }


def _fake_niche_result(episode: Path) -> dict:
    episode.mkdir(parents=True, exist_ok=True)
    for name, payload in {
        "audio_manifest.json": {"provider": "imported"},
        "audio_asset_hashes.json": {"complete": True},
        "loudness_report.json": {"episode": {}},
        "sound_design_plan.json": {
            "music_identity": {"family": "test"},
            "rights": {"status": "cleared"},
        },
        "render_manifest_v2.json": {"output": "final.mp4"},
        "render_qa_report.json": {"passed": True},
    }.items():
        (episode / name).write_text(json.dumps(payload), encoding="utf-8")

    final = episode / "final.mp4"
    thumbnail = episode / "thumbnail.png"
    final.write_bytes(b"\x00\x00\x00\x18ftyp-test")
    thumbnail.write_bytes(b"png")

    return {
        "providers": ["imported"],
        "probe": {"streams": [{"sample_rate": "48000", "channels": 2}]},
        "sound_design": {
            "music_identity": {"family": "test"},
            "rights": {"status": "cleared"},
            "scenes": [{"music_cue": "bed"}],
        },
        "music_quality": {"hiss_detection": "PASS"},
        "gamma": {"native_engine_invoked": True, "scene_coverage": 1, "assets": []},
        "composed_visuals": {
            "schema": "dio.media.visual_asset_pack_receipt.v1",
            "product_id": "HOMS",
            "pack_id": "HOMS_CORPO_CULT_V1",
            "pack_sha256": "sha256:pack",
            "composition_authority": "dio_asset_pack",
            "generic_visual_fallback": "REFUSE",
            "publication_authority_created": False,
            "scenes": [],
        },
        "music_rights": {"commercial_friendly_licence": True},
        "premium_assets": {},
        "performance": {"passed": True},
        "loudness": {"episode": {}},
        "manifest": {"provider": "imported"},
        "preview": episode / "audio/episode_audio_preview.wav",
        "native_render": {
            "final": final,
            "thumbnail": thumbnail,
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


def test_pack_bound_premium_receipt_declares_dio_final_visual_authority(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(federation, "resolve_nichefoundry_root", lambda value: tmp_path / "nichefoundry")
    monkeypatch.setattr(federation, "build_media_incarnation", lambda **kwargs: {"state": "base"})
    monkeypatch.setattr(
        federation,
        "_run_nichefoundry",
        lambda niche_root, episode_dir, provider, *, script_package=None, production_request=None: _fake_niche_result(episode_dir),
    )
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

    result = federation.build_premium_media(
        output_dir=tmp_path / "out",
        nichefoundry_root=tmp_path / "ignored",
        script_package=_script(),
        production_request=_request(),
    )

    for payload in (result["proof_manifest"], result["receipt"]):
        assert payload["visual_asset_pack_binding"] == "PASS"
        assert payload["visual_asset_pack_fallback"] == "REFUSE"
        assert payload["visual_composition_authority"] == "dio_asset_pack"
        assert payload["human_visual_release"] == "NEEDS_YOU"
        assert payload["external_publication"] == "REFUSE"
        assert payload["external_send"] == "REFUSE"
        assert payload["media_spend"] == "REFUSE"
        assert payload["human_gate"] == "NEEDS_YOU"
