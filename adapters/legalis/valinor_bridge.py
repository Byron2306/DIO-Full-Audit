from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Protocol

from .service import LEGALIS_DECISION_SCHEMA, LegalisError, timestamp


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
    decision: Mapping[str, Any],
    entity_id: str,
    operation: str,
    target: str | None = None,
    runtime: ValinorRuntimeProtocol | None = None,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    """Ask Valinor to authorize the runtime boundary only after Legalis earned ALLOW.

    This does not perform the external legal/platform/business action itself.
    """
    if decision.get("schema") != LEGALIS_DECISION_SCHEMA:
        raise LegalisError("Valinor boundary requires a Legalis decision receipt.")
    if decision.get("verdict") != "ALLOW":
        return {
            "schema": "dio.legalis.valinor_authorization.v1",
            "decision_id": decision.get("decision_id"),
            "entity_id": entity_id,
            "operation": operation,
            "target": target,
            "allowed": False,
            "state": "LEGALIS_NOT_ALLOWED",
            "reason": "Valinor was not invoked because Legalis did not earn ALLOW.",
            "authorized_at": timestamp(),
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
            "decision_id": decision.get("decision_id"),
            "entity_id": entity_id,
            "operation": operation,
            "target": target,
            "allowed": False,
            "state": "VALINOR_REFUSE",
            "reason": str(exc),
            "authorized_at": timestamp(),
        }

    return {
        "schema": "dio.legalis.valinor_authorization.v1",
        "decision_id": decision.get("decision_id"),
        "entity_id": entity_id,
        "operation": operation,
        "target": target,
        "allowed": True,
        "state": "VALINOR_ALLOW",
        "result": result,
        "authorized_at": timestamp(),
        "external_action_executed": False,
    }
