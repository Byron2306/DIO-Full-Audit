from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from products.governed_case import record_action_receipt, validate_case

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dio_authority_plane.json"

AUTHORITY_RECEIPT_SCHEMA = "dio.authority.receipt.v1"
CAPABILITY_LEASE_SCHEMA = "dio.capability.lease.v1"
VALINOR_AUTH_SCHEMA = "dio.valinor.authorization.v1"
ARDA_IDENTITY_SCHEMA = "dio.arda.execution_identity.v1"
EXECUTION_RECEIPT_SCHEMA = "dio.execution.receipt.v1"


class AuthorityPlaneError(RuntimeError):
    pass


class ValinorRuntimeProtocol(Protocol):
    def syscall(self, entity_id: str, syscall_name: str) -> str: ...
    def access_secret(self, entity_id: str, secret_name: str) -> bool: ...
    def open_socket(self, entity_id: str) -> Any: ...
    def send_ipc(self, entity_id: str) -> Any: ...
    def write_stream(self, entity_id: str, target: str) -> Any: ...
    def apply_flow_shape(self, entity_id: str) -> Any: ...


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(row: dict[str, Any], *, omit: tuple[str, ...]) -> str:
    body = copy.deepcopy(row)
    for field in omit:
        body.pop(field, None)
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _timestamp(value: str | None = None) -> str:
    if value:
        parsed = _parse_time(value)
        assert parsed is not None
        return parsed.isoformat()
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AuthorityPlaneError("Authority timestamps must include a timezone.")
    return parsed.astimezone(timezone.utc)


def _sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _action_index(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["action_id"]): row for row in case.get("actions") or [] if row.get("action_id")}


def _gate_index(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["gate_id"]): row for row in case.get("gates") or [] if row.get("gate_id")}


def load_authority_config(path: Path | None = None) -> dict[str, Any]:
    payload = json.loads((path or CONFIG_PATH).read_text(encoding="utf-8"))
    if payload.get("schema") != "dio.authority_plane.config.v1":
        raise AuthorityPlaneError("Unsupported authority-plane config schema.")
    if payload.get("kernel_authority") != "Valinor":
        raise AuthorityPlaneError("Valinor must remain the sole kernel authority.")
    if payload.get("execution_identity_authority") != "ARDA":
        raise AuthorityPlaneError("ARDA must remain execution identity/attestation authority, not kernel authority.")
    return payload


def _validate_action_ready(case: dict[str, Any], action_id: str) -> dict[str, Any]:
    validate_case(case)
    actions = _action_index(case)
    if action_id not in actions:
        raise AuthorityPlaneError(f"Unknown governed action: {action_id}")
    action = actions[action_id]
    if action.get("state") != "approved":
        raise AuthorityPlaneError("Capability authority requires an already-approved Governed Case action.")
    gates = _gate_index(case)
    non_allow = [gate_id for gate_id in action.get("required_gate_ids") or [] if gates.get(gate_id, {}).get("state") != "allow"]
    if non_allow:
        raise AuthorityPlaneError("Capability authority cannot bypass non-ALLOW gates: " + ",".join(non_allow))
    return action


def _action_digest(case: dict[str, Any], action: dict[str, Any]) -> str:
    return _sha256_digest(
        {
            "case_id": case["case_id"],
            "action_id": action["action_id"],
            "action_type": action["action_type"],
            "description": action["description"],
            "risk_tier": action["risk_tier"],
            "reversibility": action["reversibility"],
            "required_gate_ids": action["required_gate_ids"],
        }
    )


def make_authority_receipt(
    case: dict[str, Any],
    *,
    action_id: str,
    capability: str,
    actor_id: str,
    actor_type: str,
    authority_scope: list[str],
    verdict: str,
    evidence_refs: list[str] | None = None,
    issued_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Create explicit human/institutional authority for an already-governed action.

    Machine systems may describe prerequisites or recommendations elsewhere, but
    they may not mint a consequential authority receipt here.
    """
    action = _validate_action_ready(case, action_id)
    config = load_authority_config()
    if actor_type not in set(config["granting_actor_types"]):
        raise AuthorityPlaneError("Only explicit human or organisational authority may grant a capability.")
    if verdict not in {"ALLOW", "REFUSE"}:
        raise AuthorityPlaneError("Authority verdict must be ALLOW or REFUSE.")
    scope = list(dict.fromkeys(str(item) for item in authority_scope if str(item)))
    if verdict == "ALLOW" and capability not in scope and "*" not in scope:
        raise AuthorityPlaneError("Authority scope does not include the requested capability.")
    if action["risk_tier"] in {"external", "irreversible"} and verdict == "ALLOW" and "external_release" not in scope:
        raise AuthorityPlaneError("External or irreversible authority requires explicit external_release scope.")

    issued = _timestamp(issued_at)
    expiry = _timestamp(expires_at) if expires_at else None
    if expiry and _parse_time(expiry) <= _parse_time(issued):
        raise AuthorityPlaneError("Authority receipt expiry must be after issuance.")

    row: dict[str, Any] = {
        "schema": AUTHORITY_RECEIPT_SCHEMA,
        "case_id": case["case_id"],
        "action_id": action_id,
        "action_digest": _action_digest(case, action),
        "capability": capability,
        "actor": {"actor_id": actor_id, "actor_type": actor_type},
        "authority_scope": scope,
        "verdict": verdict,
        "evidence_refs": list(dict.fromkeys(evidence_refs or [])),
        "issued_at": issued,
        "expires_at": expiry,
    }
    row["fingerprint"] = _fingerprint(row, omit=("fingerprint", "authority_receipt_id"))
    row["authority_receipt_id"] = f"AUTH-{row['fingerprint'][:16].upper()}"
    validate_authority_receipt(row)
    return row


def validate_authority_receipt(row: dict[str, Any], *, now: str | None = None, require_allow: bool = False) -> None:
    if row.get("schema") != AUTHORITY_RECEIPT_SCHEMA:
        raise AuthorityPlaneError("Unsupported authority receipt schema.")
    expected = _fingerprint(row, omit=("fingerprint", "authority_receipt_id"))
    if row.get("fingerprint") != expected or row.get("authority_receipt_id") != f"AUTH-{expected[:16].upper()}":
        raise AuthorityPlaneError("Authority receipt fingerprint mismatch.")
    actor_type = str((row.get("actor") or {}).get("actor_type") or "")
    if actor_type not in set(load_authority_config()["granting_actor_types"]):
        raise AuthorityPlaneError("Machine/service authority receipts are not accepted.")
    if require_allow and row.get("verdict") != "ALLOW":
        raise AuthorityPlaneError("Capability lease requires an ALLOW authority receipt.")
    expiry = _parse_time(row.get("expires_at"))
    instant = _parse_time(now or _timestamp())
    if expiry and instant and instant >= expiry:
        raise AuthorityPlaneError("Authority receipt is expired.")


def make_capability_lease(
    case: dict[str, Any],
    *,
    action_id: str,
    authority_receipt: dict[str, Any],
    principal_id: str,
    audience: str,
    route_scope: list[str] | None = None,
    output_scope: list[str] | None = None,
    resource_ceiling: dict[str, Any] | None = None,
    consequence_ceiling: str | None = None,
    issued_at: str | None = None,
    expires_at: str,
    maximum_uses: int = 1,
    revocation_epoch: int = 0,
) -> dict[str, Any]:
    action = _validate_action_ready(case, action_id)
    validate_authority_receipt(authority_receipt, now=issued_at, require_allow=True)
    if authority_receipt["case_id"] != case["case_id"] or authority_receipt["action_id"] != action_id:
        raise AuthorityPlaneError("Authority receipt is not bound to this case/action.")
    digest = _action_digest(case, action)
    if authority_receipt["action_digest"] != digest:
        raise AuthorityPlaneError("Authority receipt action binding no longer matches current action.")
    if maximum_uses <= 0 or revocation_epoch < 0:
        raise AuthorityPlaneError("Lease use limit and revocation epoch must be valid.")

    issued = _timestamp(issued_at)
    expiry = _timestamp(expires_at)
    if _parse_time(expiry) <= _parse_time(issued):
        raise AuthorityPlaneError("Capability lease expiry must be after issuance.")
    authority_expiry = _parse_time(authority_receipt.get("expires_at"))
    if authority_expiry and _parse_time(expiry) > authority_expiry:
        raise AuthorityPlaneError("Capability lease cannot outlive its authority receipt.")

    row: dict[str, Any] = {
        "schema": CAPABILITY_LEASE_SCHEMA,
        "case_id": case["case_id"],
        "action_id": action_id,
        "action_digest": digest,
        "capability": authority_receipt["capability"],
        "authority_receipt_id": authority_receipt["authority_receipt_id"],
        "authority_receipt_fingerprint": authority_receipt["fingerprint"],
        "principal_id": principal_id,
        "audience": audience,
        "route_scope": list(dict.fromkeys(route_scope or [])),
        "output_scope": list(dict.fromkeys(output_scope or [])),
        "resource_ceiling": resource_ceiling or {},
        "consequence_ceiling": consequence_ceiling or action["risk_tier"],
        "issued_at": issued,
        "expires_at": expiry,
        "maximum_uses": int(maximum_uses),
        "used_count": 0,
        "revocation_epoch": int(revocation_epoch),
        "state": "active",
        "revoked_at": None,
        "revocation_reason": None,
    }
    row["fingerprint"] = _fingerprint(row, omit=("fingerprint", "lease_id"))
    row["lease_id"] = f"LEASE-{row['fingerprint'][:16].upper()}"
    validate_capability_lease(row, now=issued)
    return row


def validate_capability_lease(row: dict[str, Any], *, now: str | None = None, require_active: bool = True) -> None:
    if row.get("schema") != CAPABILITY_LEASE_SCHEMA:
        raise AuthorityPlaneError("Unsupported capability lease schema.")
    expected = _fingerprint(row, omit=("fingerprint", "lease_id"))
    if row.get("fingerprint") != expected or row.get("lease_id") != f"LEASE-{expected[:16].upper()}":
        raise AuthorityPlaneError("Capability lease fingerprint mismatch.")
    if require_active and row.get("state") != "active":
        raise AuthorityPlaneError(f"Capability lease is not active: {row.get('state')}")
    if int(row.get("used_count", 0)) >= int(row.get("maximum_uses", 0)):
        raise AuthorityPlaneError("Capability lease use limit exhausted.")
    instant = _parse_time(now or _timestamp())
    expiry = _parse_time(row.get("expires_at"))
    if instant and expiry and instant >= expiry:
        raise AuthorityPlaneError("Capability lease is expired.")


def revoke_capability_lease(row: dict[str, Any], *, reason: str, revoked_at: str | None = None) -> dict[str, Any]:
    validate_capability_lease(row)
    if not reason:
        raise AuthorityPlaneError("Lease revocation requires a reason.")
    revoked = copy.deepcopy(row)
    revoked["state"] = "revoked"
    revoked["revoked_at"] = _timestamp(revoked_at)
    revoked["revocation_reason"] = reason
    revoked["fingerprint"] = _fingerprint(revoked, omit=("fingerprint", "lease_id"))
    revoked["lease_id"] = f"LEASE-{revoked['fingerprint'][:16].upper()}"
    return revoked


def authorize_valinor(
    lease: dict[str, Any],
    *,
    entity_id: str,
    operation: str,
    target: str | None = None,
    runtime: ValinorRuntimeProtocol,
    authorized_at: str | None = None,
) -> dict[str, Any]:
    """Obtain kernel authorization for one already-authorized capability lease.

    This authorizes a runtime boundary. It does not itself perform or attest the
    external business/institutional action.
    """
    validate_capability_lease(lease, now=authorized_at)
    if operation not in {"socket", "ipc", "write", "secret", "syscall", "flow"}:
        raise AuthorityPlaneError(f"Unsupported Valinor operation: {operation}")
    if operation in {"write", "secret", "syscall"} and not target:
        raise AuthorityPlaneError(f"Valinor {operation} authorization requires a target.")

    try:
        if operation == "socket":
            result = runtime.open_socket(entity_id)
        elif operation == "ipc":
            result = runtime.send_ipc(entity_id)
        elif operation == "write":
            result = runtime.write_stream(entity_id, str(target))
        elif operation == "secret":
            result = runtime.access_secret(entity_id, str(target))
        elif operation == "syscall":
            result = runtime.syscall(entity_id, str(target))
        else:
            result = runtime.apply_flow_shape(entity_id)
        allowed = True
        state = "VALINOR_ALLOW"
        reason = None
    except PermissionError as exc:
        result = None
        allowed = False
        state = "VALINOR_REFUSE"
        reason = str(exc)

    row: dict[str, Any] = {
        "schema": VALINOR_AUTH_SCHEMA,
        "kernel_authority": "Valinor",
        "lease_id": lease["lease_id"],
        "lease_fingerprint": lease["fingerprint"],
        "case_id": lease["case_id"],
        "action_id": lease["action_id"],
        "action_digest": lease["action_digest"],
        "entity_id": entity_id,
        "operation": operation,
        "target": target,
        "allowed": allowed,
        "state": state,
        "reason": reason,
        "result": result,
        "authorized_at": _timestamp(authorized_at),
        "external_action_executed": False,
    }
    row["fingerprint"] = _fingerprint(row, omit=("fingerprint", "authorization_id"))
    row["authorization_id"] = f"VAL-{row['fingerprint'][:16].upper()}"
    validate_valinor_authorization(row, lease=lease)
    return row


def validate_valinor_authorization(row: dict[str, Any], *, lease: dict[str, Any]) -> None:
    if row.get("schema") != VALINOR_AUTH_SCHEMA or row.get("kernel_authority") != "Valinor":
        raise AuthorityPlaneError("Only canonical Valinor authorization is accepted.")
    expected = _fingerprint(row, omit=("fingerprint", "authorization_id"))
    if row.get("fingerprint") != expected or row.get("authorization_id") != f"VAL-{expected[:16].upper()}":
        raise AuthorityPlaneError("Valinor authorization fingerprint mismatch.")
    if row.get("lease_id") != lease.get("lease_id") or row.get("lease_fingerprint") != lease.get("fingerprint"):
        raise AuthorityPlaneError("Valinor authorization is not bound to this lease.")
    if row.get("action_digest") != lease.get("action_digest"):
        raise AuthorityPlaneError("Valinor authorization action digest mismatch.")
    if row.get("external_action_executed") is not False:
        raise AuthorityPlaneError("Valinor authorization must not claim that the external action was executed.")


def make_arda_execution_identity(
    *,
    node_id: str,
    workload_digest: str,
    attestation_result_id: str,
    attestation_evidence_digest: str,
    evidence_mode: str,
    attestation_status: str,
    environment: str,
    audience: str,
    issued_at: str,
    expires_at: str,
) -> dict[str, Any]:
    """Bind execution to ARDA-attested identity without granting authority."""
    if not workload_digest.startswith("sha256:") or not attestation_evidence_digest.startswith("sha256:"):
        raise AuthorityPlaneError("ARDA execution identity requires sha256 workload and evidence digests.")
    if evidence_mode not in {"simulated", "synthetic", "observed", "enforced"}:
        raise AuthorityPlaneError("Unsupported ARDA evidence mode.")
    if attestation_status not in {"accepted", "rejected"}:
        raise AuthorityPlaneError("Unsupported ARDA attestation status.")
    issued = _timestamp(issued_at)
    expiry = _timestamp(expires_at)
    if _parse_time(expiry) <= _parse_time(issued):
        raise AuthorityPlaneError("ARDA identity expiry must be after issuance.")
    row: dict[str, Any] = {
        "schema": ARDA_IDENTITY_SCHEMA,
        "identity_authority": "ARDA",
        "kernel_authority": False,
        "node_id": node_id,
        "workload_digest": workload_digest,
        "attestation_result_id": attestation_result_id,
        "attestation_evidence_digest": attestation_evidence_digest,
        "evidence_mode": evidence_mode,
        "attestation_status": attestation_status,
        "environment": environment,
        "audience": audience,
        "issued_at": issued,
        "expires_at": expiry,
    }
    row["fingerprint"] = _fingerprint(row, omit=("fingerprint", "execution_identity_id"))
    row["execution_identity_id"] = f"ARDA-{row['fingerprint'][:16].upper()}"
    return row


def validate_arda_execution_identity(row: dict[str, Any], *, now: str | None = None, require_accepted: bool = True) -> None:
    if row.get("schema") != ARDA_IDENTITY_SCHEMA or row.get("identity_authority") != "ARDA":
        raise AuthorityPlaneError("Canonical ARDA execution identity is required.")
    if row.get("kernel_authority") is not False:
        raise AuthorityPlaneError("ARDA execution identity cannot claim kernel authority.")
    expected = _fingerprint(row, omit=("fingerprint", "execution_identity_id"))
    if row.get("fingerprint") != expected or row.get("execution_identity_id") != f"ARDA-{expected[:16].upper()}":
        raise AuthorityPlaneError("ARDA execution identity fingerprint mismatch.")
    if require_accepted and row.get("attestation_status") != "accepted":
        raise AuthorityPlaneError("Execution requires accepted ARDA attestation.")
    expiry = _parse_time(row.get("expires_at"))
    instant = _parse_time(now or _timestamp())
    if expiry and instant and instant >= expiry:
        raise AuthorityPlaneError("ARDA execution identity is expired.")


def record_execution_receipt(
    case: dict[str, Any],
    *,
    action_id: str,
    lease: dict[str, Any],
    valinor_authorization: dict[str, Any],
    arda_identity: dict[str, Any],
    executor_system: str,
    executor_receipt_ref: str,
    success: bool,
    executed_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Accept a bounded executor receipt only after the full authority chain exists.

    Phase 4 does not invoke generic executors. Phase 5 will wire specialist
    executors to this acceptance surface.
    """
    action = _validate_action_ready(case, action_id)
    instant = _timestamp(executed_at)
    validate_capability_lease(lease, now=instant)
    validate_valinor_authorization(valinor_authorization, lease=lease)
    validate_arda_execution_identity(arda_identity, now=instant, require_accepted=True)
    if not valinor_authorization.get("allowed") or valinor_authorization.get("state") != "VALINOR_ALLOW":
        raise AuthorityPlaneError("Execution requires Valinor ALLOW.")
    if lease["case_id"] != case["case_id"] or lease["action_id"] != action_id:
        raise AuthorityPlaneError("Capability lease is not bound to this case/action.")
    if lease["action_digest"] != _action_digest(case, action):
        raise AuthorityPlaneError("Capability lease action digest no longer matches.")
    if arda_identity["audience"] != lease["audience"]:
        raise AuthorityPlaneError("ARDA execution identity audience does not match capability lease audience.")
    if action["risk_tier"] in {"external", "irreversible"} and arda_identity["evidence_mode"] not in {"observed", "enforced"}:
        raise AuthorityPlaneError("External/irreversible execution requires observed or enforced ARDA evidence.")
    if executor_system in {"", "dio_core", "generic_executor"}:
        raise AuthorityPlaneError("Generic DIO execution is forbidden; a bounded specialist executor is required.")
    if not executor_receipt_ref:
        raise AuthorityPlaneError("Bounded execution requires an executor receipt reference.")

    authority_snapshot = {
        "lease_id": lease["lease_id"],
        "valinor_authorization_id": valinor_authorization["authorization_id"],
        "arda_execution_identity_id": arda_identity["execution_identity_id"],
    }
    receipt: dict[str, Any] = {
        "schema": EXECUTION_RECEIPT_SCHEMA,
        "case_id": case["case_id"],
        "action_id": action_id,
        "action_digest": lease["action_digest"],
        "capability": lease["capability"],
        "executor_system": executor_system,
        "executor_receipt_ref": executor_receipt_ref,
        "authority": authority_snapshot,
        "success": bool(success),
        "executed_at": instant,
    }
    receipt["fingerprint"] = _fingerprint(receipt, omit=("fingerprint", "execution_receipt_id"))
    receipt["execution_receipt_id"] = f"EXEC-{receipt['fingerprint'][:16].upper()}"

    consumed = copy.deepcopy(lease)
    consumed["used_count"] = int(consumed["used_count"]) + 1
    consumed["state"] = "consumed" if consumed["used_count"] >= int(consumed["maximum_uses"]) else "active"
    consumed["fingerprint"] = _fingerprint(consumed, omit=("fingerprint", "lease_id"))
    consumed["lease_id"] = f"LEASE-{consumed['fingerprint'][:16].upper()}"

    record_action_receipt(
        case,
        action_id=action_id,
        receipt_ref=f"execution://{receipt['execution_receipt_id']}",
        capability_lease_id=lease["lease_id"],
        success=success,
    )
    if executor_receipt_ref not in case["event_refs"]:
        case["event_refs"].append(executor_receipt_ref)
    validate_case(case)
    return receipt, consumed
