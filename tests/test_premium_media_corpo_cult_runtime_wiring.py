from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import products.premium_media_federation as federation


STORY_BEATS = [
    "problem",
    "product_definition",
    "mechanism",
    "proof",
    "differentiation",
    "result",
    "call_to_action",
]


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _script() -> dict[str, object]:
    return {
        "schema": "dio.product_explainer.renderer_script.v1",
        "title": "HOMS",
        "product_id": "HOMS",
        "scenes": [
            {
                "scene_id": f"scene_{index:02d}_{beat}",
                "story_beat": beat,
                "title": beat.replace("_", " ").title(),
                "claim_ids": [f"claim_{index:02d}"],
                "source_ids": [f"source_{index:02d}"],
                "target_duration_seconds": 1,
            }
            for index, beat in enumerate(STORY_BEATS, 1)
        ],
    }


def _gamma() -> dict[str, object]:
    assets = [
        {
            "scene_id": f"scene_{index:02d}_{beat}",
            "kind": "scene",
            "relative_path": f"premium_visuals/gamma/scene_{index:02d}.png",
            "sha256": f"gamma-scene-{index:02d}",
        }
        for index, beat in enumerate(STORY_BEATS, 1)
    ]
    assets.append(
        {
            "kind": "thumbnail",
            "relative_path": "premium_visuals/gamma/thumbnail.png",
            "sha256": "gamma-thumbnail",
        }
    )
    return {
        "native_engine_invoked": True,
        "scene_coverage": 7,
        "assets": assets,
    }


def _install_nichefoundry_evidence(episode: Path) -> None:
    _write(episode / "premium_assets_receipt.json", {"passed": True})
    _write(episode / "gamma_execution_receipt.json", _gamma())
    _write(
        episode / "music_rights_receipt.json",
        {"commercial_friendly_licence": True},
    )
    for name in (
        "host_profile.json",
        "pronunciation_lexicon.json",
        "audio_performance_plan.json",
        "audio_preflight_report.json",
        "audio_asset_hashes.json",
    ):
        _write(episode / name, {})
    _write(
        episode / "audio_manifest.json",
        {"provider": "imported", "scenes": [{"provider": "imported"}]},
    )
    _write(episode / "audio_performance_report.json", {"passed": True})
    _write(
        episode / "sound_design_plan.json",
        {
            "music_identity": {"id": "bound-score"},
            "rights": {"status": "cleared"},
            "scenes": [{"music_cue": "continuity_bed"}],
        },
    )
    _write(episode / "loudness_report.json", {"passed": True})
    (episode / "audio").mkdir(parents=True, exist_ok=True)
    (episode / "audio/episode_audio_preview.wav").write_bytes(b"test-audio")
    (episode / "audio/episode_music_bed_preview.wav").write_bytes(b"test-music")
    _write(episode / "render_qa_report.json", {"passed": True})
    _write(episode / "render_manifest_v2.json", {})
    _write(episode / "render_asset_hashes.json", {"complete": True})
    (episode / "final.mp4").write_bytes(b"test-video")
    (episode / "thumbnail.png").write_bytes(b"test-thumbnail")


def test_run_nichefoundry_invokes_bound_scene_compositor_before_final_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    niche_root = tmp_path / "NicheFoundry"
    episode = tmp_path / "episode"
    episode.mkdir(parents=True)
    _install_nichefoundry_evidence(episode)

    script = _script()
    request = {
        "schema": "dio.media.production_request.v2",
        "product_id": "HOMS",
        "visual_asset_pack": {
            "id": "HOMS_CORPO_CULT_V1",
            "sha256": "sha256:pack",
            "fallback": "REFUSE",
        },
    }
    composed = {
        "schema": "dio.media.visual_asset_pack_receipt.v1",
        "pack_id": "HOMS_CORPO_CULT_V1",
        "pack_sha256": "sha256:pack",
        "composition_authority": "dio_asset_pack",
        "generic_visual_fallback": "REFUSE",
        "publication_authority_created": False,
        "scenes": [],
    }
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        federation,
        "_prepare_episode",
        lambda *args, **kwargs: {"voice_import": None, "music_import": None},
    )
    monkeypatch.setattr(
        federation,
        "_run",
        lambda *args, **kwargs: SimpleNamespace(stdout="ok"),
    )
    monkeypatch.setattr(
        federation,
        "_resolve_premium_provider",
        lambda *args, **kwargs: "imported",
    )
    monkeypatch.setattr(
        federation,
        "_probe_audio",
        lambda *args, **kwargs: {"streams": [{"sample_rate": "48000", "channels": 2}]},
    )
    monkeypatch.setattr(
        federation,
        "_music_quality",
        lambda *args, **kwargs: {"hiss_detection": "PASS"},
    )
    monkeypatch.setattr(federation.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_compose(episode_dir, script_package, production_request, *, root=federation.ROOT):
        seen["compose_called"] = True
        seen["episode_dir"] = episode_dir
        seen["script"] = script_package
        seen["request"] = production_request
        return composed

    monkeypatch.setattr(
        federation,
        "compose_product_explainer_scenes",
        fake_compose,
        raising=False,
    )

    def fake_contract(episode_dir, gamma, *, script_package=None, composed_visuals=None):
        seen["contract_composed"] = composed_visuals

    monkeypatch.setattr(federation, "_prepare_native_render_contract", fake_contract)

    result = federation._run_nichefoundry(
        niche_root,
        episode,
        "imported",
        script_package=script,
        production_request=request,
    )

    assert seen.get("compose_called") is True
    assert seen["episode_dir"] == episode
    assert seen["script"] is script
    assert seen["request"] is request
    assert seen["contract_composed"] is composed
    assert result["composed_visuals"] is composed
