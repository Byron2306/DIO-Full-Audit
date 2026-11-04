"""Read-only verifier for customer-supplied Seraph telemetry chain exports.

The hash calculation mirrors backend/services/telemetry_chain.py. This does not
verify agent signatures, source identity, persistence, or live telemetry.
"""

from __future__ import annotations

import hashlib
import json
import base64
from typing import Any


EVENT_GENESIS = hashlib.sha256(b"SERAPH_GENESIS_EVENT").hexdigest()
AUDIT_GENESIS = hashlib.sha256(b"SERAPH_GENESIS_AUDIT").hexdigest()
ALGORITHM_REF = "cross_folder_variants/Metatron-triune-outbound-gate/A_CODE/backend/services/telemetry_chain.py"


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _verify_attestation(row: dict[str, Any], *, record_type: str, case_id: str) -> str:
    """Verify a detached record signature; embedded keys prove integrity, not identity."""
    attestation = row.get("attestation")
    if not isinstance(attestation, dict) or attestation.get("algorithm") != "Ed25519":
        return "MISSING"
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        public_key = base64.b64decode(attestation["public_key_b64"], validate=True)
        signature = base64.b64decode(attestation["signature_b64"], validate=True)
        body = {key: value for key, value in row.items() if key != "attestation"}
        signed = json.dumps({"record_type": record_type, "case_id": case_id, "record": body}, sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(public_key).hexdigest() != attestation.get("key_id"):
            return "INVALID"
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, signed)
        return "VALID_UNTRUSTED_KEY"
    except Exception:
        return "INVALID"


def assess_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    request = payload.get("seraph_telemetry")
    if request is None:
        return {"state": "NOT_REQUESTED", "required": False, "event_count": 0, "audit_count": 0,
                "signature_state": "NOT_ASSESSED", "algorithm_ref": ALGORITHM_REF}
    if not isinstance(request, dict) or not isinstance(request.get("required"), bool):
        raise ValueError("seraph_telemetry requires an object with explicit boolean required")
    events = request.get("event_chain") or []
    audits = request.get("audit_chain") or []
    if not isinstance(events, list) or not isinstance(audits, list) or len(events) + len(audits) > 10000:
        raise ValueError("seraph_telemetry chains must be bounded lists")
    required = request["required"]
    case_id = str(payload.get("case_id") or "")
    if not case_id:
        raise ValueError("seraph_telemetry requires a case_id for scope binding")
    state = "HASH_CHAIN_VERIFIED" if events or audits else ("MISSING" if required else "NOT_SUPPLIED")
    event_head, audit_head = EVENT_GENESIS, AUDIT_GENESIS
    seen: set[str] = set()
    attestations: list[str] = []
    for row in events:
        if not isinstance(row, dict) or not isinstance(row.get("data"), dict):
            state = "INVALID_CHAIN"; break
        event_id = str(row.get("event_id") or "")
        if (not event_id or event_id in seen or row.get("prev_hash") != event_head
                or (case_id and row["data"].get("case_id") != case_id)):
            state = "INVALID_CHAIN"; break
        seen.add(event_id)
        expected = _digest({key: row.get(key) for key in ("event_id", "event_type", "timestamp", "data", "prev_hash")})
        if row.get("event_hash") != expected:
            state = "INVALID_CHAIN"; break
        attestations.append(_verify_attestation(row, record_type="event", case_id=case_id))
        event_head = expected
    seen.clear()
    if state != "INVALID_CHAIN":
        for row in audits:
            if not isinstance(row, dict):
                state = "INVALID_CHAIN"; break
            record_id = str(row.get("record_id") or "")
            if (not record_id or record_id in seen or row.get("prev_hash") != audit_head
                    or (case_id and row.get("case_id") != case_id)):
                state = "INVALID_CHAIN"; break
            seen.add(record_id)
            expected = _digest({key: row.get(key) for key in ("record_id", "timestamp", "principal", "action", "targets", "prev_hash")})
            if row.get("record_hash") != expected:
                state = "INVALID_CHAIN"; break
            attestations.append(_verify_attestation(row, record_type="audit", case_id=case_id))
            audit_head = expected
    if state == "HASH_CHAIN_VERIFIED" and (
        request.get("event_head") != event_head or request.get("audit_head") != audit_head
    ):
        state = "INVALID_CHAIN"
    valid_attestation_count = sum(x == "VALID_UNTRUSTED_KEY" for x in attestations)
    attestation_scope = (
        "complete record envelope, including fields outside the legacy hash chain"
        if valid_attestation_count == len(attestations) and valid_attestation_count > 0 else
        f"complete record envelope on {valid_attestation_count} of {len(attestations)} records; remaining records unsigned or unverified"
        if valid_attestation_count > 0 else "none"
    )
    return {
        "state": state, "required": required, "event_count": len(events), "audit_count": len(audits),
        "event_head": event_head, "audit_head": audit_head,
        "signature_state": ("INVALID" if "INVALID" in attestations else
                            "VERIFIED_UNTRUSTED_KEY" if attestations and all(x == "VALID_UNTRUSTED_KEY" for x in attestations) else
                            "PARTIAL" if any(x == "VALID_UNTRUSTED_KEY" for x in attestations) else
                            "UNVERIFIED" if events else "NOT_ASSESSED"),
        "source_identity_state": "UNVERIFIED" if events or audits else "NOT_ASSESSED",
        "signed_record_count": valid_attestation_count,
        "attestation_count": len(attestations),
        "case_scope_state": "EVENT_HASH_BOUND_AUDIT_DECLARED" if events and audits else (
            "EVENT_HASH_BOUND" if events else ("AUDIT_DECLARED_UNHASHED" if audits else "NOT_ASSESSED")),
        "unhashed_fields": [] if attestations and all(x == "VALID_UNTRUSTED_KEY" for x in attestations) else ["event.severity", "event.agent_id", "event.signature", "event.trace_id",
                            "audit.case_id", "audit.result", "audit.evidence_refs"],
        "attestation_scope": attestation_scope,
        "trust_anchor_state": "EMBEDDED_KEY_ONLY_UNTRUSTED" if valid_attestation_count else "NOT_SUPPLIED",
        "algorithm_ref": ALGORITHM_REF,
    }
