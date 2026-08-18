from __future__ import annotations

import json
from pathlib import Path

from adapters.lingua.communicator import plain_text_from_html, register_communication, requested_language
from presence_core.engine import process_envelope
from scripts.manage_mail_intent import create_intent_from_payload


def _presence_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "telemetry").mkdir()
    (tmp_path / "config" / "routes.json").write_text(
        json.dumps({"routes": [{"product": "homs", "keywords": ["homs", "assessment"]}]}),
        encoding="utf-8",
    )
    return tmp_path


def test_shared_communicator_registers_meaning_without_authority(tmp_path: Path) -> None:
    receipt = register_communication(
        dio_root=tmp_path,
        owner="vesper",
        artifact_type="conversation_response",
        channel="telegram",
        body="Your evidence pack is ready for human review.",
        audience="public",
        correlation_id="CONV-1",
        source_message_id="MSG-1",
        target_language="Afrikaans",
        purpose="status_request",
    )
    assert receipt["semantic_lineage_created"] is True
    assert receipt["translation_state"] == "translation_review_required"
    assert receipt["send_authorized"] is False
    assert receipt["authority_created"] is False
    semantic = json.loads(Path(receipt["object_path"]).read_text(encoding="utf-8"))
    assert semantic["schema"] == "dio.lingua.semantic_object.v1"
    assert semantic["origin"]["product"] == "vesper"
    assert semantic["origin"]["channel"] == "telegram"
    assert semantic["origin"]["target_language"] == "Afrikaans"


def test_common_locale_codes_resolve_to_canonical_lingua_languages() -> None:
    assert requested_language(explicit="en-ZA") == "English"
    assert requested_language(explicit="af_ZA") == "Afrikaans"
    assert requested_language(explicit="zu-ZA") == "isiZulu"
    assert requested_language(explicit="st-ZA") == "Sesotho"
    assert requested_language(explicit="tn-ZA") == "Setswana"


def test_presence_reply_is_bound_to_lingua(tmp_path: Path, monkeypatch) -> None:
    root = _presence_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    result = process_envelope(
        {
            "channel": "telegram",
            "external_user_id": "123",
            "source_message_id": "TG-42",
            "text": "hello Vesper",
            "message_type": "text",
        },
        root,
        {"state_root": "state/presence", "event_log": "telemetry/dio_events.jsonl", "routes_path": "config/routes.json"},
    )
    assert result["reply"]["text"]
    assert result["lingua"]["semantic_lineage_created"] is True
    assert result["lingua"]["owner"] == "vesper"
    assert result["lingua"]["channel"] == "telegram"
    assert result["lingua"]["send_authorized"] is False
    assert result["authority"]["executed_external_action"] is False


def test_mail_intent_registers_plain_meaning_from_html(tmp_path: Path) -> None:
    intent_dir = tmp_path / "state" / "mail_intents"
    event_log = tmp_path / "telemetry" / "events.jsonl"
    source = {
        "mail_intent_id": "MAIL-LINGUA-001",
        "recipient": "client@example.org",
        "subject": "Review-ready Evidex pack",
        "body_html": "<html><body><p>Hello Dr N.</p><p>Your <strong>pack</strong> is ready for review.</p></body></html>",
        "purpose": "review_ready",
        "risk": "routine",
        "product": "evidex",
    }
    intent = create_intent_from_payload(source, intent_dir, event_log)
    assert intent["send_state"] == "draft"
    assert intent["approval"]["required"] is True
    assert intent["lingua"]["semantic_lineage_created"] is True
    assert intent["lingua"]["send_authorized"] is False
    semantic = json.loads(Path(intent["lingua"]["object_path"]).read_text(encoding="utf-8"))
    units = {row["unit_id"]: row["source_text"] for row in semantic["source"]["units"]}
    assert units["SUBJECT"] == "Review-ready Evidex pack"
    assert "Hello Dr N." in units["BODY"]
    assert "<strong>" not in units["BODY"]


def test_html_plain_text_preserves_words_not_markup() -> None:
    plain = plain_text_from_html("<p>Hello &amp; welcome.</p><p>Human <b>approval</b> remains.</p>")
    assert "Hello & welcome." in plain
    assert "Human approval remains." in plain
    assert "<b>" not in plain
