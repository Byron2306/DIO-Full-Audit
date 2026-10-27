from __future__ import annotations

import json
from pathlib import Path

from presence_core import voice
from scripts import build_campaign_media as legacy
from scripts import build_campaign_media_v3 as media

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_campaign_media_v3.py"


def test_v3_media_script_bootstraps_repo_root_for_direct_execution() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "ROOT = Path(__file__).resolve().parents[1]" in source
    assert "sys.path.insert(0, str(ROOT))" in source
    assert "from scripts import build_campaign_media as legacy" in source


def test_media_tool_resolves_from_user_local_bin_when_missing_from_path(monkeypatch, tmp_path: Path) -> None:
    binary = tmp_path / ".local" / "bin" / "ffprobe"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setattr(legacy.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(legacy.shutil, "which", lambda _name: None)

    assert legacy.require_tool("ffprobe") == binary.resolve()


def test_pocket_tts_campaign_narration_uses_approved_vera_and_writes_receipt(
    monkeypatch, tmp_path: Path
) -> None:
    plan = {
        "state": "ready_for_internal_render",
        "public_default_authorized": True,
        "backend": "pocket_tts",
        "voice_url": "vera",
        "profile_id": "vera_pocket_public",
    }
    monkeypatch.setattr(voice, "build_voice_plan", lambda **_kwargs: plan)
    monkeypatch.setattr(media.legacy, "require_tool", lambda _name: Path("/usr/bin/ffprobe"))
    monkeypatch.setattr(media.legacy, "probe_duration", lambda _path, _ffprobe: 1.25)

    def synthesize(*, text, output_path, plan):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"RIFF" + b"\x00" * 40)
        return {
            "backend": plan["backend"],
            "profile_id": plan["profile_id"],
            "voice_url": plan["voice_url"],
            "send_authorized": False,
            "text": text,
        }

    monkeypatch.setattr(voice, "synthesize_voice", synthesize)
    receipt = media.synthesize_projected_story(
        [{"scene_id": "scene_a", "narration": "A reviewable story."}],
        tmp_path,
        {
            "required": True,
            "provider": "pocket_tts",
            "profile": "vera_pocket_public",
            "voice": "vera",
            "remote_tts_allowed": False,
        },
        nichefoundry_root=tmp_path,
    )

    saved = json.loads((tmp_path / "POCKET_TTS_NARRATION_RECEIPT.json").read_text(encoding="utf-8"))
    assert receipt["provider"] == "pocket_tts"
    assert receipt["voice"] == "vera"
    assert receipt["local_only"] is True
    assert receipt["remote_tts_used"] is False
    assert receipt["scenes"][0]["duration_seconds"] == 1.25
    assert saved["governance"]["publication"] == "held_for_operator_approval"
    assert saved["governance"]["send_authorized"] is False


def test_piper_is_rejected_for_production_campaign_narration(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(media.CampaignMediaError, match="Piper narration is retired"):
        media.synthesize_projected_story(
            [{"scene_id": "scene_a", "narration": "A reviewable story."}],
            tmp_path,
            {"required": True, "provider": "piper_local"},
            nichefoundry_root=tmp_path,
        )


def test_unavailable_pocket_tts_is_a_held_campaign_error(monkeypatch, tmp_path: Path) -> None:
    plan = {
        "state": "ready_for_internal_render",
        "public_default_authorized": True,
        "backend": "pocket_tts",
        "voice_url": "vera",
        "profile_id": "vera_pocket_public",
    }
    monkeypatch.setattr(voice, "build_voice_plan", lambda **_kwargs: plan)
    monkeypatch.setattr(media.legacy, "require_tool", lambda _name: Path("/usr/bin/ffprobe"))
    monkeypatch.setattr(voice, "synthesize_voice", lambda **_kwargs: (_ for _ in ()).throw(ConnectionRefusedError("offline")))
    import pytest

    with pytest.raises(media.CampaignMediaError, match="Pocket TTS Vera is unavailable"):
        media.synthesize_pocket_story(
            [{"scene_id": "scene_a", "narration": "A reviewable story."}],
            tmp_path,
            {"required": True, "provider": "pocket_tts", "profile": "vera_pocket_public", "voice": "vera", "remote_tts_allowed": False},
        )


def test_gilded_asset_pack_fails_closed_when_the_declared_manifest_is_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(media, "ROOT", tmp_path)
    (tmp_path / "config" / "media").mkdir(parents=True)
    (tmp_path / "config" / "media" / "dio_gilded_house_style.json").write_text(
        json.dumps({"source_manifest": "media/pack.json", "source_pack_id": "DIO_GILDED"}),
        encoding="utf-8",
    )
    import pytest

    with pytest.raises(media.CampaignMediaError, match="asset-pack manifest is unavailable"):
        media._gilded_asset_pack()
