from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Protocol

from .decision_ledger import consume_decision
from .service import LegalisError, canonical_hash, timestamp


class ValinorUnavailable(RuntimeError):
    pass


class ValinorRuntimeProtocol(Protocol):
    def syscall(self, entity_id: str, syscall_name: str) -> str: ...
    def access_secret(self, entity_id: str, secret_name: str) -> bool: ...
    def open_socket(self, entity_id: str) -> Any: ...
    def send_ipc(self, entity_id: str) -> Any: ...
    def write_stream(self, entity_id: str, target: str) -> Any: ...
    def apply_flow_shape(self, entity_id: str) -> Any: ...


def resolve_valinor_runtime(workspace_root: str | Path) -> ValinorRuntimeProtocol:
    """Resolve the mounted Sophia/Integritas Valinor runtime. No fallback kernel is created."""
    workspace = Path(workspace_root).expanduser().resolve()
    arda_root = workspace / "organs" / "sophia" / "arda_os"
    runtime_hooks = arda_root / "backend" / "valinor" / "runtime_hooks.py"
    if not runtime_hooks.is_file():
        raise ValinorUnavailable(f"Valinor runtime hooks are not available at {runtime_hooks}")
    path_text = str(arda_root)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
    try:
        from backend.valinor.runtime_hooks import get_valinor_runtime
    except Exception as exc:
        raise ValinorUnavailable(f"Valinor runtime import failed: {type(exc).__name__}: {exc}") from exc
    return get_valinor_runtime()


def authorize_valinor_boundary(
    *,
    decision_id: str | None = None,
    state_root: str | Path | None = None,
    request: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    expected_capability: str | None = None,
    expected_policy_version: str | None = None,
    decision: Mapping[str, Any] | None = None,
    entity_id: str,
    operation: str,
    target: str | None = None,
    runtime: ValinorRuntimeProtocol | None = None,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    """Ask Valinor only after loading an authenticated Legalis ledger decision.

    This does not perform the external legal/platform/business action itself.
    """
    if decision is not None or not decision_id:
        raise LegalisError("Valinor boundary requires an authenticated decision_id, not a caller decision map.")
    if state_root is None or request is None or evidence is None or not expected_capability or not expected_policy_version:
        raise LegalisError("Valinor boundary requires state_root, request, evidence, capability, and policy bindings.")
    valinor_request = request.get("valinor") if isinstance(request, Mapping) else None
    if not isinstance(valinor_request, Mapping) or (
        str(valinor_request.get("entity_id") or "") != entity_id
        or str(valinor_request.get("operation") or "") != operation
        or valinor_request.get("target") != target
    ):
        raise LegalisError("Authenticated Legalis request does not match the Valinor effect boundary.")
    authenticated = consume_decision(
        Path(state_root),
        decision_id,
        expected_request_digest=canonical_hash(request),
        expected_evidence_digest=canonical_hash(evidence),
        expected_capability=expected_capability,
        expected_policy_version=expected_policy_version,
    )
    verified_decision = authenticated["decision"]
    if verified_decision.get("verdict") != "ALLOW":
        return {
            "schema": "dio.legalis.valinor_authorization.v1",
            "decision_id": decision_id,
            "entity_id": entity_id,
            "operation": operation,
            "target": target,
            "allowed": False,
            "state": "LEGALIS_NOT_ALLOWED",
            "reason": "Valinor was not invoked because Legalis did not earn ALLOW.",
            "authorized_at": timestamp(),
            "decision_ledger_entry_sha256": authenticated["ledger_entry_sha256"],
        }
    if runtime is None:
        if workspace_root is None:
            raise ValinorUnavailable("workspace_root is required when no Valinor runtime is injected.")
        runtime = resolve_valinor_runtime(workspace_root)

    try:
        if operation == "socket":
            result = runtime.open_socket(entity_id)
        elif operation == "ipc":
            result = runtime.send_ipc(entity_id)
        elif operation == "write":
            if not target:
                raise LegalisError("Valinor write authorization requires target.")
            result = runtime.write_stream(entity_id, target)
        elif operation == "secret":
            if not target:
                raise LegalisError("Valinor secret authorization requires target.")
            result = runtime.access_secret(entity_id, target)
        elif operation == "syscall":
            if not target:
                raise LegalisError("Valinor syscall authorization requires target.")
            result = runtime.syscall(entity_id, target)
        elif operation == "flow":
            result = runtime.apply_flow_shape(entity_id)
        else:
            raise LegalisError(f"Unsupported Valinor operation: {operation}")
    except PermissionError as exc:
        return {
            "schema": "dio.legalis.valinor_authorization.v1",
            "decision_id": decision_id,
            "entity_id": entity_id,
            "operation": operation,
            "target": target,
            "allowed": False,
            "state": "VALINOR_REFUSE",
            "reason": str(exc),
            "authorized_at": timestamp(),
            "decision_ledger_entry_sha256": authenticated["ledger_entry_sha256"],
        }

    return {
        "schema": "dio.legalis.valinor_authorization.v1",
        "decision_id": decision_id,
        "entity_id": entity_id,
        "operation": operation,
        "target": target,
        "allowed": True,
        "state": "VALINOR_ALLOW",
        "result": result,
        "authorized_at": timestamp(),
        "external_action_executed": False,
        "decision_ledger_entry_sha256": authenticated["ledger_entry_sha256"],
    }
