from __future__ import annotations

import base64
import json
import pytest

from scripts import sync_vesper_presence_edge as sync


def _voice_attachment() -> dict:
    audio = b"OggS" + b"voice" * 20
    return {
        "provider": "telegram",
        "provider_file_id": "voice-file-1",
        "file_name": "telegram-voice.ogg",
        "mime_type": "audio/ogg",
        "file_size": len(audio),
        "sha256": sync.hashlib.sha256(audio).hexdigest(),
        "content_b64": base64.b64encode(audio).decode("ascii"),
    }


def _event() -> dict:
    return {
        "id": 1,
        "update_id": "9001",
        "body_text": json.dumps(
            {
                "update_id": 9001,
                "message": {
                    "message_id": 77,
                    "from": {"id": 123, "first_name": "Byron"},
                    "chat": {"id": 456},
                    "voice": {
                        "file_id": "voice-file-1",
                        "mime_type": "audio/ogg",
                    },
                },
            }
        ),
    }


def test_hf_voice_transcription_is_refused_by_sovereign_runtime(monkeypatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    monkeypatch.setenv("DIO_PRESENCE_ASR_MODEL", "openai/whisper-large-v3-turbo")
    calls = []

    def forbidden_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Hugging Face network access must not occur.")

    monkeypatch.setattr(sync, "urlopen", forbidden_urlopen)

    with pytest.raises(
        sync.PermanentPresenceError,
        match="disabled by DIO Phase 9 sovereign runtime",
    ):
        sync.transcribe_voice_with_hf(_voice_attachment())

    assert calls == [], "Refused transcription must not make an external request."


def test_telegram_voice_hf_mode_is_refused_without_external_transcription(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-test-token")
    monkeypatch.setenv("DIO_PRESENCE_VOICE_TRANSCRIPTION", "hf")
    monkeypatch.setattr(
        sync, "telegram_download_attachment",
        lambda *args, **kwargs: _voice_attachment(),
    )
    hf_calls = []

    def forbidden_hf_call(attachment):
        hf_calls.append(attachment)
        raise AssertionError("Telegram voice must not be sent to Hugging Face.")

    monkeypatch.setattr(sync, "transcribe_voice_with_hf", forbidden_hf_call)

    with pytest.raises(
        sync.PermanentPresenceError,
        match="disabled by DIO Phase 9 sovereign runtime",
    ):
        sync.telegram_to_envelope(_event())

    assert hf_calls == [], "The refused HF mode must not call the external provider."


def test_voice_without_transcription_does_not_enter_document_quarantine(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-test-token")
    monkeypatch.delenv("DIO_PRESENCE_VOICE_TRANSCRIPTION", raising=False)
    monkeypatch.setattr(sync, "telegram_download_attachment", lambda *args, **kwargs: _voice_attachment())

    envelope = sync.telegram_to_envelope(_event())

    assert envelope["message_type"] == "voice"
    assert envelope["attachment"] is None
    assert "transcription is not enabled" in envelope["text"].lower()
    assert envelope["metadata"]["voice_source"]["sha256"] == _voice_attachment()["sha256"]
