from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from presence_core.outlook_identity import OutlookIdentityError, verify_outlook_identity
from presence_core.outlook_ingress import dispatch_outlook_capture


def _token(payload: dict[str, str], secret: str) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw + "." + signature


def _session(*, customer_id: str = "CUS-1", sender: str = "customer@example.org", expires_in_minutes: int = 15) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "customer_id": customer_id,
        "sender": sender,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=expires_in_minutes)).isoformat(),
    }


def test_signed_customer_session_binds_outlook_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "s" * 32
    monkeypatch.setenv("DIO_OUTLOOK_IDENTITY_HMAC", secret)
    receipt = verify_outlook_identity({"sender": "customer@example.org", "session_token": _token(_session(), secret)})
    assert receipt["binding_state"] == "verified"
    assert receipt["customer_id"] == "CUS-1"
    assert receipt["session_expires_at"]


def test_signed_customer_session_refuses_expired_or_unbounded_token(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "s" * 32
    monkeypatch.setenv("DIO_OUTLOOK_IDENTITY_HMAC", secret)
    with pytest.raises(OutlookIdentityError, match="validity window"):
        verify_outlook_identity({"sender": "customer@example.org", "session_token": _token(_session(expires_in_minutes=-1), secret)})
    with pytest.raises(OutlookIdentityError, match="invalid expires_at"):
        verify_outlook_identity({"sender": "customer@example.org", "session_token": _token({"customer_id": "CUS-1", "sender": "customer@example.org", "issued_at": datetime.now(timezone.utc).isoformat()}, secret)})


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
    token = _token(_session(), secret)
    monkeypatch.setattr("presence_core.outlook_ingress.process_envelope", lambda envelope, *_args, **_kwargs: {"conversation_id": "CONV-1", "envelope": envelope})
    first = dispatch_outlook_capture(tmp_path, tmp_path / "state", "MAILCAP-1", session_token=token)
    replay = dispatch_outlook_capture(tmp_path, tmp_path / "state", "MAILCAP-1", session_token=token)
    assert first["state"] == "completed"
    assert first["canonical_conversation_id"] == "CONV-1"
    assert replay == first
