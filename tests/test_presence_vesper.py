from __future__ import annotations

import json
from pathlib import Path

from presence_core.authority import (
    authorize_external_reply,
    bind_external_action_receipt,
    telegram_reply_switch_enabled,
)
from presence_core.router import route_message


def test_vesper_is_canonical_presence_identity() -> None:
    cfg = json.loads(Path("config/presence.json").read_text(encoding="utf-8"))
    assert cfg["identity"] == {"name": "Vesper", "role": "DIO Presence Core", "legacy_alias": "Lilith"}
    assert cfg["external_replies"]["default_enabled"] is False
    assert cfg["external_replies"]["receipt_required"] is True
    assert cfg["llm"]["tool_authority"] is False


def test_external_reply_switch_is_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", raising=False)
    assert telegram_reply_switch_enabled() is False
    result = {
        "decision": {"intent": "general_info"},
        "reply": {"text": "Hello"},
        "authority": {"spend_authorized": False, "fulfilment_released": False, "attachment_processed": False},
    }
    receipt = authorize_external_reply({"channel": "telegram"}, result)
    assert receipt["authorized"] is False
    assert "external_reply_switch_disabled" in receipt["reasons"]
    assert receipt["spend_authorized"] is False
    assert receipt["fulfilment_release_authorized"] is False
    assert receipt["attachment_processing_authorized"] is False


def test_enabled_reply_still_refuses_side_effect_authority(monkeypatch) -> None:
    monkeypatch.setenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "1")
    result = {
        "decision": {"intent": "general_info"},
        "reply": {"text": "Hello"},
        "authority": {"spend_authorized": True, "fulfilment_released": False, "attachment_processed": False},
    }
    receipt = authorize_external_reply({"channel": "telegram"}, result)
    assert receipt["authorized"] is False
    assert "reply_path_cannot_spend" in receipt["reasons"]


def test_successful_send_is_explicitly_bound_to_receipt(monkeypatch) -> None:
    monkeypatch.setenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "true")
    result = {
        "decision": {"intent": "general_info"},
        "reply": {"text": "Hello"},
        "authority": {"spend_authorized": False, "fulfilment_released": False, "attachment_processed": False},
    }
    receipt = authorize_external_reply({"channel": "telegram"}, result)
    assert receipt["authorized"] is True
    bound = bind_external_action_receipt(result, receipt, sent=True)
    assert bound["authority"]["presence_identity"]["name"] == "Vesper"
    assert bound["authority"]["executed_external_action"] is True
    assert bound["authority"]["external_action_type"] == "telegram_reply"


def test_vesper_aliases_route_without_removing_legacy_alias() -> None:
    routes = Path("config/routes.json")
    assert route_message("hi vesper", "public", routes).intent == "general_info"
    assert route_message("hi lilith", "public", routes).intent == "general_info"
    assert route_message("morning vesper", "operator", routes).intent == "operator_summary"
