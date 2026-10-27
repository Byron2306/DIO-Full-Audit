from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from presence_core.outlook_identity import OutlookIdentityError, verify_outlook_identity
from presence_core.outlook_ingress import dispatch_outlook_capture


def _token(payload: dict[str, str], secret: str) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw + "." + signature


def test_signed_customer_session_binds_outlook_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "s" * 32
    monkeypatch.setenv("DIO_OUTLOOK_IDENTITY_HMAC", secret)
    receipt = verify_outlook_identity({"sender": "customer@example.org", "session_token": _token({"customer_id": "CUS-1", "sender": "customer@example.org"}, secret)})
    assert receipt["binding_state"] == "verified"
    assert receipt["customer_id"] == "CUS-1"


def test_shared_mailbox_requires_identified_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIO_OUTLOOK_IDENTITY_HMAC", "s" * 32)
    with pytest.raises(OutlookIdentityError, match="operator"):
        verify_outlook_identity({"sender": "shared@example.org", "shared_mailbox": True})


def test_dispatch_claims_capture_once_and_processes_canonical_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "s" * 32
    monkeypatch.setenv("DIO_OUTLOOK_IDENTITY_HMAC", secret)
    capture = {
        "capture_id": "MAILCAP-1",
        "message": {"from": {"emailAddress": {"address": "customer@example.org"}}, "body": {"content": "I need help with an Evidex pack"}},
        "attachments": [],
    }
    path = tmp_path / "outlook_captures" / "MAILCAP-1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(capture))
    token = _token({"customer_id": "CUS-1", "sender": "customer@example.org"}, secret)
    first = dispatch_outlook_capture(tmp_path, tmp_path / "state", "MAILCAP-1", session_token=token)
    replay = dispatch_outlook_capture(tmp_path, tmp_path / "state", "MAILCAP-1", session_token=token)
    assert first["state"] == "completed"
    assert replay == first
