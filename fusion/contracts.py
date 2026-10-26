from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "dio_fusion_assertion.schema.json"
ASSERTION_TYPES = {
    "evidence",
    "observation",
    "challenge",
    "requirement",
    "authority",
    "capability_request",
    "decision",
    "receipt",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def assertion_fingerprint(assertion: dict[str, Any]) -> str:
    body = dict(assertion)
    body.pop("fingerprint", None)
    body.pop("assertion_id", None)
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def make_assertion(
    *,
    assertion_type: str,
    issuer_system: str,
    issuer_role: str,
    subject_kind: str,
    subject_ref: str,
    payload: dict[str, Any],
    source_refs: list[str] | None = None,
    case_id: str | None = None,
    parent_assertion_id: str | None = None,
    epistemic_state: str = "UNVERIFIED",
    authority_grade: str = "source_backed",
    trust_state: str = "captured_untrusted",
    freshness_state: str = "unknown",
    human_required: bool = False,
    kernel_authorized: bool = False,
    external_release_authorized: bool = False,
    created_at: str | None = None,
) -> dict[str, Any]:
    if assertion_type not in ASSERTION_TYPES:
        raise ValueError(f"Unsupported assertion type: {assertion_type}")
    created_at = created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    row: dict[str, Any] = {
        "schema": "dio.fusion.assertion.v1",
        "assertion_type": assertion_type,
        "issuer": {"system_id": issuer_system, "role": issuer_role},
        "subject": {"kind": subject_kind, "ref": subject_ref},
        "payload": payload,
        "epistemic": {
            "state": epistemic_state,
            "authority_grade": authority_grade,
            "trust_state": trust_state,
            "freshness_state": freshness_state,
        },
        "authority": {
            "kernel_authority": "Valinor",
            "kernel_authorized": bool(kernel_authorized),
            "external_release_authorized": bool(external_release_authorized),
            "human_required": bool(human_required),
        },
        "lineage": {
            "case_id": case_id,
            "parent_assertion_id": parent_assertion_id,
            "source_refs": list(dict.fromkeys(source_refs or [])),
        },
        "created_at": created_at,
    }
    row["fingerprint"] = assertion_fingerprint(row)
    row["assertion_id"] = f"FUS-{row['fingerprint'][:16].upper()}"
    validate_assertion(row)
    return row


def validate_assertion(assertion: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(assertion)
    expected = assertion_fingerprint(assertion)
    if assertion.get("fingerprint") != expected:
        raise ValueError("Fusion assertion fingerprint mismatch.")
    issuer = str((assertion.get("issuer") or {}).get("system_id") or "")
    authority = assertion.get("authority") or {}
    if authority.get("kernel_authorized") and issuer != "valinor":
        raise ValueError("Only Valinor may assert kernel_authorized=true.")
    if authority.get("external_release_authorized") and issuer not in {"human", "authorized_human"}:
        raise ValueError("Only an explicit human authority receipt may assert external_release_authorized=true.")
    if assertion.get("assertion_type") == "challenge" and authority.get("kernel_authorized"):
        raise ValueError("Challenge assertions cannot carry kernel authorization.")
