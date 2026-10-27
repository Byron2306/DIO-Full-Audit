from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


class OutlookIdentityError(ValueError):
    pass


def _utc_timestamp(value: Any, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutlookIdentityError(f"Outlook identity session token has invalid {field}.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OutlookIdentityError(f"Outlook identity session token {field} must be timezone-aware.")
    return parsed.astimezone(timezone.utc)


def verify_outlook_identity(request: Mapping[str, Any]) -> dict[str, Any]:
    sender = str(request.get("sender") or "").strip().lower()
    if not sender:
        raise OutlookIdentityError("Outlook identity requires a sender address.")
    if request.get("shared_mailbox") and not request.get("operator_id"):
        raise OutlookIdentityError("Shared Outlook mailbox binding requires an identified operator.")
    token = str(request.get("session_token") or "")
    if token:
        try:
            raw, supplied = token.rsplit(".", 1)
            payload = json.loads(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            raise OutlookIdentityError("Outlook identity session token is malformed.") from exc
        secret = os.getenv("DIO_OUTLOOK_IDENTITY_HMAC", "")
        expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not secret or not hmac.compare_digest(supplied, expected):
            raise OutlookIdentityError("Outlook identity session token is invalid.")
        if not isinstance(payload, Mapping):
            raise OutlookIdentityError("Outlook identity session token payload is invalid.")
        if str(payload.get("sender") or "").lower() != sender or not payload.get("customer_id"):
            raise OutlookIdentityError("Outlook identity session token does not bind this sender.")
        issued_at = _utc_timestamp(payload.get("issued_at"), field="issued_at")
        expires_at = _utc_timestamp(payload.get("expires_at"), field="expires_at")
        now = datetime.now(timezone.utc)
        if issued_at > now + timedelta(seconds=30) or expires_at <= now:
            raise OutlookIdentityError("Outlook identity session token is outside its validity window.")
        if expires_at <= issued_at or expires_at - issued_at > timedelta(hours=24):
            raise OutlookIdentityError("Outlook identity session token lifetime is invalid.")
        customer_id = str(payload["customer_id"])
        method = "signed_customer_session"
    elif request.get("operator_id"):
        customer_id = str(request.get("customer_id") or "")
        if not customer_id:
            raise OutlookIdentityError("Operator Outlook binding requires customer_id.")
        method = "identified_operator"
    else:
        raise OutlookIdentityError("Outlook sender is unverified; signed session or operator binding required.")
    return {"schema": "dio.outlook_identity_binding.v1", "binding_state": "verified", "customer_id": customer_id, "sender": sender, "method": method, "verified_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), **({"session_expires_at": expires_at.replace(microsecond=0).isoformat()} if method == "signed_customer_session" else {})}
