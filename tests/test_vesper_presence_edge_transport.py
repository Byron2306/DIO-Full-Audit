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
    module = load_module()
    monkeypatch.setenv("DIO_PRESENCE_OPERATOR_SHARED_SECRET", "x" * 40)
    signed = module.locally_sign_telegram_event(telegram_event())
    assert signed["key_id"] == "operator-edge"
    assert len(signed["signature"]) == 64
    assert signed["nonce"].startswith("tg_123_")
    envelope = json.loads(signed["body_text"])
    assert envelope["external_user_id"] == "42"
    assert "DIO_PRESENCE_OPERATOR_SHARED_SECRET" not in signed["body_text"]


def test_missing_local_operator_secret_is_retryable(monkeypatch):
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
