from __future__ import annotations

import json
from pathlib import Path

from adapters.lingua.interaction_regulator import observe_interaction
from presence_core.engine import process_envelope


def make_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "telemetry").mkdir()
    (tmp_path / "config" / "routes.json").write_text(
        json.dumps({"routes": [{"product": "homs", "keywords": ["homs", "assessment"]}]}),
        encoding="utf-8",
    )
    return tmp_path


def test_hostile_complaint_disables_sales_pressure_and_humour(tmp_path: Path) -> None:
    receipt = observe_interaction(
        state_root=tmp_path,
        conversation_id="CONV-AGGRO",
        text="THIS IS FUCKING USELESS!!! It is still broken and nobody replied.",
        channel="webchat",
        role="public",
        source_message_id="M1",
    )
    policy = receipt["delivery_policy"]
    assert policy["mode"] == "calm_service_recovery"
    assert policy["sales_pressure_allowed"] is False
    assert policy["humour_allowed"] is False
    assert policy["single_next_action"] is True
    assert policy["voice"]["piper_length_scale"] > 1.0
    assert receipt["emotion_diagnosed"] is False
    assert receipt["personality_diagnosed"] is False
    assert receipt["external_action_authorized"] is False
    assert Path(receipt["receipt_path"]).is_file()


def test_positive_profanity_is_not_treated_as_hostile(tmp_path: Path) -> None:
    receipt = observe_interaction(
        state_root=tmp_path,
        conversation_id="CONV-HAPPY",
        text="This is fucking great, tell me more about HOMS",
        channel="telegram",
        role="public",
    )
    assert receipt["signals"]["positive_engagement"]["detected"] is True
    assert receipt["signals"]["hostility"]["score"] < 0.35
    assert receipt["delivery_policy"]["mode"] == "warm_professional"
    assert receipt["delivery_policy"]["sales_pressure_allowed"] is True


def test_confusion_prefers_clarity_without_sales_pressure(tmp_path: Path) -> None:
    receipt = observe_interaction(
        state_root=tmp_path,
        conversation_id="CONV-CONFUSED",
        text="I don't understand. What does that mean and how does this work?",
        channel="webchat",
        role="public",
    )
    policy = receipt["delivery_policy"]
    assert policy["mode"] == "clarify_gently"
    assert policy["jargon_level"] == "low"
    assert policy["sales_pressure_allowed"] is False
    assert policy["ask_at_most_one_question"] is True


def test_skepticism_prioritizes_proof(tmp_path: Path) -> None:
    receipt = observe_interaction(
        state_root=tmp_path,
        conversation_id="CONV-SKEPTIC",
        text="How do I know this is real? Show me proof before I pay anything.",
        channel="webchat",
        role="public",
    )
    policy = receipt["delivery_policy"]
    assert policy["mode"] == "proof_first"
    assert policy["proof_priority"] == "high"
    assert policy["humour_allowed"] is False


def test_presence_binds_interaction_policy_into_lingua_reply(tmp_path: Path, monkeypatch) -> None:
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    cfg = {"state_root": "state/presence", "event_log": "telemetry/dio_events.jsonl", "routes_path": "config/routes.json"}
    result = process_envelope(
        {
            "channel": "telegram",
            "external_user_id": "123",
            "source_message_id": "TG-AGGRO-1",
            "text": "This is fucking useless!!! I need HOMS and nobody replied.",
            "message_type": "text",
        },
        root,
        cfg,
    )
    assert result["interaction"]["delivery_policy"]["mode"] == "calm_service_recovery"
    assert result["interaction"]["delivery_policy"]["sales_pressure_allowed"] is False
    assert result["lingua"]["interaction_context"]["delivery_mode"] == "calm_service_recovery"
    assert result["lingua"]["interaction_context"]["emotion_diagnosed"] is False
    semantic = json.loads(Path(result["lingua"]["object_path"]).read_text(encoding="utf-8"))
    assert semantic["origin"]["interaction_context"]["delivery_mode"] == "calm_service_recovery"
    assert result["authority"]["executed_external_action"] is False
