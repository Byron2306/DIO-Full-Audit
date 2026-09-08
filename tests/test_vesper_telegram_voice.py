from __future__ import annotations

from pathlib import Path

import pytest

from presence_core.telegram_transport import send_telegram_reply


def _envelope() -> dict:
    return {
        "channel": "telegram",
        "external_user_id": "123",
        "metadata": {"telegram_chat_id": "456"},
    }


def _result(*, voice_eligible: bool = True) -> dict:
    return {
        "decision": {"intent": "general_info", "product": None},
        "reply": {
            "text": "Vesper is ready.",
            "voice_eligible": voice_eligible,
            "voice_plan": {
                "schema": "dio.vesper.voice_render_plan.v1",
                "profile_id": "vera_pocket_public",
                "backend": "pocket_tts",
                "model": "vera",
                "voice_url": "vera",
                "language": "English",
                "state": "ready_for_internal_render",
                "reasons": [],
                "delivery_mode": "warm_professional",
                "identity_locked": True,
                "send_authority_created": False,
                "public_default_authorized": True,
            },
        },
        "authority": {
            "executed_external_action": False,
            "spend_authorized": False,
            "fulfilment_released": False,
            "attachment_processed": False,
        },
    }


def test_authorized_voice_reply_renders_vera_then_sends_voice(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "1")
    monkeypatch.setenv("DIO_PRESENCE_TELEGRAM_VOICE_REPLIES", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    calls: list[tuple] = []

    def fake_synthesize_voice(*, text, output_path, plan, timeout):
        assert text == "Vesper is ready."
        assert plan["profile_id"] == "vera_pocket_public"
        Path(output_path).write_bytes(b"RIFF" + b"0" * 128)
        return {
            "schema": "dio.vesper.voice_render_receipt.v1",
            "profile_id": "vera_pocket_public",
            "backend": "pocket_tts",
            "voice_url": "vera",
            "audio_path": str(output_path),
            "external_action_executed": False,
            "send_authorized": False,
        }

    def fake_convert(wav_path, ogg_path):
        assert Path(wav_path).read_bytes().startswith(b"RIFF")
        Path(ogg_path).write_bytes(b"OggS" + b"0" * 128)
        return {
            "schema": "dio.vesper.telegram_voice_encoding.v1",
            "source_path": str(wav_path),
            "voice_path": str(ogg_path),
            "codec": "opus",
            "external_action_executed": False,
            "send_authorized": False,
        }

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"ok": True, "result": {"message_id": 77}}

    def fake_post(url, *, data=None, files=None, json=None, timeout=None):
        calls.append((url, data, files, json, timeout))
        assert url.endswith("/sendVoice")
        assert data == {"chat_id": "456"}
        assert files and "voice" in files
        return Response()

    monkeypatch.setattr("presence_core.telegram_transport.synthesize_voice", fake_synthesize_voice)
    monkeypatch.setattr("presence_core.telegram_transport.convert_wav_to_telegram_voice", fake_convert)
    monkeypatch.setattr("presence_core.telegram_transport.httpx.post", fake_post)

    sent, error, receipt = send_telegram_reply(_envelope(), _result(), root=tmp_path)

    assert sent is True
    assert error is None
    assert len(calls) == 1
    assert receipt["authorized"] is True
    assert receipt["delivery_mode"] == "voice"
    assert receipt["voice_render"]["profile_id"] == "vera_pocket_public"
    assert receipt["voice_encoding"]["codec"] == "opus"
    assert receipt["external_action_type"] == "telegram_voice_reply"
    assert receipt["spend_authorized"] is False
    assert receipt["fulfilment_release_authorized"] is False


def test_voice_render_failure_falls_back_to_text_before_send_attempt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "1")
    monkeypatch.setenv("DIO_PRESENCE_TELEGRAM_VOICE_REPLIES", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    def fail_render(**kwargs):
        raise RuntimeError("pocket unavailable")

    calls: list[tuple] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"ok": True, "result": {"message_id": 78}}

    def fake_post(url, *, data=None, files=None, json=None, timeout=None):
        calls.append((url, data, files, json, timeout))
        assert url.endswith("/sendMessage")
        assert json == {"chat_id": "456", "text": "Vesper is ready."}
        return Response()

    monkeypatch.setattr("presence_core.telegram_transport.synthesize_voice", fail_render)
    monkeypatch.setattr("presence_core.telegram_transport.httpx.post", fake_post)

    sent, error, receipt = send_telegram_reply(_envelope(), _result(), root=tmp_path)

    assert sent is True
    assert error is None
    assert len(calls) == 1
    assert receipt["delivery_mode"] == "text"
    assert receipt["voice_fallback_reason"].startswith("voice_prepare_failed:")
    assert receipt["external_action_type"] == "telegram_reply"


def test_voice_transport_failure_does_not_double_send_text(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "1")
    monkeypatch.setenv("DIO_PRESENCE_TELEGRAM_VOICE_REPLIES", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    def fake_synthesize_voice(*, text, output_path, plan, timeout):
        Path(output_path).write_bytes(b"RIFF" + b"0" * 128)
        return {"profile_id": "vera_pocket_public", "external_action_executed": False, "send_authorized": False}

    def fake_convert(wav_path, ogg_path):
        Path(ogg_path).write_bytes(b"OggS" + b"0" * 128)
        return {"codec": "opus", "external_action_executed": False, "send_authorized": False}

    calls: list[str] = []

    def fail_post(url, **kwargs):
        calls.append(url)
        raise RuntimeError("telegram timeout")

    monkeypatch.setattr("presence_core.telegram_transport.synthesize_voice", fake_synthesize_voice)
    monkeypatch.setattr("presence_core.telegram_transport.convert_wav_to_telegram_voice", fake_convert)
    monkeypatch.setattr("presence_core.telegram_transport.httpx.post", fail_post)

    with pytest.raises(RuntimeError, match="telegram timeout"):
        send_telegram_reply(_envelope(), _result(), root=tmp_path)

    assert len(calls) == 1
    assert calls[0].endswith("/sendVoice")


def test_text_reply_remains_default_when_voice_not_eligible(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "1")
    monkeypatch.setenv("DIO_PRESENCE_TELEGRAM_VOICE_REPLIES", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    calls: list[str] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"ok": True}

    def fake_post(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr("presence_core.telegram_transport.httpx.post", fake_post)

    sent, error, receipt = send_telegram_reply(_envelope(), _result(voice_eligible=False), root=tmp_path)

    assert sent is True
    assert error is None
    assert calls == ["https://api.telegram.org/bottest-token/sendMessage"]
    assert receipt["delivery_mode"] == "text"


def test_reply_gate_blocks_voice_render_and_transport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", raising=False)
    monkeypatch.setenv("DIO_PRESENCE_TELEGRAM_VOICE_REPLIES", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    def forbidden(*args, **kwargs):
        raise AssertionError("render or transport must not run before authorization")

    monkeypatch.setattr("presence_core.telegram_transport.synthesize_voice", forbidden)
    monkeypatch.setattr("presence_core.telegram_transport.httpx.post", forbidden)

    sent, error, receipt = send_telegram_reply(_envelope(), _result(), root=tmp_path)

    assert sent is False
    assert error == "external_reply_switch_disabled"
    assert receipt["authorized"] is False
