from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from authority.canonical import (
    AuthorityPlaneError,
    record_execution_receipt,
    validate_arda_execution_identity,
    validate_capability_lease,
    validate_valinor_authorization,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "dio_vertical_executors.json"
REQUEST_SCHEMA = "dio.vertical_execution_request.v1"


class VerticalExecutorError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_vertical_executor_registry(path: Path | None = None) -> dict[str, Any]:
    payload = json.loads((path or REGISTRY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema") != "dio.vertical_executors.registry.v1":
        raise VerticalExecutorError("Unsupported vertical executor registry schema.")
    laws = payload.get("laws") or {}
    if laws.get("generic_executor") is not False:
        raise VerticalExecutorError("Generic execution must remain disabled.")
    if laws.get("automatic_external_actions") is not False:
        raise VerticalExecutorError("Automatic external actions must remain disabled.")
    if laws.get("receipt_required") is not True:
        raise VerticalExecutorError("Every vertical execution must require a receipt.")
    return payload


def _binding(registry: Mapping[str, Any], executor_id: str, capability: str) -> tuple[dict[str, Any], dict[str, Any]]:
    executor = next((row for row in registry.get("executors") or [] if row.get("executor_id") == executor_id), None)
    if executor is None:
        raise VerticalExecutorError(f"Unknown vertical executor: {executor_id}")
    cap = next((row for row in executor.get("capabilities") or [] if row.get("capability") == capability), None)
    if cap is None:
        raise VerticalExecutorError(f"Executor {executor_id} does not expose capability {capability}.")
    return dict(executor), dict(cap)


def prepare_vertical_execution(
    *,
    executor_id: str,
    capability: str,
    lease: dict[str, Any],
    valinor_authorization: dict[str, Any],
    arda_identity: dict[str, Any],
    environment_gate: bool = False,
    requested_at: str | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Fail-closed preflight for one capability-bound specialist execution.

    This function never invokes the specialist executor. It only proves that the
    Wave 4 authority chain and the Wave 5 registry binding agree exactly.
    """
    registry = load_vertical_executor_registry(registry_path)
    executor, cap = _binding(registry, executor_id, capability)

    try:
        validate_capability_lease(lease, now=requested_at)
        validate_valinor_authorization(valinor_authorization, lease=lease)
        validate_arda_execution_identity(arda_identity, now=requested_at, require_accepted=True)
    except AuthorityPlaneError as exc:
        raise VerticalExecutorError(str(exc)) from exc

    if lease.get("capability") != capability:
        raise VerticalExecutorError("Capability lease does not match requested vertical capability.")
    if not valinor_authorization.get("allowed") or valinor_authorization.get("state") != "VALINOR_ALLOW":
        raise VerticalExecutorError("Vertical execution requires Valinor ALLOW.")
    if valinor_authorization.get("operation") != cap.get("valinor_operation"):
        raise VerticalExecutorError("Valinor operation does not match the vertical capability binding.")
    if arda_identity.get("audience") != lease.get("audience"):
        raise VerticalExecutorError("ARDA audience does not match the capability lease.")

    mode = cap.get("mode")
    if mode == "hard_locked":
        raise VerticalExecutorError(f"Capability is hard locked: {executor_id}/{capability}")
    if mode not in {"local_only", "explicit_environment_gate"}:
        raise VerticalExecutorError("Unsupported vertical execution mode.")
    if cap.get("external_side_effect") is True:
        if mode != "explicit_environment_gate":
            raise VerticalExecutorError("External side effects require an explicit environment gate.")
        if environment_gate is not True:
            raise VerticalExecutorError("Explicit environment gate is not enabled for this external action.")
        if arda_identity.get("evidence_mode") not in {"observed", "enforced"}:
            raise VerticalExecutorError("External execution requires observed or enforced ARDA evidence.")
    elif mode == "explicit_environment_gate" and environment_gate is not True:
        raise VerticalExecutorError("Explicit environment gate is not enabled for this capability.")

    request: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "executor_id": executor_id,
        "system_ids": list(executor.get("system_ids") or []),
        "capability": capability,
        "mode": mode,
        "external_side_effect": bool(cap.get("external_side_effect")),
        "case_id": lease.get("case_id"),
        "action_id": lease.get("action_id"),
        "action_digest": lease.get("action_digest"),
        "lease_id": lease.get("lease_id"),
        "lease_fingerprint": lease.get("fingerprint"),
        "valinor_authorization_id": valinor_authorization.get("authorization_id"),
        "arda_execution_identity_id": arda_identity.get("execution_identity_id"),
        "valinor_operation": cap.get("valinor_operation"),
        "receipt_prefix": cap.get("receipt_prefix"),
        "requested_at": requested_at,
    }
    request["fingerprint"] = _fingerprint(request)
    request["vertical_request_id"] = f"VEXEC-{request['fingerprint'][:16].upper()}"
    return request


def execute_vertical_capability(
    case: dict[str, Any],
    *,
    executor_id: str,
    capability: str,
    lease: dict[str, Any],
    valinor_authorization: dict[str, Any],
    arda_identity: dict[str, Any],
    specialist_executor: Callable[[dict[str, Any]], Mapping[str, Any]],
    environment_gate: bool = False,
    executed_at: str | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Execute exactly one pre-authorized specialist capability and close it with a Wave 4 receipt."""
    request = prepare_vertical_execution(
        executor_id=executor_id,
        capability=capability,
        lease=lease,
        valinor_authorization=valinor_authorization,
        arda_identity=arda_identity,
        environment_gate=environment_gate,
        requested_at=executed_at,
        registry_path=registry_path,
    )

    result = specialist_executor(dict(request))
    if not isinstance(result, Mapping):
        raise VerticalExecutorError("Specialist executor must return a receipt mapping.")
    receipt_ref = str(result.get("receipt_ref") or "")
    success = result.get("success")
    if not isinstance(success, bool):
        raise VerticalExecutorError("Specialist receipt must contain boolean success.")
    prefix = str(request.get("receipt_prefix") or "")
    if not receipt_ref or not prefix or not receipt_ref.startswith(prefix):
        raise VerticalExecutorError("Specialist receipt reference does not match the registered executor prefix.")

    try:
        execution_receipt, consumed_lease = record_execution_receipt(
            case,
            action_id=str(lease["action_id"]),
            lease=lease,
            valinor_authorization=valinor_authorization,
            arda_identity=arda_identity,
            executor_system=executor_id,
            executor_receipt_ref=receipt_ref,
            success=success,
            executed_at=executed_at,
        )
    except AuthorityPlaneError as exc:
        raise VerticalExecutorError(str(exc)) from exc

    return {
        "request": request,
        "specialist_receipt": dict(result),
        "execution_receipt": execution_receipt,
        "consumed_lease": consumed_lease,
    }
