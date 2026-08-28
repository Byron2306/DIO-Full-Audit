from __future__ import annotations

import json
import sys
from pathlib import Path

import scripts.run_premium_media_phase16_1_1 as runner


def test_runner_loads_and_passes_optional_explainer_contracts(monkeypatch, tmp_path: Path, capsys):
    script = {"schema": "dio.product_explainer.script_package.v1", "title": "HOMS", "scenes": []}
    request = {"schema": "dio.media.production_request.v2", "release": {"external_publication": "NEEDS_YOU"}}
    script_path = tmp_path / "script.json"
    request_path = tmp_path / "request.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    request_path.write_text(json.dumps(request), encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_run_gauntlet(**kwargs):
        seen.update(kwargs)
        result = {
            "explainer_contract_binding": "PASS",
            "nichefoundry_repository_execution": "PASS",
            "premium_or_approved_voice": "PASS",
            "robotic_production_fallback": "REFUSE",
            "music_asset_present": "PASS",
            "music_rights_evidence": "PASS",
            "narration_music_mix": "PASS",
            "sample_rate_48khz_stereo": "PASS",
            "loudness_qa": "PASS",
            "procedural_music_fallback": "REFUSE",
            "music_hiss_detection": "PASS",
            "native_gamma_execution": "PASS",
            "gamma_scene_coverage": "PASS",
            "gamma_final_video_binding": "PASS",
            "native_nichefoundry_render_execution": "PASS",
            "gamma_composition_preserved": "PASS",
            "document_studio_control_surface_binding": "PASS",
            "document_studio_native_render_execution": "REFUSE",
            "destructive_media_recomposition": "REFUSE",
            "automated_perceptual_release": "REFUSE",
            "human_visual_release": "NEEDS_YOU",
            "premium_video_rendering": "PASS",
            "corpus_execution_census": "PASS",
            "full_corpus_native_execution": "REFUSE",
            "canonical_output_integrity": "PASS",
            "tamper_detection": "PASS",
            "provider_set": ["imported"],
            "external_publication": "REFUSE",
            "external_send": "REFUSE",
            "media_spend": "REFUSE",
            "human_gate": "NEEDS_YOU",
            "acceptance_token": "DIO_FUSION_CLOSURE_READY",
        }
        return result

    monkeypatch.setattr(runner, "run_gauntlet", fake_run_gauntlet)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_premium_media_phase16_1_1.py",
            "--output",
            str(tmp_path / "out"),
            "--provider",
            "auto",
            "--script-package",
            str(script_path),
            "--production-request",
            str(request_path),
        ],
    )

    assert runner.main() == 0
    output = capsys.readouterr().out
    assert seen["script_package"] == script
    assert seen["production_request"] == request
    assert '"explainer_contract_binding": "PASS"' in output
    assert output.rstrip().endswith("DIO_FUSION_CLOSURE_READY")


def test_optional_json_loader_refuses_non_object(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("[]", encoding="utf-8")
    try:
        runner._load_optional_json(path)
    except ValueError as exc:
        assert "expected JSON object" in str(exc)
    else:
        raise AssertionError("non-object explainer contract was accepted")
