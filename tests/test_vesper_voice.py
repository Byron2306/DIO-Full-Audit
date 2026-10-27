from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

import pytest

from presence_core.voice import build_voice_plan, synthesize_piper_http, synthesize_voice, verified_vera_runtime_inventory


def make_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "vesper_voice_profiles.json").write_text(
        json.dumps(
            {
                "schema": "dio.vesper.voice_profiles.v1",
                "default_public_profile": None,
                "profiles": {
                    "piper_test": {
                        "backend": "piper_http",
                        "model": "en_US-lessac-medium",
                        "language": "English",
                        "public_brand_state": "experiment_only",
                    },
                    "pocket_test": {
                        "backend": "pocket_tts",
                        "model": "vera",
                        "voice_url": "vera",
                        "language": "English",
                        "public_brand_state": "approved",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_voice_plan_uses_interaction_cadence_without_send_authority(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    plan = build_voice_plan(
        root=root,
        language="English",
        requested_profile="piper_test",
        interaction={"delivery_policy": {"mode": "calm_service_recovery", "voice": {"piper_length_scale": 1.08}}},
    )
    assert plan["state"] == "ready_for_internal_render"
    assert plan["piper"]["length_scale"] == 1.08
    assert plan["send_authority_created"] is False
    assert plan["public_default_authorized"] is False


def test_unreviewed_language_does_not_fake_voice_support(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    plan = build_voice_plan(root=root, language="isiZulu", requested_profile="piper_test", interaction=None)
    assert plan["state"] == "not_renderable"
    assert "voice_language_mismatch" in plan["reasons"]
    assert plan["send_authority_created"] is False


def test_piper_render_is_internal_only(tmp_path: Path, monkeypatch) -> None:
    root = make_root(tmp_path)
    plan = build_voice_plan(root=root, language="English", requested_profile="piper_test", interaction=None)

    class Response:
        content = b"RIFF" + b"0" * 100
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, json, timeout):
        assert url.endswith("/synthesize")
        assert json["voice"] == "en_US-lessac-medium"
        return Response()

    monkeypatch.setattr("presence_core.voice.httpx.post", fake_post)
    receipt = synthesize_piper_http(text="Hello from Vesper.", output_path=tmp_path / "voice.wav", plan=plan)
    assert receipt["external_action_executed"] is False
    assert receipt["send_authorized"] is False
    assert Path(receipt["audio_path"]).is_file()


def test_vera_is_vspers_default_public_voice() -> None:
    plan = build_voice_plan(
        root=Path("."),
        language="English",
        interaction={"delivery_policy": {"mode": "warm_professional"}},
    )
    assert plan["profile_id"] == "vera_pocket_public"
    assert plan["backend"] == "pocket_tts"
    assert plan["voice_url"] == "vera"
    assert plan["public_default_authorized"] is True
    assert plan["send_authority_created"] is False


def test_proven_vera_pocket_profile_is_public_render_only() -> None:
    plan = build_voice_plan(
        root=Path("."),
        language="English",
        requested_profile="vera_pocket_public",
        interaction={"delivery_policy": {"mode": "warm_professional"}},
    )
    assert plan["backend"] == "pocket_tts"
    assert plan["model"] == "vera"
    assert plan["voice_url"] == "vera"
    assert plan["state"] == "ready_for_internal_render"
    assert plan["public_default_authorized"] is True
    assert plan["send_authority_created"] is False


def test_pocket_tts_render_uses_vera_without_creating_send_authority(tmp_path: Path, monkeypatch) -> None:
    root = make_root(tmp_path)
    plan = build_voice_plan(root=root, language="English", requested_profile="pocket_test", interaction=None)
    calls = []

    class Response:
        content = b"RIFF" + b"0" * 256
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, data, timeout):
        calls.append((url, data, timeout))
        return Response()

    monkeypatch.setattr("presence_core.voice.httpx.post", fake_post)
    receipt = synthesize_voice(
        text="DIO determines what is true. I determine how to say it.",
        output_path=tmp_path / "vera.wav",
        plan=plan,
        timeout=12.0,
    )

    assert calls == [("http://127.0.0.1:8000/tts", {"text": "DIO determines what is true. I determine how to say it.", "voice_url": "vera"}, 12.0)]
    assert receipt["backend"] == "pocket_tts"
    assert receipt["voice_url"] == "vera"
    assert receipt["external_action_executed"] is False
    assert receipt["send_authorized"] is False
    assert Path(receipt["audio_path"]).read_bytes().startswith(b"RIFF")


@pytest.mark.parametrize("default_profile", [None, "piper_test"])
def test_public_voice_fails_closed_when_default_is_missing_or_unapproved(
    tmp_path: Path, monkeypatch, default_profile: str | None
) -> None:
    root = make_root(tmp_path)
    path = root / "config" / "vesper_voice_profiles.json"
    registry = json.loads(path.read_text())
    registry["default_public_profile"] = default_profile
    path.write_text(json.dumps(registry))
    monkeypatch.setenv("DIO_VESPER_VOICE_PROFILE", "pocket_test")

    plan = build_voice_plan(root=root, language="English", interaction=None, public_default_only=True)

    assert plan["profile_id"] == default_profile
    assert plan["state"] == "not_renderable"
    assert plan["public_default_authorized"] is False
    with pytest.raises(RuntimeError, match="not renderable"):
        synthesize_voice(text="Hello", output_path=tmp_path / "blocked.wav", plan=plan)


def test_local_vera_inventory_rechecks_observed_files_and_service(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DIO_VESPER_RUNTIME_INVENTORY", raising=False)
    monkeypatch.delenv("DIO_VESPER_POCKET_TTS_URL", raising=False)
    model = tmp_path / "model.safetensors"
    voice = tmp_path / "vera.safetensors"
    model.write_bytes(b"test model fixture")
    voice.write_bytes(b"test voice fixture")
    model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
    voice_hash = hashlib.sha256(voice.read_bytes()).hexdigest()
    inventory_path = tmp_path / "state/presence/voice_verification/vera_runtime_inventory.json"
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(json.dumps({
        "schema": "dio.vesper.local_verified_runtime_inventory.v1",
        "evidence_class": "LOCAL_VERIFIED_RUNTIME_INVENTORY",
        "service": {"endpoint": "http://127.0.0.1:8000/tts", "pid": os.getpid(),
                    "command": Path(f"/proc/{os.getpid()}/cmdline").read_bytes().decode().strip("\0").split("\0")},
        "files": [{"role": "model", "path": str(model), "sha256": model_hash},
                  {"role": "voice", "path": str(voice), "sha256": voice_hash}],
        "model_provenance": {"model_id": "fixture", "model_revision": "fixture", "model_sha256": model_hash,
                             "voice_id": "vera", "voice_revision": "fixture", "voice_sha256": voice_hash,
                             "runtime_source": "local_observed_inventory"},
    }))

    proof = verified_vera_runtime_inventory(tmp_path)
    assert proof["runtime_inventory"]["sha256"] == hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    assert proof["model_provenance"]["voice_sha256"] == voice_hash

    with pytest.raises(RuntimeError, match="endpoint"):
        verified_vera_runtime_inventory(tmp_path, base_url="http://127.0.0.1:8999")
    voice.write_bytes(b"different voice fixture")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        verified_vera_runtime_inventory(tmp_path)
