from __future__ import annotations

import base64
import json

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


def test_hf_voice_transcription_is_read_only_semantic_input(monkeypatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    monkeypatch.setenv("DIO_PRESENCE_ASR_MODEL", "openai/whisper-large-v3-turbo")
    calls = []

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            return json.dumps({"text": "I've got eighty papers to mark."}).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return Response()

    monkeypatch.setattr(sync, "urlopen", fake_urlopen)

    receipt = sync.transcribe_voice_with_hf(_voice_attachment())

    request, timeout = calls[0]
    assert request.full_url == "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3-turbo"
    assert request.get_header("Authorization") == "Bearer hf-test-token"
    assert request.get_header("Content-type") == "audio/ogg"
    assert request.data.startswith(b"OggS")
    assert timeout == 60
    assert receipt["text"] == "I've got eighty papers to mark."
    assert receipt["provider"] == "hf-inference"
    assert receipt["model"] == "openai/whisper-large-v3-turbo"
    assert receipt["audio_sha256"] == _voice_attachment()["sha256"]
    assert receipt["authority_created"] is False
    assert receipt["external_processing"] is True


def test_telegram_voice_becomes_transcript_not_document_attachment(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-test-token")
    monkeypatch.setenv("DIO_PRESENCE_VOICE_TRANSCRIPTION", "hf")
    monkeypatch.setattr(sync, "telegram_download_attachment", lambda *args, **kwargs: _voice_attachment())
    monkeypatch.setattr(
        sync,
        "transcribe_voice_with_hf",
        lambda attachment: {
            "schema": "dio.vesper.voice_transcription.v1",
            "text": "I've got 80 student papers to mark. What would you suggest?",
            "provider": "hf-inference",
            "model": "openai/whisper-large-v3-turbo",
            "audio_sha256": attachment["sha256"],
            "authority_created": False,
            "external_processing": True,
        },
    )

    envelope = sync.telegram_to_envelope(_event())

    assert envelope["message_type"] == "voice"
    assert envelope["text"] == "I've got 80 student papers to mark. What would you suggest?"
    assert envelope["attachment"] is None
    assert envelope["metadata"]["telegram_chat_id"] == "456"
    assert envelope["metadata"]["voice_source"]["provider_file_id"] == "voice-file-1"
    assert envelope["metadata"]["voice_source"]["sha256"] == _voice_attachment()["sha256"]
    assert envelope["metadata"]["voice_transcription"]["provider"] == "hf-inference"
    assert envelope["metadata"]["voice_transcription"]["authority_created"] is False


def test_voice_without_transcription_does_not_enter_document_quarantine(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-test-token")
    monkeypatch.delenv("DIO_PRESENCE_VOICE_TRANSCRIPTION", raising=False)
    monkeypatch.setattr(sync, "telegram_download_attachment", lambda *args, **kwargs: _voice_attachment())

    envelope = sync.telegram_to_envelope(_event())

    assert envelope["message_type"] == "voice"
    assert envelope["attachment"] is None
    assert "transcription is not enabled" in envelope["text"].lower()
    assert envelope["metadata"]["voice_source"]["sha256"] == _voice_attachment()["sha256"]
