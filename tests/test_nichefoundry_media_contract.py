from __future__ import annotations

import json
from pathlib import Path

import scripts.run_nichefoundry_media_pipeline as legacy_bridge
import scripts.run_nichefoundry_media_pipeline_v2 as media_v2
from dio_secrets import _derive_local_media_env


def test_legacy_media_entrypoint_is_the_v2_narrated_pipeline() -> None:
    assert legacy_bridge.run_media_pipeline is media_v2.run_media_pipeline
    assert legacy_bridge.main is media_v2.main


def test_nichefoundry_legacy_piper_env_derives_dio_model(monkeypatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "voices"
    model_dir.mkdir()
    model = model_dir / "en_US-lessac-high.onnx"
    config = Path(str(model) + ".json")
    model.write_bytes(b"onnx-model")
    config.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    monkeypatch.delenv("PIPER_CONFIG_FILE", raising=False)
    monkeypatch.setenv("PIPER_MODEL_DIR", str(model_dir))
    monkeypatch.setenv("PIPER_MODEL_FILE", model.name)
    loaded: dict[str, str] = {}
    _derive_local_media_env(loaded, overwrite=False)
    assert loaded["PIPER_MODEL"] == str(model.resolve())
    assert loaded["PIPER_CONFIG_FILE"] == str(config.resolve())


def test_nichefoundry_model_name_finds_existing_legacy_voice(monkeypatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "original-nichefoundry" / "models" / "piper"
    model_dir.mkdir(parents=True)
    model = model_dir / "en_US-lessac-high.onnx"
    config = Path(str(model) + ".json")
    model.write_bytes(b"onnx-model")
    config.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    monkeypatch.delenv("PIPER_CONFIG_FILE", raising=False)
    monkeypatch.setenv("PIPER_MODEL_DIR", str(model_dir))
    monkeypatch.setenv("PIPER_MODEL_NAME", "en_US-lessac-high")
    monkeypatch.setenv("PIPER_MODEL_FILE", "")
    loaded: dict[str, str] = {}
    _derive_local_media_env(loaded, overwrite=False)
    assert loaded["PIPER_MODEL"] == str(model.resolve())


def test_v2_media_bridge_requires_and_registers_both_mp4_outputs(monkeypatch, tmp_path: Path) -> None:
    family_dir = tmp_path / "family"
    gamma_dir = family_dir / "gamma"
    media_dir = family_dir / "media"
    assets_dir = family_dir / "assets"
    gamma_dir.mkdir(parents=True)
    media_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)

    gamma_receipt = gamma_dir / "GAMMA_STORY_RECEIPT.json"
    gamma_receipt.write_text(json.dumps({"state": "ready"}), encoding="utf-8")
    vertical = assets_dir / "reel_1080x1920.mp4"
    landscape = assets_dir / "explainer_1920x1080.mp4"
    request_path = family_dir / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    request_path.write_text(
        json.dumps(
            {
                "gamma": {"receipt": str(gamma_receipt)},
                "outputs": {
                    "vertical_reel": str(vertical),
                    "long_form_explainer": str(landscape),
                },
            }
        ),
        encoding="utf-8",
    )
    family = {
        "family_id": "test-product--test-audience",
        "nichefoundry": {"request": str(request_path)},
        "assets": {},
        "governance": {},
    }

    monkeypatch.setattr(media_v2, "load_secret_env", lambda overwrite=False: {})

    def fake_render(request, gamma, *, nichefoundry_root):
        assert request == request_path
        assert gamma == gamma_receipt
        assert nichefoundry_root == tmp_path / "foundry"
        vertical.write_bytes(b"v" * 12000)
        landscape.write_bytes(b"l" * 12000)
        (media_dir / "PIPER_NARRATION_RECEIPT.json").write_text("{}", encoding="utf-8")
        (media_dir / "CAMPAIGN_MEDIA_RECEIPT.json").write_text("{}", encoding="utf-8")
        return {
            "outputs": {
                "vertical_reel": {"path": str(vertical)},
                "long_form_explainer": {"path": str(landscape)},
            }
        }

    monkeypatch.setattr(media_v2, "render_campaign_media", fake_render)
    receipt = media_v2.run_family(family, foundry_root=tmp_path / "foundry", render_media=True)
    assert receipt["state"] == "ready"
    assert receipt["voice_provider"] == "piper_local"
    assert receipt["music_required"] is True
    assert receipt["outputs"]["vertical_reel"].endswith("reel_1080x1920.mp4")
    assert receipt["outputs"]["long_form_explainer"].endswith("explainer_1920x1080.mp4")
    assert family["piper"]["state"] == "ready"
    assert family["nichefoundry"]["reel_state"] == "ready"
    assert family["nichefoundry"]["long_form_state"] == "ready"
    assert family["governance"]["publication"] == "held"
    assert family["governance"]["spend"] == "disabled"


def test_media_preflight_can_be_invoked_as_direct_script() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts" / "check_nichefoundry_media_runtime.py").read_text(encoding="utf-8")
    assert "sys.path.insert(0, str(ROOT))" in source
