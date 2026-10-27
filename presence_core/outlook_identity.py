from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping


class OutlookIdentityError(ValueError):
    pass


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
        if str(payload.get("sender") or "").lower() != sender or not payload.get("customer_id"):
            raise OutlookIdentityError("Outlook identity session token does not bind this sender.")
        customer_id = str(payload["customer_id"])
        method = "signed_customer_session"
    elif request.get("operator_id"):
        customer_id = str(request.get("customer_id") or "")
        if not customer_id:
            raise OutlookIdentityError("Operator Outlook binding requires customer_id.")
        method = "identified_operator"
    else:
        raise OutlookIdentityError("Outlook sender is unverified; signed session or operator binding required.")
    return {"schema": "dio.outlook_identity_binding.v1", "binding_state": "verified", "customer_id": customer_id, "sender": sender, "method": method, "verified_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
