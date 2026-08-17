from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_nichefoundry_media_pipeline as media


def family_fixture(tmp_path: Path) -> tuple[dict, Path, Path, Path]:
    family_dir = tmp_path / "family"
    family_dir.mkdir(parents=True)
    scene = family_dir / "scene.jpg"
    scene.write_bytes(b"scene")
    music = family_dir / "music.ogg"
    music.write_bytes(b"music")
    reel = family_dir / "assets" / "reel.mp4"
    request = {
        "schema": "nichefoundry.dio_campaign_production_request.v1",
        "family_id": "FAMILY-TEST",
        "scene_images": [str(scene)],
        "music": {"path": str(music)},
        "outputs": {"vertical_reel": str(reel)},
        "request_hash": "sha256:test",
    }
    request_path = family_dir / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    family = {
        "family_id": "FAMILY-TEST",
        "product": {"id": "grantproof"},
        "assets": {},
        "nichefoundry": {"request": str(request_path)},
        "validation": {},
        "governance": {},
    }
    return family, request_path, reel, reel.parent / "NICHEFOUNDRY_REEL_RECEIPT.json"


def ready_checks() -> dict:
    return {
        "nichefoundry_root": "/tmp/foundry",
        "node": True,
        "ffmpeg": True,
        "ffprobe": True,
        "reel_engine": True,
        "premium_assets_engine": True,
        "episode_renderer": True,
        "youtube_publisher": True,
        "ready_for_campaign_reels": True,
    }


def test_skipped_render_is_render_ready_not_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    family, _, reel, _ = family_fixture(tmp_path)
    monkeypatch.setattr(media, "assert_engine_ready", lambda root: ready_checks())
    monkeypatch.setattr(media, "EVENT_LOG", tmp_path / "events.jsonl")

    receipt = media.run_family(family, tmp_path / "foundry", render_reel=False, timeout=10)

    assert receipt["state"] == "render_ready"
    assert receipt["outputs"] == {}
    assert receipt["planned_outputs"]["vertical_reel"]
    assert family["nichefoundry"]["native_reel_state"] == "render_ready"
    assert family["validation"]["state"] == "inputs_validated"
    assert "reel_1080x1920" not in family["assets"]
    assert not reel.exists()


def test_renderer_must_leave_verified_reel_and_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    family, _, reel, native_receipt = family_fixture(tmp_path)
    monkeypatch.setattr(media, "assert_engine_ready", lambda root: ready_checks())
    monkeypatch.setattr(media, "EVENT_LOG", tmp_path / "events.jsonl")
    monkeypatch.setattr(media, "run_reel_engine", lambda *args, **kwargs: {"output": str(reel)})

    receipt = media.run_family(family, tmp_path / "foundry", render_reel=True, timeout=10)

    assert receipt["state"] == "failed"
    assert any("Renderer returned without verified artifacts" in item for item in receipt["missing_inputs"])
    assert family["nichefoundry"]["native_reel_state"] == "failed"
    assert family["validation"]["state"] == "failed"
    assert not native_receipt.exists()


def test_rendered_reel_is_ready_only_after_artifact_and_receipt_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    family, _, reel, native_receipt = family_fixture(tmp_path)
    monkeypatch.setattr(media, "assert_engine_ready", lambda root: ready_checks())
    monkeypatch.setattr(media, "EVENT_LOG", tmp_path / "events.jsonl")

    def fake_renderer(*args, **kwargs):
        reel.parent.mkdir(parents=True, exist_ok=True)
        reel.write_bytes(b"video-bytes")
        native_receipt.write_text(json.dumps({"status": "ok", "output": str(reel)}), encoding="utf-8")
        return {"status": "ok", "output": str(reel)}

    monkeypatch.setattr(media, "run_reel_engine", fake_renderer)
    receipt = media.run_family(family, tmp_path / "foundry", render_reel=True, timeout=10)

    assert receipt["state"] == "ready"
    assert receipt["outputs"]["vertical_reel"]
    assert receipt["outputs"]["reel_receipt"]
    assert family["nichefoundry"]["native_reel_state"] == "ready"
    assert family["validation"]["state"] == "passed"
    assert family["assets"]["reel_1080x1920"]
