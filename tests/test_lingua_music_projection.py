from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.build_multichannel_campaign_factory_v3 as factory_v3
import scripts.lingua_music_projection as music_projection
from scripts.lingua_music_projection import select_projection_music


def _surface_plan() -> dict:
    return {
        "arc_family": "recognition_then_relief",
        "music": {
            "family": "warm_upbeat",
            "keywords": ["warm", "sunset", "upbeat", "education"],
            "allow_silence": True,
            "volume": 0.10,
        },
    }


def _product() -> dict[str, str]:
    return {"name": "HOMS Assessment Desk"}


def _audience() -> dict[str, str]:
    return {
        "name": "Teachers and lecturers",
        "pain": "Marking consumes evenings and weekends.",
        "outcome": "Structured drafts ready for educator review.",
    }


def test_active_factory_uses_lingua_music_selector() -> None:
    import scripts.build_multichannel_campaign_factory  # noqa: F401

    assert factory_v3._select_music is select_projection_music


def test_checked_in_music_catalog_is_byte_verified_and_selectable() -> None:
    rows = music_projection._catalog()
    warm_sunset = next(row for row in rows if row["title"] == "Warm Sunset by MusicLFiles")
    assert warm_sunset["path"].is_file()
    result = select_projection_music(_surface_plan(), _product(), _audience(), "HOMS--teachers")
    assert result["mode"] == "rights_recorded"
    assert result["title"] == "Warm Sunset by MusicLFiles"


def test_zero_semantic_match_is_not_reused_as_generic_background(monkeypatch, tmp_path: Path) -> None:
    irrelevant = {
        "path": tmp_path / "generic.ogg",
        "attribution": tmp_path / "ATTRIBUTION.md",
        "receipt": tmp_path / "RECEIPT.json",
        "metadata": "somber industrial documentary machinery",
        "title": "Factory Night",
        "artist": "Example",
        "licence": "CC BY 4.0",
    }
    monkeypatch.setattr(music_projection, "_catalog", lambda: [irrelevant])
    monkeypatch.setattr(music_projection, "_fresh_projection_music", lambda **kwargs: None)
    result = select_projection_music(_surface_plan(), _product(), _audience(), "HOMS--teachers")
    assert result["mode"] == "none"
    assert result["selection_basis"] == "intentional_silence_no_semantically_matched_cleared_track"
    assert "generic.ogg" not in result["path"]


def test_semantically_matching_cleared_track_is_selected(monkeypatch, tmp_path: Path) -> None:
    track = {
        "path": tmp_path / "warm-sunset.ogg",
        "attribution": tmp_path / "ATTRIBUTION.md",
        "receipt": tmp_path / "RECEIPT.json",
        "metadata": "Warm Sunset education upbeat warm",
        "title": "Warm Sunset",
        "artist": "MusicLFiles",
        "licence": "BY 4.0",
    }
    monkeypatch.setattr(music_projection, "_catalog", lambda: [track])
    result = select_projection_music(_surface_plan(), _product(), _audience(), "HOMS--teachers")
    assert result["mode"] == "rights_recorded"
    assert result["title"] == "Warm Sunset"
    assert result["selection_basis"] == "audience_projection_catalog_match"
    assert result["match_score"] > 0


def test_fresh_rights_search_is_used_before_silence(monkeypatch) -> None:
    monkeypatch.setattr(music_projection, "_catalog", lambda: [])
    sourced = {
        **_surface_plan()["music"],
        "mode": "rights_recorded",
        "path": "/tmp/new.ogg",
        "attribution": "/tmp/MUSIC_ATTRIBUTION.md",
        "selection_basis": "fresh_audience_projection_openverse_search",
    }
    monkeypatch.setattr(music_projection, "_fresh_projection_music", lambda **kwargs: sourced)
    result = select_projection_music(_surface_plan(), _product(), _audience(), "HOMS--teachers")
    assert result == sourced


def test_fresh_music_source_includes_user_local_ffprobe_and_surfaces_failures(monkeypatch, tmp_path: Path) -> None:
    foundry = tmp_path / "NicheFoundry"
    (foundry / "scripts").mkdir(parents=True)
    (foundry / "scripts" / "source_commercial_music.js").write_text("", encoding="utf-8")
    (foundry / "studios" / "builtin").mkdir(parents=True)
    (foundry / "studios" / "builtin" / "practical_open_source.json").write_text("{}", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    local_bin = tmp_path / ".local" / "bin"
    monkeypatch.setattr(music_projection, "FOUNDRY", foundry)
    monkeypatch.setattr(music_projection, "ROOT", repo)
    monkeypatch.setattr(music_projection.Path, "home", lambda: tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(music_projection, "_catalog", lambda: [])
    captured: dict[str, object] = {}

    def fail_without_ffprobe(_command, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=1, stderr="ffprobe: not found", stdout="")

    monkeypatch.setattr(music_projection.subprocess, "run", fail_without_ffprobe)

    with pytest.raises(RuntimeError, match="ffprobe: not found"):
        select_projection_music(_surface_plan(), _product(), _audience(), "HOMS--teachers")

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["PATH"].startswith(str(local_bin) + ":")
