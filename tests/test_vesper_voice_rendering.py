from __future__ import annotations

import json
from pathlib import Path

import pytest

from presence_core.voice import build_voice_plan, synthesize_piper_http


ROOT = Path(__file__).resolve().parents[1]


def _root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(parents=True)
    source = json.loads((ROOT / "config" / "vesper_voice_profiles.json").read_text(encoding="utf-8"))
    (tmp_path / "config" / "vesper_voice_profiles.json").write_text(json.dumps(source), encoding="utf-8")
    return tmp_path


def test_piper_baseline_is_internal_render_only(tmp_path: Path) -> None:
    root = _root(tmp_path)
    plan = build_voice_plan(root=root, language="English", interaction=None, requested_profile="piper_free_local_baseline")
    assert plan["state"] == "ready_for_internal_render"
    assert plan["backend"] == "piper_http"
    assert plan["send_authority_created"] is False
    assert plan["public_default_authorized"] is False


def test_openvoice2_candidate_refuses_without_reference_provenance(tmp_path: Path) -> None:
    root = _root(tmp_path)
    plan = build_voice_plan(root=root, language="English", interaction=None, requested_profile="openvoice2_sa_warm_candidate")
    assert plan["state"] == "not_renderable"
    assert "openvoice_target_embedding_not_assigned" in plan["reasons"]
    assert "voice_reference_consent_not_verified" in plan["reasons"]
    assert "voice_reference_provenance_missing" in plan["reasons"]
    assert plan["send_authority_created"] is False


def test_voice_language_mismatch_refuses(tmp_path: Path) -> None:
    root = _root(tmp_path)
    plan = build_voice_plan(root=root, language="Afrikaans", interaction=None, requested_profile="piper_free_local_baseline")
    assert plan["state"] == "not_renderable"
    assert "voice_language_mismatch" in plan["reasons"]


def test_piper_receipt_cannot_send(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    plan = build_voice_plan(root=root, language="English", interaction={"delivery_policy": {"mode": "proof_first", "voice": {"piper_length_scale": 1.03}}}, requested_profile="piper_free_local_baseline")

    class Response:
        content = b"RIFF" + (b"\x00" * 64)
        def raise_for_status(self) -> None:
            return None

    def fake_post(*args, **kwargs):
        payload = kwargs["json"]
        assert payload["voice"] == "en_US-lessac-medium"
        assert payload["length_scale"] == 1.03
        return Response()

    monkeypatch.setattr("presence_core.voice.httpx.post", fake_post)
    receipt = synthesize_piper_http(text="Vesper test.", output_path=tmp_path / "vesper.wav", plan=plan)
    assert receipt["backend"] == "piper_http"
    assert receipt["delivery_mode"] == "proof_first"
    assert receipt["send_authorized"] is False
    assert receipt["external_action_executed"] is False
    assert receipt["identity_authority_created"] is False


def test_empty_voice_text_refuses(tmp_path: Path) -> None:
    root = _root(tmp_path)
    plan = build_voice_plan(root=root, language="English", interaction=None, requested_profile="piper_free_local_baseline")
    with pytest.raises(ValueError):
        synthesize_piper_http(text="", output_path=tmp_path / "empty.wav", plan=plan)
