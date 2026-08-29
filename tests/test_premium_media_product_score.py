from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest

import products.premium_media_federation as federation
from products.premium_media_federation import _prepare_dio_product_score
from products.product_explainer_branding import load_product_media_profile


def _write_stereo_motif(path: Path, *, seconds: float = 0.35) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 48_000
    frame_count = int(sample_rate * seconds)
    frames = bytearray()
    for index in range(frame_count):
        t = index / sample_rate
        sample = int(7_500 * math.sin(2.0 * math.pi * 220.0 * t))
        frames.extend(struct.pack("<hh", sample, sample))

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))


def _request(source: Path) -> dict:
    return {
        "schema": "dio.media.production_request.v2",
        "product_id": "HOMS",
        "sound": {
            "music_origin": "dio_product_score",
            "sonic_identity": "DIO_SONIC_IDENTITY_V1",
            "source_path": str(source),
            "music_direction": {
                "inherits": "DIO_SONIC_IDENTITY_V1",
                "variant": "institutional_glass",
            },
            "score_recipe": {
                "tone": "dark premium restrained institutional",
                "texture": [
                    "low sustained harmonic bed",
                    "glassy restrained percussion",
                    "subtle procedural pulse",
                ],
                "avoid": [
                    "uplifting stock corporate music",
                    "EDM drop",
                    "trailer braam overload",
                ],
                "mix_rule": "Narration remains dominant; music supports structure and never masks Vesper.",
            },
        },
        "release": {
            "local_render": "ALLOW",
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }


def test_prepare_dio_product_score_derives_source_bound_homs_bed(tmp_path: Path) -> None:
    source = tmp_path / "DIO_SONIC_IDENTITY_V1.wav"
    _write_stereo_motif(source)

    episode = tmp_path / "episode"
    receipt = _prepare_dio_product_score(
        episode,
        _request(source),
        target_seconds=5.0,
    )

    output = episode / "imports/music_bed.wav"
    receipt_path = episode / "DIO_PRODUCT_SCORE_RECEIPT.json"

    assert output.is_file()
    assert receipt_path.is_file()
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == receipt

    assert receipt["schema"] == "dio.media.product_score.v1"
    assert receipt["sonic_identity"] == "DIO_SONIC_IDENTITY_V1"
    assert receipt["product_id"] == "HOMS"
    assert receipt["variant"] == "institutional_glass"
    assert receipt["duration_seconds"] == pytest.approx(5.0, abs=0.05)
    assert receipt["sample_rate"] == 48_000
    assert receipt["channels"] == 2
    assert receipt["source_sha256"]
    assert receipt["output_sha256"]
    assert receipt["recipe_fingerprint"].startswith("sha256:")
    assert receipt["music_rights_state"] == "project_owned_derived_score"
    assert receipt["generic_music_fallback"] == "REFUSE"

    with wave.open(str(output), "rb") as handle:
        assert handle.getframerate() == 48_000
        assert handle.getnchannels() == 2
        assert handle.getsampwidth() == 2
        assert handle.getnframes() / handle.getframerate() == pytest.approx(5.0, abs=0.05)


def test_prepare_episode_routes_dio_product_score_into_imported_music_path(tmp_path: Path) -> None:
    source = tmp_path / "DIO_SONIC_IDENTITY_V1.wav"
    _write_stereo_motif(source)

    niche = tmp_path / "niche"
    pack = niche / "studios/builtin/practical_open_source.json"
    pack.parent.mkdir(parents=True)
    pack.write_text(
        json.dumps({"studio": {"id": "practical_open_source"}, "samples": [{}]}),
        encoding="utf-8",
    )

    script = {
        "schema": "dio.product_explainer.script_package.v1",
        "product_id": "HOMS",
        "title": "HOMS",
        "target_seconds": 3.0,
        "scenes": [
            {
                "scene_id": "scene_01_problem",
                "story_beat": "problem",
                "title": "The problem",
                "narration": "Assessment work is fragmented.",
                "screen_anchor": "THE WORK IS FRAGMENTED",
                "target_duration_seconds": 3.0,
                "claim_ids": ["CLM-PROBLEM"],
                "source_ids": ["portfolio.json"],
            }
        ],
    }

    episode = tmp_path / "episode"
    result = federation._prepare_episode(
        niche,
        episode,
        script_package=script,
        production_request=_request(source),
    )

    assert result["music_import"] is not None
    assert result["music_import"]["schema"] == "dio.media.product_score.v1"
    assert result["music_import"]["generic_music_fallback"] == "REFUSE"
    assert result["music_import"]["duration_seconds"] == pytest.approx(3.0, abs=0.05)
    assert (episode / "imports/music_bed.wav").is_file()
    assert (episode / "DIO_PRODUCT_SCORE_RECEIPT.json").is_file()


def test_prepare_dio_product_score_uses_numeric_product_recipe(tmp_path: Path) -> None:
    source = tmp_path / "DIO_SONIC_IDENTITY_V1.wav"
    _write_stereo_motif(source)

    request = _request(source)
    request["sound"]["score_recipe"]["render"] = {
        "motif_gain": 0.17,
        "shadow_gain": 0.05,
        "shadow_delay_ms": 240,
        "shadow_pitch_ratio": 0.93,
        "highpass_hz": 55,
        "main_lowpass_hz": 4700,
        "shadow_lowpass_hz": 1500,
        "fade_in_seconds": 0.25,
        "fade_out_seconds": 0.60,
    }

    receipt = _prepare_dio_product_score(
        tmp_path / "episode",
        request,
        target_seconds=5.0,
    )

    render = receipt["render_recipe"]
    assert render["motif_gain"] == pytest.approx(0.17)
    assert render["shadow_gain"] == pytest.approx(0.05)
    assert render["shadow_delay_ms"] == 240
    assert render["shadow_pitch_ratio"] == pytest.approx(0.93)
    assert render["highpass_hz"] == 55
    assert render["main_lowpass_hz"] == 4700
    assert render["shadow_lowpass_hz"] == 1500
    assert render["fade_in_seconds"] == pytest.approx(0.25)
    assert render["fade_out_seconds"] == pytest.approx(0.60)


def test_homs_profile_owns_numeric_product_score_recipe() -> None:
    profile, _ = load_product_media_profile("HOMS")
    render = profile["score"]["recipe"]["render"]

    assert render == {
        "motif_gain": 0.20,
        "shadow_gain": 0.08,
        "shadow_delay_ms": 180,
        "shadow_pitch_ratio": 0.90,
        "highpass_hz": 45,
        "main_lowpass_hz": 5200,
        "shadow_lowpass_hz": 1800,
        "fade_in_seconds": 0.35,
        "fade_out_seconds": 0.75,
    }
