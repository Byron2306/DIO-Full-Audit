from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_vesper_presence_edge.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sync_vesper_presence_edge", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def sample_event(body_text: str) -> dict:
    return {
        "id": 7,
        "event_key": "presence:operator-edge:nonce:hash",
        "key_id": "operator-edge",
        "signature": "a" * 64,
        "signed_timestamp": "1787031000",
        "nonce": "abcdefghijklmnopQRSTUV",
        "body_text": body_text,
        "received_at": "2026-08-18T05:30:00Z",
        "attempts": 0,
    }


def telegram_event(text: str = "Tell me what HOMS does") -> dict:
    return {
        "id": 9,
        "event_key": "telegram:123:hash",
        "update_id": "123",
        "body_text": json.dumps({
            "update_id": 123,
            "message": {
                "message_id": 77,
                "from": {"id": 42, "first_name": "Byron"},
                "chat": {"id": 42, "type": "private"},
                "text": text,
            },
        }, separators=(",", ":")),
        "received_at": "2026-08-18T05:30:00Z",
        "attempts": 0,
    }


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return self.payload


def test_forward_preserves_exact_signed_body(monkeypatch):
    module = load_module()
    body = '{"channel":"telegram", "external_user_id":"42","text":"hello  there"}'
    captured = {}

    def fake_urlopen(request, timeout):
        captured["data"] = request.data
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        return FakeResponse({"ok": True})

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    module.forward_to_core(sample_event(body), "http://127.0.0.1:8787")
    assert captured["data"] == body.encode("utf-8")
    assert captured["headers"]["x-dio-presence-key-id"] == "operator-edge"
    assert captured["headers"]["x-dio-presence-signature"] == "a" * 64


def test_core_4xx_is_permanent_rejection(monkeypatch):
    module = load_module()

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"detail":"Invalid presence signature."}'))

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    with pytest.raises(module.PermanentPresenceError):
        module.forward_to_core(sample_event('{"channel":"telegram","external_user_id":"42","text":"hello"}'), "http://127.0.0.1:8787")


def test_core_network_failure_stays_retryable(monkeypatch):
    module = load_module()

    def fake_urlopen(request, timeout):
        raise URLError("offline")

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    with pytest.raises(module.TransientPresenceError):
        module.forward_to_core(sample_event('{"channel":"telegram","external_user_id":"42","text":"hello"}'), "http://127.0.0.1:8787")


def test_config_refuses_public_core(tmp_path):
    module = load_module()
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "base_url": "https://dio-presence-gateway-staging.example",
        "edge_token_path": "/tmp/token",
        "core_url": "https://public-core.example",
    }))
    with pytest.raises(module.PresenceEdgeError):
        module.read_config(path)


def test_telegram_text_update_becomes_operator_signable_presence_envelope():
    module = load_module()
    envelope = module.telegram_to_envelope(telegram_event())
    assert envelope["schema"] == "dio.presence_ingress.v2"
    assert envelope["channel"] == "telegram"
    assert envelope["external_user_id"] == "42"
    assert envelope["display_name"] == "Byron"
    assert envelope["source_message_id"] == "77"
    assert envelope["message_type"] == "text"
    assert envelope["text"] == "Tell me what HOMS does"
    assert envelope["metadata"]["telegram_update_id"] == "123"
    assert envelope["metadata"]["telegram_chat_id"] == "42"
    assert envelope["metadata"]["custody"] == "cloudflare_d1_provider_authenticated_transport_only"
    assert envelope["attachment"] is None


def test_telegram_local_signing_keeps_dio_shared_secret_off_cloudflare(monkeypatch):
    monkeypatch.setenv("DIO_OPERATOR_TELEGRAM_IDS", "42")
    module = load_module()
    monkeypatch.setenv("DIO_PRESENCE_OPERATOR_SHARED_SECRET", "x" * 40)
    signed = module.locally_sign_telegram_event(telegram_event())
    assert signed["key_id"] == "operator-edge"
    assert len(signed["signature"]) == 64
    assert signed["nonce"].startswith("tg_operator_123_")
    envelope = json.loads(signed["body_text"])
    assert envelope["external_user_id"] == "42"
    assert "DIO_PRESENCE_OPERATOR_SHARED_SECRET" not in signed["body_text"]


def test_missing_local_operator_secret_is_retryable(monkeypatch):
    monkeypatch.setenv("DIO_OPERATOR_TELEGRAM_IDS", "42")
    module = load_module()
    monkeypatch.delenv("DIO_PRESENCE_OPERATOR_SHARED_SECRET", raising=False)
    with pytest.raises(module.TransientPresenceError):
        module.locally_sign_telegram_event(telegram_event())


def test_replay_409_can_close_telegram_delivery_without_duplicate_processing(monkeypatch):
    module = load_module()
    event = sample_event('{"channel":"telegram","external_user_id":"42","text":"hello"}')

    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 409, "Conflict", {}, io.BytesIO(b'{"detail":"Replay detected."}'))

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    result = module.forward_to_core(event, "http://127.0.0.1:8787", replay_is_success=True)
    assert result["duplicate_delivery"] is True


def web_voice_event() -> dict:
    audio = b"synthetic-web-audio"
    return {
        "id": 17,
        "event_key": "web:VWC-0123456789ABCDEF:voice:test",
        "conversation_id": "VWC-0123456789ABCDEF",
        "body_text": json.dumps(
            {
                "channel": "webchat",
                "external_user_id":
                    "WEB-0123456789ABCDEF0123456789ABCDEF",
                "text":
                    "Web voice input awaiting local transcription.",
                "message_type": "voice",
                "metadata": {
                    "web_conversation_id":
                        "VWC-0123456789ABCDEF",
                    "web_surface": "dio_web",
                    "voice_input": {
                        "content_b64":
                            __import__("base64")
                            .b64encode(audio)
                            .decode("ascii"),
                        "mime_type": "audio/webm",
                        "custody":
                            "cloudflare_d1_transport_only",
                        "authority_created": False,
                    },
                },
            },
            separators=(",", ":"),
        ),
        "received_at": "2026-09-15T12:00:00Z",
        "attempts": 0,
    }


def test_web_voice_transcription_replaces_transport_audio_before_signing(
    monkeypatch,
):
    module = load_module()

    monkeypatch.setenv(
        "DIO_PRESENCE_PUBLIC_SHARED_SECRET",
        "p" * 40,
    )

    def fake_transcribe(attachment):
        assert attachment["mime_type"] == "audio/webm"
        assert attachment["content_b64"]

        return {
            "schema":
                "dio.vesper.voice_transcription.v1",
            "text":
                "What would HOMS Assess cost for 80 students?",
            "provider": "hf-inference",
            "model":
                "openai/whisper-large-v3-turbo",
            "audio_sha256": "b" * 64,
            "audio_bytes": 19,
            "mime_type": "audio/webm",
            "truncated": False,
            "authority_created": False,
            "external_processing": True,
            "execution_authority_created": False,
            "send_authority_created": False,
        }

    monkeypatch.setattr(
        module,
        "transcribe_voice_with_hf",
        fake_transcribe,
    )

    signed = module.locally_sign_web_event(
        web_voice_event()
    )

    assert signed["key_id"] == "public-edge"
    assert len(signed["signature"]) == 64

    envelope = json.loads(
        signed["body_text"]
    )

    assert envelope["channel"] == "webchat"
    assert envelope["message_type"] == "voice"

    assert envelope["text"] == (
        "What would HOMS Assess cost for 80 students?"
    )

    metadata = envelope["metadata"]

    assert "voice_input" not in metadata
    assert "content_b64" not in signed["body_text"]

    assert metadata["voice_source"]["provider"] == "web"
    assert (
        metadata["voice_source"]["custody"]
        == "cloudflare_d1_transport_only"
    )
    assert (
        metadata["voice_source"]["authority_created"]
        is False
    )

    assert (
        metadata["voice_transcription"]
        ["authority_created"]
        is False
    )


def test_web_voice_client_authority_fields_are_refused(
    monkeypatch,
):
    module = load_module()

    monkeypatch.setenv(
        "DIO_PRESENCE_PUBLIC_SHARED_SECRET",
        "p" * 40,
    )

    event = web_voice_event()
    envelope = json.loads(event["body_text"])

    envelope["role"] = "operator"
    envelope["_trusted_edge_key_id"] = (
        "operator-edge"
    )

    event["body_text"] = json.dumps(
        envelope,
        separators=(",", ":"),
    )

    with pytest.raises(
        module.PermanentPresenceError,
    ):
        module.locally_sign_web_event(event)


def test_web_voice_reply_is_presentation_only_and_preserves_canonical_text(
    monkeypatch,
    tmp_path,
):
    module = load_module()

    monkeypatch.setattr(
        module,
        "ROOT",
        tmp_path,
    )

    captured = {}

    def fake_synthesize_voice(
        *,
        text,
        output_path,
        plan,
        timeout,
    ):
        captured["text"] = text
        captured["plan"] = plan
        captured["timeout"] = timeout

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_bytes(
            b"RIFFsynthetic-wav"
        )

        return {
            "profile_id":
                "vera_pocket_public",
            "backend": "pocket_tts",
            "audio_sha256": "c" * 64,
            "authority_created": False,
        }

    monkeypatch.setattr(
        module,
        "synthesize_voice",
        fake_synthesize_voice,
    )

    canonical = (
        "Pricing sits between R350 and R1,800."
    )

    result = {
        "schema":
            "dio.presence_response.v2",
        "reply": {
            "text": canonical,
            "voice_eligible": True,
            "voice_plan": {
                "state":
                    "ready_for_internal_render",
                "profile_id":
                    "vera_pocket_public",
                "backend":
                    "pocket_tts",
            },
        },
    }

    rendered = module.render_web_voice_reply(
        event_id=17,
        result=result,
    )

    assert (
        rendered["reply"]["text"]
        == canonical
    )

    assert (
        captured["text"]
        == "Pricing sits between 350 rand and 1,800 rand."
    )

    audio = rendered["reply"]["audio"]

    assert audio["state"] == "ready"
    assert audio["mime_type"] == "audio/wav"
    assert (
        audio["profile_id"]
        == "vera_pocket_public"
    )
    assert audio["backend"] == "pocket_tts"
    assert audio["presentation_only"] is True
    assert audio["authority_created"] is False
    assert (
        audio["spoken_text_normalized"]
        is True
    )
    assert audio["content_b64"]


def test_non_voice_web_message_never_invokes_transcription(
    monkeypatch,
):
    module = load_module()

    def refuse_transcription(_attachment):
        raise AssertionError(
            "Text web message invoked ASR"
        )

    monkeypatch.setattr(
        module,
        "transcribe_voice_with_hf",
        refuse_transcription,
    )

    envelope = {
        "channel": "webchat",
        "external_user_id":
            "WEB-0123456789ABCDEF0123456789ABCDEF",
        "text": "Tell me about Evidex.",
        "message_type": "text",
        "metadata": {
            "web_conversation_id":
                "VWC-0123456789ABCDEF",
            "web_surface": "dio_web",
        },
    }

    result = (
        module.prepare_web_semantic_envelope(
            {
                "id": 18,
                "conversation_id":
                    "VWC-0123456789ABCDEF",
            },
            envelope,
        )
    )

    assert result == envelope


def test_web_reply_outbox_round_trip_is_exact(
    monkeypatch,
    tmp_path,
):
    module = load_module()

    monkeypatch.setattr(
        module,
        "ROOT",
        tmp_path,
    )

    result = {
        "schema":
            "dio.presence_response.v2",
        "reply": {
            "text":
                "Canonical reply.",
        },
        "authority": {
            "executed_external_action":
                False,
        },
    }

    path = module.save_web_reply_outbox(
        event_id=17,
        conversation_id=
            "VWC-0123456789ABCDEF",
        result=result,
    )

    assert path.exists()

    loaded = module.load_web_reply_outbox(
        17
    )

    assert loaded == {
        "schema":
            "dio.vesper.web_reply_outbox.v1",
        "event_id":
            17,
        "conversation_id":
            "VWC-0123456789ABCDEF",
        "result":
            result,
    }


def test_web_reply_outbox_delete_is_idempotent(
    monkeypatch,
    tmp_path,
):
    module = load_module()

    monkeypatch.setattr(
        module,
        "ROOT",
        tmp_path,
    )

    module.save_web_reply_outbox(
        event_id=18,
        conversation_id=
            "VWC-0123456789ABCDEF",
        result={
            "reply": {
                "text":
                    "Stored once.",
            }
        },
    )

    assert (
        module.delete_web_reply_outbox(18)
        is True
    )

    assert (
        module.delete_web_reply_outbox(18)
        is False
    )


def test_web_reply_outbox_rejects_corruption(
    monkeypatch,
    tmp_path,
):
    module = load_module()

    monkeypatch.setattr(
        module,
        "ROOT",
        tmp_path,
    )

    path = module.web_reply_outbox_path(
        19
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        '{"schema":"wrong"}',
        encoding="utf-8",
    )

    with pytest.raises(
        module.PermanentPresenceError
    ):
        module.load_web_reply_outbox(
            19
        )


def test_web_reply_retry_uses_outbox_without_reexecuting_core(
    monkeypatch,
    tmp_path,
):
    module = load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)

    event = {
        "id": 21,
        "conversation_id": "VWC-0123456789ABCDEF",
    }

    original = {
        "schema": "dio.presence_response.v2",
        "reply": {"text": "Original canonical reply."},
    }

    core_calls = []
    deliveries = []

    monkeypatch.setattr(
        module,
        "locally_sign_web_event",
        lambda event: {"body_text": "{}"},
    )

    def fake_core(*args, **kwargs):
        core_calls.append(1)
        return original

    def fake_edge(url, token, method="GET", payload=None):
        deliveries.append(payload)
        if len(deliveries) == 1:
            raise module.PresenceEdgeError(
                "synthetic reply delivery failure"
            )
        return {"stored": True}

    monkeypatch.setattr(
        module,
        "forward_to_core",
        fake_core,
    )
    monkeypatch.setattr(
        module,
        "render_web_voice_reply",
        lambda **kwargs: kwargs["result"],
    )
    monkeypatch.setattr(
        module,
        "edge_request",
        fake_edge,
    )

    first = module.sync_web_event_batch(
        events=[event],
        core_url="http://127.0.0.1:8787",
        base_url="https://edge.example",
        token="test",
        reply_path="/api/presence/web-replies",
    )

    assert first[2] == [21]
    assert len(core_calls) == 1

    second = module.sync_web_event_batch(
        events=[event],
        core_url="http://127.0.0.1:8787",
        base_url="https://edge.example",
        token="test",
        reply_path="/api/presence/web-replies",
    )

    assert second[0] == [21]
    assert second[2] == []
    assert len(core_calls) == 1
    assert deliveries[0] == deliveries[1]
    assert deliveries[1]["result"] == original


def test_web_reply_outbox_deleted_only_after_full_ack(
    monkeypatch,
    tmp_path,
):
    module = load_module()

    monkeypatch.setattr(
        module,
        "ROOT",
        tmp_path,
    )

    for event_id in (31, 32):
        module.save_web_reply_outbox(
            event_id=event_id,
            conversation_id=
                "VWC-0123456789ABCDEF",
            result={
                "reply": {
                    "text":
                        f"Reply {event_id}.",
                },
            },
        )

    deleted = (
        module.cleanup_web_reply_outbox_after_ack(
            [31, 32],
            {"acknowledged": 2},
        )
    )

    assert deleted == [31, 32]

    assert (
        module.load_web_reply_outbox(31)
        is None
    )

    assert (
        module.load_web_reply_outbox(32)
        is None
    )


def test_web_reply_outbox_preserved_on_partial_ack(
    monkeypatch,
    tmp_path,
):
    module = load_module()

    monkeypatch.setattr(
        module,
        "ROOT",
        tmp_path,
    )

    for event_id in (33, 34):
        module.save_web_reply_outbox(
            event_id=event_id,
            conversation_id=
                "VWC-0123456789ABCDEF",
            result={
                "reply": {
                    "text":
                        f"Reply {event_id}.",
                },
            },
        )

    deleted = (
        module.cleanup_web_reply_outbox_after_ack(
            [33, 34],
            {"acknowledged": 1},
        )
    )

    assert deleted == []

    assert (
        module.load_web_reply_outbox(33)
        is not None
    )

    assert (
        module.load_web_reply_outbox(34)
        is not None
    )


def test_web_attachment_transport_becomes_canonical_attachment():
    module = load_module()

    content = b"hello from web attachment"

    envelope = {
        "channel": "webchat",
        "external_user_id": "WEB-TEST",
        "text": "Please route this file.",
        "message_type": "text",
        "metadata": {
            "web_conversation_id":
                "VWC-0123456789ABCDEF",
            "web_attachment_input": {
                "file_name": "evidence.txt",
                "mime_type": "text/plain",
                "content_b64":
                    __import__("base64")
                    .b64encode(content)
                    .decode("ascii"),
                "transport_size_bytes":
                    len(content),
                "custody":
                    "cloudflare_d1_transport_only",
                "authority_created": False,
            },
        },
    }

    result = module.prepare_web_semantic_envelope(
        {"id": 71},
        envelope,
    )

    attachment = result["attachment"]

    assert attachment["provider"] == "web"
    assert attachment["file_name"] == "evidence.txt"
    assert attachment["mime_type"] == "text/plain"
    assert attachment["file_size"] == len(content)
    assert attachment["sha256"] == (
        __import__("hashlib")
        .sha256(content)
        .hexdigest()
    )


def test_web_attachment_raw_transport_wrapper_removed_before_signing():
    module = load_module()

    content = b"bounded custody"

    envelope = {
        "channel": "webchat",
        "external_user_id": "WEB-TEST",
        "text": "Attached.",
        "message_type": "text",
        "metadata": {
            "web_conversation_id":
                "VWC-0123456789ABCDEF",
            "web_attachment_input": {
                "file_name": "note.txt",
                "mime_type": "text/plain",
                "content_b64":
                    __import__("base64")
                    .b64encode(content)
                    .decode("ascii"),
                "transport_size_bytes":
                    len(content),
            },
        },
    }

    result = module.prepare_web_semantic_envelope(
        {"id": 72},
        envelope,
    )

    assert (
        "web_attachment_input"
        not in result["metadata"]
    )
    assert "attachment" in result


def test_web_attachment_transport_size_mismatch_refused():
    module = load_module()

    content = b"size matters"

    envelope = {
        "channel": "webchat",
        "external_user_id": "WEB-TEST",
        "text": "Attached.",
        "message_type": "text",
        "metadata": {
            "web_conversation_id":
                "VWC-0123456789ABCDEF",
            "web_attachment_input": {
                "file_name": "note.txt",
                "mime_type": "text/plain",
                "content_b64":
                    __import__("base64")
                    .b64encode(content)
                    .decode("ascii"),
                "transport_size_bytes":
                    len(content) + 1,
            },
        },
    }

    with pytest.raises(
        module.PermanentPresenceError,
        match="byte count",
    ):
        module.prepare_web_semantic_envelope(
            {"id": 73},
            envelope,
        )


def test_public_telegram_document_becomes_canonical_attachment(
    monkeypatch,
):
    module = load_module()

    event = telegram_event("")
    event["bot_surface"] = "public"

    update = json.loads(event["body_text"])
    update["message"].pop("text", None)
    update["message"]["document"] = {
        "file_id": "DOC-123",
        "file_name": "evidence.pdf",
        "mime_type": "application/pdf",
    }
    event["body_text"] = json.dumps(
        update,
        separators=(",", ":"),
    )

    monkeypatch.setenv(
        "DIO_TELEGRAM_PUBLIC_BOT_TOKEN",
        "public-token",
    )

    monkeypatch.setattr(
        module,
        "telegram_download_attachment",
        lambda token, file_id, file_name, mime_type: {
            "provider": "telegram",
            "provider_file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": 12,
            "sha256": "a" * 64,
            "content_b64": "JVBERi0xLjQK",
        },
    )

    envelope = module.telegram_to_envelope(
        event
    )

    assert envelope["channel"] == "telegram"
    assert envelope["message_type"] == "document"

    attachment = envelope["attachment"]

    assert attachment["provider"] == "telegram"
    assert attachment["provider_file_id"] == "DOC-123"
    assert attachment["file_name"] == "evidence.pdf"
    assert attachment["mime_type"] == "application/pdf"

    assert (
        envelope["metadata"]["telegram_bot_surface"]
        == "public"
    )

    assert "role" not in envelope
    assert "_trusted_edge_role" not in envelope


def test_public_telegram_photo_becomes_canonical_attachment(
    monkeypatch,
):
    module = load_module()

    event = telegram_event("")
    event["bot_surface"] = "public"

    update = json.loads(event["body_text"])
    update["message"].pop("text", None)
    update["message"]["photo"] = [
        {
            "file_id": "PHOTO-SMALL",
        },
        {
            "file_id": "PHOTO-LARGE",
        },
    ]
    event["body_text"] = json.dumps(
        update,
        separators=(",", ":"),
    )

    monkeypatch.setenv(
        "DIO_TELEGRAM_PUBLIC_BOT_TOKEN",
        "public-token",
    )

    captured = {}

    def fake_download(
        token,
        file_id,
        file_name,
        mime_type,
    ):
        captured["token"] = token
        captured["file_id"] = file_id

        return {
            "provider": "telegram",
            "provider_file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": 3,
            "sha256": "b" * 64,
            "content_b64": "/9j/",
        }

    monkeypatch.setattr(
        module,
        "telegram_download_attachment",
        fake_download,
    )

    envelope = module.telegram_to_envelope(
        event
    )

    assert envelope["message_type"] == "photo"
    assert captured["token"] == "public-token"
    assert captured["file_id"] == "PHOTO-LARGE"

    attachment = envelope["attachment"]

    assert attachment["provider"] == "telegram"
    assert attachment["file_name"] == "telegram-image.jpg"
    assert attachment["mime_type"] == "image/jpeg"

    assert (
        envelope["metadata"]["telegram_bot_surface"]
        == "public"
    )


def test_public_telegram_attachment_signs_only_as_public_edge(
    monkeypatch,
):
    module = load_module()

    event = telegram_event("")
    event["bot_surface"] = "public"

    update = json.loads(event["body_text"])
    update["message"].pop("text", None)
    update["message"]["document"] = {
        "file_id": "DOC-PUBLIC",
        "file_name": "sample.txt",
        "mime_type": "text/plain",
    }
    event["body_text"] = json.dumps(
        update,
        separators=(",", ":"),
    )

    monkeypatch.setenv(
        "DIO_TELEGRAM_PUBLIC_BOT_TOKEN",
        "public-token",
    )

    monkeypatch.setenv(
        "DIO_PRESENCE_PUBLIC_SHARED_SECRET",
        "p" * 40,
    )

    monkeypatch.setattr(
        module,
        "telegram_download_attachment",
        lambda *args, **kwargs: {
            "provider": "telegram",
            "provider_file_id": "DOC-PUBLIC",
            "file_name": "sample.txt",
            "mime_type": "text/plain",
            "file_size": 4,
            "sha256": "c" * 64,
            "content_b64": "dGVzdA==",
        },
    )

    signed = module.locally_sign_telegram_event(
        event
    )

    assert signed["key_id"] == "public-edge"

    envelope = json.loads(
        signed["body_text"]
    )

    assert (
        envelope["metadata"]["telegram_bot_surface"]
        == "public"
    )

    assert "role" not in envelope
    assert "_trusted_edge_role" not in envelope
    assert "_trusted_edge_key_id" not in envelope


def test_public_telegram_oversize_attachment_is_refused(
    monkeypatch,
):
    module = load_module()

    monkeypatch.setenv(
        "DIO_PRESENCE_MAX_ATTACHMENT_BYTES",
        "8",
    )

    class FakeHeaders(dict):
        def get(self, key, default=None):
            return super().get(key.lower(), default)

    class FakeBinaryResponse:
        def __init__(self, data: bytes):
            self._data = data
            self.headers = FakeHeaders(
                {
                    "content-length":
                        str(len(data)),
                }
            )

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, *args):
            return self._data

    calls = []

    def fake_urlopen(request, timeout):
        url = request.full_url
        calls.append(url)

        if "/getFile" in url:
            return FakeResponse(
                {
                    "ok": True,
                    "result": {
                        "file_path":
                            "documents/big.bin"
                    },
                }
            )

        return FakeBinaryResponse(
            b"0123456789"
        )

    monkeypatch.setattr(
        module,
        "urlopen",
        fake_urlopen,
    )

    with pytest.raises(
        module.PermanentPresenceError,
        match="exceeds the local Presence limit",
    ):
        module.telegram_download_attachment(
            "public-token",
            "BIG-DOC",
            "big.bin",
            "application/octet-stream",
        )

    assert any(
        "/getFile" in url
        for url in calls
    )


def test_voice_transcription_prefers_hf_and_skips_local(
    monkeypatch,
):
    module = load_module()

    attachment = {
        "content_b64": "dGVzdA==",
        "sha256": "",
        "mime_type": "audio/webm",
    }

    expected = {
        "text": "HF transcript",
        "provider": "hf-inference",
        "authority_created": False,
    }

    monkeypatch.setattr(
        module,
        "transcribe_voice_with_hf",
        lambda value: expected,
    )

    def local_must_not_run(value):
        raise AssertionError(
            "local fallback ran despite HF success"
        )

    monkeypatch.setattr(
        module,
        "transcribe_voice_with_local_whisper",
        local_must_not_run,
    )

    result = module.transcribe_voice(
        attachment
    )

    assert result is expected
    assert result["provider"] == "hf-inference"
    assert result["authority_created"] is False


def test_voice_transcription_falls_back_locally_on_hf_transient(
    monkeypatch,
):
    module = load_module()

    attachment = {
        "content_b64": "dGVzdA==",
        "sha256": "",
        "mime_type": "audio/webm",
    }

    def hf_failure(value):
        raise module.TransientPresenceError(
            "HF HTTP 500"
        )

    monkeypatch.setattr(
        module,
        "transcribe_voice_with_hf",
        hf_failure,
    )

    monkeypatch.setattr(
        module,
        "transcribe_voice_with_local_whisper",
        lambda value: {
            "text": "Local transcript",
            "provider": "faster-whisper-local",
            "authority_created": False,
            "external_processing": False,
            "fallback_used": True,
        },
    )

    result = module.transcribe_voice(
        attachment
    )

    assert result["text"] == "Local transcript"
    assert result["provider"] == "faster-whisper-local"
    assert result["fallback_used"] is True
    assert result["authority_created"] is False
    assert result["external_processing"] is False
    assert "HF HTTP 500" in result[
        "primary_provider_failure"
    ]


def test_voice_transcription_both_fail_remains_transient(
    monkeypatch,
):
    module = load_module()

    attachment = {
        "content_b64": "dGVzdA==",
        "sha256": "",
        "mime_type": "audio/webm",
    }

    monkeypatch.setattr(
        module,
        "transcribe_voice_with_hf",
        lambda value: (_ for _ in ()).throw(
            module.TransientPresenceError(
                "HF HTTP 500"
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "transcribe_voice_with_local_whisper",
        lambda value: (_ for _ in ()).throw(
            module.TransientPresenceError(
                "local unavailable"
            )
        ),
    )

    with pytest.raises(
        module.TransientPresenceError,
        match="Voice transcription unavailable",
    ):
        module.transcribe_voice(
            attachment
        )
