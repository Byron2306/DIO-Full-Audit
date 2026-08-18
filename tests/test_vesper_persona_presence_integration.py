from __future__ import annotations

import json
from pathlib import Path

from presence_core.engine import process_envelope


ROOT = Path(__file__).resolve().parents[1]


def _root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "telemetry").mkdir(parents=True)
    (tmp_path / "config" / "routes.json").write_text(
        json.dumps({"routes": [{"product": "homs", "keywords": ["homs", "assessment"]}]}), encoding="utf-8"
    )
    for name in ("vesper_persona_lab.json", "vesper_voice_profiles.json"):
        (tmp_path / "config" / name).write_text((ROOT / "config" / name).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_presence_returns_stable_persona_avatar_and_voice_plan(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    monkeypatch.setenv("DIO_VESPER_PERSONA_LAB", "1")
    cfg = {"state_root": "state/presence", "event_log": "telemetry/dio_events.jsonl", "routes_path": "config/routes.json"}
    envelope = {"channel": "webchat", "external_user_id": "visitor-9", "text": "Tell me about HOMS", "message_type": "text", "metadata": {"locale": "en-ZA"}}
    first = process_envelope(envelope, root, cfg)
    second = process_envelope(envelope, root, cfg)
    assert first["persona"]["experimental_assignment"] is True
    assert first["persona"]["assignment_id"] == second["persona"]["assignment_id"]
    assert first["reply"]["avatar_id"] == second["reply"]["avatar_id"]
    assert first["reply"]["voice_plan"]["profile_id"] == first["persona"]["package"]["voice_profile_id"]
    assert first["lingua"]["persona_context"]["assignment_id"] == first["persona"]["assignment_id"]
    assert first["authority"]["executed_external_action"] is False


def test_aggro_regulation_does_not_change_persona_identity(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    monkeypatch.setenv("DIO_VESPER_PERSONA_LAB", "1")
    cfg = {"state_root": "state/presence", "event_log": "telemetry/dio_events.jsonl", "routes_path": "config/routes.json"}
    base = {"channel": "webchat", "external_user_id": "visitor-10", "message_type": "text"}
    calm = process_envelope({**base, "text": "Tell me about HOMS"}, root, cfg)
    aggro = process_envelope({**base, "text": "THIS FUCKING THING DOESN'T WORK!!!"}, root, cfg)
    assert calm["persona"]["assignment_id"] == aggro["persona"]["assignment_id"]
    assert calm["reply"]["avatar_id"] == aggro["reply"]["avatar_id"]
    assert aggro["interaction"]["delivery_policy"]["mode"] == "calm_service_recovery"
    assert aggro["interaction"]["delivery_policy"]["sales_pressure_allowed"] is False
