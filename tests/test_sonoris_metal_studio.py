"""Regression checks for distinct, fully orchestrated Sonoris metal sketches."""
from __future__ import annotations

import json
from pathlib import Path

import mido

from products.sonoris_metal_patterns import metal_models
from products.sonoris_song_engine import compile_song


def _events(root: Path, job: str) -> dict:
    return json.loads((root / job / "SONG_EVENTS.json").read_text())


def test_metal_styles_have_distinct_original_rhythms_and_full_band(tmp_path: Path) -> None:
    fingerprints = set()
    for genre, style in metal_models()["profiles"].items():
        receipt = compile_song({"genre": genre, "seed": 4812, "bars": 8}, output_root=tmp_path, job_id=genre)
        events = _events(tmp_path, genre)
        assert events["harmony"] and events["bass"] and events["drums"]
        assert receipt["tuning"] == style["tuning"]
        assert receipt["tone_profile"] == style["tone"]
        assert receipt["modules"]["drums"] == "virtuosity"
        if style["extra"] == "folk": assert events["folk"] and receipt["modules"]["folk"] != "off"
        if style["extra"] == "keys": assert events["keys"] and receipt["modules"]["keys"] != "off"
        notes = events["harmony"]
        fingerprints.add(tuple((row["beat"], row["pitch"], row["articulation"]) for row in notes if row["beat"] < 8))
        midi = mido.MidiFile(tmp_path / genre / "SONG_CANDIDATE.mid")
        names = {message.name for track in midi.tracks for message in track if message.type == "track_name"}
        assert {"harmony", "bass", "drums"} <= names
    assert len(fingerprints) == len(metal_models()["profiles"])


def test_attack_and_drum_intensity_change_exported_performance(tmp_path: Path) -> None:
    base = compile_song({"genre":"thrash_metal", "seed":91, "bars":8}, output_root=tmp_path, job_id="base")
    changed = compile_song({"genre":"thrash_metal", "seed":91, "bars":8,
                            "guitar_attack":.6, "drum_intensity":.5}, output_root=tmp_path, job_id="changed")
    before, after = _events(tmp_path,"base"), _events(tmp_path,"changed")
    assert changed["guitar_attack"] == .6 and changed["drum_intensity"] == .5
    assert after["harmony"][0]["velocity"] < before["harmony"][0]["velocity"]
    assert after["drums"][0]["velocity"] < before["drums"][0]["velocity"]
    assert after["bass"] == before["bass"]
    assert base["midi_sha256"] != changed["midi_sha256"]


def _compositional_fingerprint(
    events: dict,
) -> tuple:
    rows = events["harmony"]

    if not rows:
        return ()

    first_beat = min(
        row["beat"]
        for row in rows
    )

    root = min(
        row["pitch"]
        for row in rows
        if row["beat"] == first_beat
    )

    return tuple(
        (
            round(
                row["beat"],
                4,
            ),
            row["pitch"] - root,
            row["articulation"],
        )
        for row in rows
        if row["beat"] < 16
    )


def test_same_genre_many_seeds_generate_distinct_compositions(
    tmp_path: Path,
) -> None:

    genres = (
        "thrash_metal",
        "death_metal",
        "doom_metal",
        "power_metal",
        "prog_metal",
        "industrial_metal",
        "alternative_metal",
        "nu_metal",
    )

    seeds = (
        11,
        29,
        47,
        83,
        131,
        197,
    )

    for genre in genres:
        fingerprints = set()
        dna_hashes = set()

        for seed in seeds:
            job = (
                f"{genre}-{seed}"
            )

            receipt = compile_song(
                {
                    "genre": genre,
                    "seed": seed,
                    "bars": 12,
                },
                output_root=tmp_path,
                job_id=job,
            )

            events = _events(
                tmp_path,
                job,
            )

            signature = json.loads(
                (
                    tmp_path
                    / job
                    / "METAL_PATTERN_SIGNATURE.json"
                ).read_text()
            )

            fingerprints.add(
                _compositional_fingerprint(
                    events
                )
            )

            dna_hashes.add(
                signature[
                    "motif_dna"
                ][
                    "sha256"
                ]
            )

            assert (
                signature[
                    "source_phrase_reuse"
                ]
                is False
            )

            assert (
                signature[
                    "composition_source"
                ]
                ==
                "generated_song_specific_motif_dna"
            )

        assert len(
            dna_hashes
        ) == len(
            seeds
        ), (
            genre,
            dna_hashes,
        )

        assert len(
            fingerprints
        ) >= 5, (
            genre,
            len(
                fingerprints
            ),
        )


def test_same_seed_is_compositionally_deterministic(
    tmp_path: Path,
) -> None:

    request = {
        "genre": "thrash_metal",
        "seed": 2306,
        "bars": 12,
    }

    compile_song(
        request,
        output_root=tmp_path,
        job_id="a",
    )

    compile_song(
        request,
        output_root=tmp_path,
        job_id="b",
    )

    a = _events(
        tmp_path,
        "a",
    )

    b = _events(
        tmp_path,
        "b",
    )

    assert (
        _compositional_fingerprint(a)
        ==
        _compositional_fingerprint(b)
    )

    da = json.loads(
        (
            tmp_path
            / "a"
            / "METAL_PATTERN_SIGNATURE.json"
        ).read_text()
    )

    db = json.loads(
        (
            tmp_path
            / "b"
            / "METAL_PATTERN_SIGNATURE.json"
        ).read_text()
    )

    assert (
        da["motif_dna"]["sha256"]
        ==
        db["motif_dna"]["sha256"]
    )
