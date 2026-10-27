from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from products import canonical_marketing_media as canon
from scripts import build_campaign_media_v3 as media

ROOT = Path(__file__).resolve().parents[1]


def test_golden_identity_uses_hash_verified_original_and_preserves_customer_source():
    original = Image.new("RGB", (720, 720), "blue")
    changed, receipt = canon.apply_golden_identity(original, brand_owner="dio")
    assert changed.tobytes() != original.tobytes()
    assert original.getpixel((719, 719)) == (0, 0, 255)
    assert receipt["asset_id"] == "DIO_EYE_PREMIUM"
    assert receipt["source_sha256"]
    unchanged, customer_receipt = canon.apply_golden_identity(original, brand_owner="customer")
    assert unchanged.tobytes() == original.tobytes()
    assert customer_receipt["brand_owner"] == "customer"


def test_music_receipt_is_bound_to_track_bytes_and_attribution():
    selected = canon.approved_music()
    assert selected["sha256"] == hashlib.sha256(Path(selected["path"]).read_bytes()).hexdigest()
    assert selected["rights_receipt_sha256"]
    assert selected["attribution_sha256"]
    assert selected["licence"] == "CC BY 4.0"
    with pytest.raises(ValueError, match="canonical music"):
        canon.approved_music({**selected, "path": str(ROOT / "README.md")})


def test_music_refuses_changed_rights_receipt(tmp_path, monkeypatch):
    import shutil
    shutil.copytree(ROOT / "config/media", tmp_path / "config/media")
    shutil.copytree(ROOT / "media/music_catalog", tmp_path / "media/music_catalog")
    receipt = tmp_path / "media/music_catalog/MUSICLFLES_WARM_SUNSET_RIGHTS_RECEIPT.json"
    payload = json.loads(receipt.read_text())
    payload["rights"]["commercial_use"] = False
    receipt.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="rights"):
        canon.approved_music(root=tmp_path)


def test_marketing_refuses_edge_tts_instead_of_remote_voice(tmp_path):
    with pytest.raises(media.CampaignMediaError, match="Vera"):
        media.synthesize_projected_story([], tmp_path, {"required": True, "provider": "edge_tts", "remote_tts_allowed": True}, nichefoundry_root=tmp_path)


def test_voice_receipt_requires_audio_hash_and_real_provenance(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF" + b"0" * 60)
    receipt = {"backend": "pocket_tts", "profile_id": "vera_pocket_public", "voice_url": "vera", "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match="provenance"):
        canon.verify_voice_receipt(receipt, audio)
    with pytest.raises(ValueError, match="integrity"):
        canon.verify_voice_receipt({**receipt, "audio_sha256": "bad", "model_provenance": {"voice_id": "vera"}}, audio)


def test_legacy_campaign_entrypoint_cannot_render_retired_piper(tmp_path):
    from scripts import build_campaign_media as legacy
    with pytest.raises(legacy.CampaignMediaError, match="retired"):
        legacy.render_campaign_media(tmp_path / "request.json", tmp_path / "gamma.json")
