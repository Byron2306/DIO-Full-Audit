from pathlib import Path

from products.sonoris_genre_compiler import (
    compile_composition_request,
)

from products.sonoris_song_engine import compile_song


def test_free_meter_ambient_song_compiles(tmp_path: Path):
    request = {
        "title": "Dicere Free Meter Acceptance",
        "genre": "ambient",
        "tempo_bpm": 72,
        "bars": 8,
        "seed": 31026,
    }

    plan = compile_composition_request(request)

    assert plan["musical_frame"]["meter"] == "free"

    result = compile_song(
        request,
        output_root=tmp_path,
        job_id="dicere-free-meter-test",
    )

    assert result["state"] == "COMPILED"
    assert result["meter"] == "free"

    job = tmp_path / "dicere-free-meter-test"

    assert (job / "COMPOSITION_PLAN.json").is_file()
    assert (job / "SONG_EVENTS.json").is_file()
    assert (job / "SONG_CANDIDATE.mid").is_file()
    assert (job / "SONORIS_STUDIO_RECEIPT.json").is_file()

    assert result["audio_state"] == "NOT_RENDERED"
    assert result["release_authorized"] is False
