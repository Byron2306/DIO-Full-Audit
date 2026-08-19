from __future__ import annotations

import os
from pathlib import Path

from scripts.build_campaign_media_v3 import resolve_edge_tts_binary
from scripts.edge_tts_runtime import configure_edge_tts_environment, resolve_edge_tts_for_service

ROOT = Path(__file__).resolve().parents[1]


def _fake_edge(home: Path) -> Path:
    binary = home / ".local" / "bin" / "edge-tts"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary.resolve()


def test_systemd_style_path_still_resolves_user_local_edge_tts(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    expected = _fake_edge(home)
    monkeypatch.delenv("EDGE_TTS_BIN", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    resolved = resolve_edge_tts_for_service(tmp_path / "nichefoundry", home=home)
    assert resolved == expected


def test_service_bootstrap_exports_binding_consumed_by_media_executor(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    expected = _fake_edge(home)
    monkeypatch.delenv("EDGE_TTS_BIN", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    exported = configure_edge_tts_environment(tmp_path / "nichefoundry", home=home)
    assert exported == str(expected)
    assert os.environ["EDGE_TTS_BIN"] == str(expected)
    assert resolve_edge_tts_binary(tmp_path / "nichefoundry") == expected


def test_active_factory_hydrates_edge_before_importing_v3() -> None:
    source = (ROOT / "scripts" / "build_multichannel_campaign_factory.py").read_text(encoding="utf-8")
    hydrate = source.index("configure_edge_tts_environment()")
    v3_import = source.index("from scripts import build_multichannel_campaign_factory_v3 as _v3")
    assert hydrate < v3_import
    assert "~/.local/bin" in source
