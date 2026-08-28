from __future__ import annotations

import json
import struct
import wave
from pathlib import Path

import pytest

import products.premium_media_federation as federation


def _script() -> dict:
    durations = [7, 7, 11, 11, 9, 7, 3]
    beats = [
        "problem",
        "product_definition",
        "mechanism",
        "proof",
        "differentiation",
        "result",
        "call_to_action",
    ]
    return {
        "schema": "dio.product_explainer.script_package.v1",
        "title": "HOMS",
        "target_seconds": 55,
        "scenes": [
            {
                "scene_id": f"scene_{index:02d}_{beat}",
                "story_beat": beat,
                "narration": f"Scene {index}",
                "target_duration_seconds": duration,
                "claim_ids": [],
                "source_ids": [],
            }
            for index, (beat, duration) in enumerate(zip(beats, durations), 1)
        ],
    }


def _niche_root(root: Path) -> Path:
    pack = root / "studios/builtin/practical_open_source.json"
    pack.parent.mkdir(parents=True)
    pack.write_text(json.dumps({"studio": {"id": "practical_open_source"}, "samples": [{}]}), encoding="utf-8")
    return root


def test_prepare_episode_reallocates_fixed_story_budget_to_measured_voice(monkeypatch, tmp_path: Path):
    # Measured Pocket TTS / Vera durations from the first real HOMS render.
    measured = [6.44, 6.12, 7.40, 5.16, 12.44, 10.36, 2.20]
    script = _script()

    def fake_voice_imports(episode_dir, script_package, production_request):
        return {
            "schema": "dio.vesper.media_voice_import.v1",
            "voice_profile": "vera_pocket_public",
            "backend": "pocket_tts",
            "scene_count": len(measured),
            "assets": [
                {
                    "scene_id": scene["scene_id"],
                    "relative_path": f"imports/audio/{index:02d}.wav",
                    "duration_seconds": duration,
                }
                for index, (scene, duration) in enumerate(zip(script_package["scenes"], measured), 1)
            ],
            "external_action_executed": False,
            "send_authorized": False,
            "identity_authority_created": False,
            "translation_authority_created": False,
        }

    monkeypatch.setattr(federation, "_prepare_presence_core_voice_imports", fake_voice_imports)

    result = federation._prepare_episode(
        _niche_root(tmp_path / "nf"),
        tmp_path / "episode",
        script_package=script,
        production_request={"voice": {"render_mode": "presence_core_imported_audio"}},
    )

    targets = {
        row["scene_id"]: float(row["target_duration_seconds"])
        for row in result["timing"]["scenes"]
    }

    assert round(sum(targets.values()), 2) == 55.00
    for scene, duration in zip(script["scenes"], measured):
        assert targets[scene["scene_id"]] >= duration + 0.45

    assert targets["scene_05_differentiation"] > 9
    assert targets["scene_06_result"] > 7
    assert result["timing"]["reconciliation"]["state"] == "VOICE_FIT_REBALANCED"
    assert result["timing"]["reconciliation"]["voice_profile"] == "vera_pocket_public"


def test_presence_voice_import_records_measured_wav_duration(monkeypatch, tmp_path: Path):
    script = {
        "schema": "dio.product_explainer.script_package.v1",
        "title": "HOMS",
        "scenes": [
            {
                "scene_id": "scene_01_problem",
                "narration": "Assessment work is fragmented.",
                "target_duration_seconds": 7,
            }
        ],
    }

    def fake_build_voice_plan(**kwargs):
        return {
            "profile_id": "vera_pocket_public",
            "backend": "pocket_tts",
            "state": "ready_for_internal_render",
            "reasons": [],
        }

    def fake_synthesize_voice(*, text, output_path, plan):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sample_rate = 16000
        seconds = 1.25
        with wave.open(str(output_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(b"\x00\x00" * int(sample_rate * seconds))
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

    receipt = federation._prepare_presence_core_voice_imports(
        tmp_path / "episode",
        script,
        {
            "voice": {
                "render_mode": "presence_core_imported_audio",
                "profile": "vera_pocket_public",
            }
        },
    )

    assert receipt is not None
    assert receipt["assets"][0]["duration_seconds"] == pytest.approx(1.25, abs=0.01)


def test_wav_duration_uses_actual_pcm_payload_when_streaming_header_overstates_data(tmp_path: Path):
    sample_rate = 24000
    channels = 1
    sample_width = 2
    actual_seconds = 2.20
    frame_count = int(sample_rate * actual_seconds)
    payload = b"\x00\x00" * frame_count
    path = tmp_path / "pocket_streaming.wav"

    # Pocket TTS currently emits a streaming-style WAV header that advertises
    # a 2,000,000,000-byte RIFF/data payload while writing a much shorter file.
    declared_data_bytes = 2_000_000_000
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width
    header = (
        b"RIFF"
        + struct.pack("<I", declared_data_bytes + 36)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, 16)
        + b"data"
        + struct.pack("<I", declared_data_bytes)
    )
    path.write_bytes(header + payload)

    with wave.open(str(path), "rb") as handle:
        assert handle.getnframes() == 1_000_000_000

    assert federation._wav_duration_seconds(path) == pytest.approx(actual_seconds, abs=0.01)


def test_prepare_episode_refuses_when_measured_voice_cannot_fit_story_budget(monkeypatch, tmp_path: Path):
    measured = [8.0, 8.0, 12.0, 12.0, 13.0, 11.0, 3.0]

    def fake_voice_imports(episode_dir, script_package, production_request):
        return {
            "schema": "dio.vesper.media_voice_import.v1",
            "voice_profile": "vera_pocket_public",
            "backend": "pocket_tts",
            "scene_count": len(measured),
            "assets": [
                {
                    "scene_id": scene["scene_id"],
                    "relative_path": f"imports/audio/{index:02d}.wav",
                    "duration_seconds": duration,
                }
                for index, (scene, duration) in enumerate(zip(script_package["scenes"], measured), 1)
            ],
            "external_action_executed": False,
            "send_authorized": False,
            "identity_authority_created": False,
            "translation_authority_created": False,
        }

    monkeypatch.setattr(federation, "_prepare_presence_core_voice_imports", fake_voice_imports)

    with pytest.raises(federation.PremiumMediaError, match="cannot fit canonical timing budget"):
        federation._prepare_episode(
            _niche_root(tmp_path / "nf"),
            tmp_path / "episode",
            script_package=_script(),
            production_request={"voice": {"render_mode": "presence_core_imported_audio"}},
        )
