from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest

from products.premium_media_federation import _prepare_dio_product_score


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
