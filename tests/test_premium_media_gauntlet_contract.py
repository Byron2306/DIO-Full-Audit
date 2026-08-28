from __future__ import annotations

import hashlib
from pathlib import Path

import products.premium_media_gauntlet as gauntlet


def _script() -> dict:
    return {
        "schema": "dio.product_explainer.script_package.v1",
        "title": "HOMS",
        "scenes": [{"scene_id": "scene_01_problem", "story_beat": "problem", "narration": "A problem."}],
    }


def _request() -> dict:
    return {
        "schema": "dio.media.production_request.v2",
        "release": {
            "local_render": "ALLOW",
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }


def test_gauntlet_passes_explainer_contracts_without_weakening_release_gates(monkeypatch, tmp_path: Path):
    seen: dict[str, object] = {}
    script = _script()
    request = _request()

    def fake_build_premium_media(*, output_dir, nichefoundry_root, provider, script_package, production_request):
        seen["script_package"] = script_package
        seen["production_request"] = production_request
        root = Path(output_dir)
        final = root / "media/youtube/FINAL_VIDEO_PREMIUM.mp4"
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(b"clean-final")
        digest = hashlib.sha256(final.read_bytes()).hexdigest()
        return {
            "output_dir": str(root),
            "proof_manifest": {
                "artifacts": [
                    {
                        "path": "media/youtube/FINAL_VIDEO_PREMIUM.mp4",
                        "sha256": digest,
                    }
                ]
            },
            "receipt": {
                "provider_set": ["imported"],
                "premium_media_fingerprint": "sha256:test",
                "explainer_contract_binding": "PASS",
            },
            "nichefoundry": {
                "probe": {"streams": [{"sample_rate": "48000", "channels": 2}]},
                "sound_design": {
                    "music_identity": {"family": "bound-original"},
                    "rights": {"status": "cleared"},
                    "scenes": [{"music_cue": "continuity_bed"}],
                },
                "music_quality": {"hiss_detection": "PASS"},
                "gamma": {"native_engine_invoked": True},
                "native_render": {"qa": {"passed": True}},
            },
            "census": {
                "engines": [
                    {"engine_id": "nichefoundry", "state": "NATIVE_EXECUTED"},
                    {"engine_id": "document_studio", "state": "CONTROL_SURFACE_BOUND"},
                    {"engine_id": "lingua", "state": "NOT_INVOKED"},
                    {"engine_id": "homs", "state": "PROJECTION_ONLY"},
                    {"engine_id": "evidex", "state": "PROJECTION_ONLY"},
                    {"engine_id": "vamp", "state": "NOT_BOUND"},
                    {"engine_id": "sophia", "state": "PROJECTION_ONLY"},
                ],
                "full_corpus_native_execution": "REFUSE",
            },
            "document_studio": {
                "native_engine_invoked": False,
                "binding_state": "CONTROL_SURFACE_BOUND",
                "gamma_composition_preserved": "PASS",
                "destructive_crop": "REFUSE",
            },
        }

    monkeypatch.setattr(gauntlet, "build_premium_media", fake_build_premium_media)

    receipt = gauntlet.run_gauntlet(
        output_dir=tmp_path / "gauntlet",
        nichefoundry_root=tmp_path / "nf",
        provider="auto",
        script_package=script,
        production_request=request,
    )

    assert seen["script_package"] is script
    assert seen["production_request"] is request
    assert receipt["explainer_contract_binding"] == "PASS"
    assert receipt["external_publication"] == "REFUSE"
    assert receipt["external_send"] == "REFUSE"
    assert receipt["media_spend"] == "REFUSE"
    assert receipt["human_gate"] == "NEEDS_YOU"
    assert receipt["tamper_detection"] == "PASS"
