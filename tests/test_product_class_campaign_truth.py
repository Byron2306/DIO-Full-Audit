from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_product_class_campaign_batch as campaign


def test_ensure_video_registry_bootstraps_clean_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = tmp_path / "deliverables" / "dio_video_candidates" / "DIO_VIDEO_CANDIDATE_REGISTRY.json"
    monkeypatch.setattr(campaign, "VIDEO_REGISTRY", registry)

    campaign._ensure_video_registry()

    payload = json.loads(registry.read_text())
    assert payload["schema"] == "dio.video_candidate_registry.v1"
    assert payload["candidates"] == []
    assert payload["counts"]["total"] == 0


def test_wrapper_does_not_call_unrendered_reel_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    product_dir = tmp_path / "campaign"
    request_path = product_dir / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    reel = product_dir / "assets" / "reel.mp4"
    request_path.parent.mkdir(parents=True)
    request_path.write_text(json.dumps({"outputs": {"vertical_reel": str(reel)}}), encoding="utf-8")
    family = {
        "family_id": "product-class--grantproof",
        "product": {"id": "grantproof"},
        "nichefoundry": {"request": str(request_path), "native_reel_state": "brief_ready"},
        "assets": {"reel_1080x1920": str(reel)},
        "validation": {"state": "passed", "errors": []},
    }
    monkeypatch.setattr(campaign, "_legacy_build_ads_and_reel", lambda *args, **kwargs: family)
    monkeypatch.setattr(campaign.legacy, "write_json", lambda *args, **kwargs: None)

    result = campaign.build_ads_and_reel({"slug": "grantproof"}, product_dir, render_reel=False)

    assert result["nichefoundry"]["native_reel_state"] == "render_ready"
    assert result["nichefoundry"]["long_form_state"] == "not_generated"
    assert result["validation"]["state"] == "inputs_validated"
    assert "reel_1080x1920" not in result["assets"]


def test_wrapper_requires_native_receipt_for_ready_reel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    product_dir = tmp_path / "campaign"
    reel = product_dir / "assets" / "reel.mp4"
    reel.parent.mkdir(parents=True)
    reel.write_bytes(b"video")
    request_path = product_dir / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    request_path.write_text(json.dumps({"outputs": {"vertical_reel": str(reel)}}), encoding="utf-8")
    family = {
        "family_id": "product-class--grantproof",
        "product": {"id": "grantproof"},
        "nichefoundry": {"request": str(request_path)},
        "assets": {"reel_1080x1920": str(reel)},
        "validation": {"state": "passed", "errors": []},
    }
    monkeypatch.setattr(campaign, "_legacy_build_ads_and_reel", lambda *args, **kwargs: family)
    monkeypatch.setattr(campaign.legacy, "write_json", lambda *args, **kwargs: None)

    result = campaign.build_ads_and_reel({"slug": "grantproof"}, product_dir, render_reel=True)

    assert result["nichefoundry"]["native_reel_state"] == "failed"
    assert result["validation"]["state"] == "failed"
    assert "reel_1080x1920" not in result["assets"]
