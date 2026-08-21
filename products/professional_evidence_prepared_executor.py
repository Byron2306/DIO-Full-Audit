from __future__ import annotations

import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from products.professional_evidence_final_compat import install_final_gauntlet_compat

install_final_gauntlet_compat()

from products.professional_evidence_red13_compat import install_red13_compat

install_red13_compat()

from products.professional_evidence_final3_compat import install_final3_compat

install_final3_compat()

from products.professional_evidence_sophia_boundary_probe import install_sophia_boundary_probe

install_sophia_boundary_probe()

from products.professional_evidence_customer_surface_compat import install_customer_surface_compat

# Legacy compatibility remains installed for routes that still require it, but
# mature canonical products are dispatched through explicit native-route laws
# before the generic/compat route. Native routing may not silently fall back to
# a weaker implementation.
install_customer_surface_compat()

from products.professional_evidence_executor import (
    BLOCKED,
    FAIL,
    OUTER_RECEIPT,
    PASS,
    _artifact_inventory,
    _blind_review,
    _load_routes,
    _route_execute,
    _trace_customer_records,
)
from products.professional_evidence_native_rich_routes import (
    RICH_NATIVE_NOT_HANDLED,
    execute_rich_native_route,
)
from products.professional_evidence_native_routes import (
    NATIVE_ENGINE_ROUTES,
    NATIVE_ROUTE_NOT_HANDLED,
    execute_native_route,
)
from products.professional_evidence_projection import binding_receipt, load_packet, write_json


SCHEMA = "dio.professional_evidence.prepared_packet_execution.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def execute_prepared_customer_case(
    incarnation: str,
    case_root: Path,
    *,
    operator_id: str = "professional-evidence-harness",
    now: str | None = None,
    online: bool = False,
    prepared_by: str = "vesper_web_chat",
) -> dict[str, Any]:
    """Execute an already-materialised literal customer packet in place.

    Vesper owns source capture and byte custody. Mature native engines may receive
    a typed projection of those bytes, but the prepared executor refuses silent
    replacement by a weaker surrogate implementation.
    """
    now = now or utc_now()
    route = (_load_routes().get("routes") or {}).get(incarnation)
    if not isinstance(route, dict):
        raise ValueError(f"No Professional Evidence route for {incarnation}")

    case_root = case_root.resolve()
    packet_dir = case_root / "CUSTOMER_PACKET"
    examiner_dir = case_root / "EXAMINER"
    if not packet_dir.is_dir():
        raise FileNotFoundError(f"Prepared customer packet missing: {packet_dir}")
    if not examiner_dir.is_dir():
        raise FileNotFoundError(f"Blind examiner directory missing: {examiner_dir}")
    if prepared_by != "vesper_web_chat":
        raise ValueError("Prepared professional execution currently requires prepared_by=vesper_web_chat")

    packet = load_packet(packet_dir)
    projection_dir = case_root / "PROJECTION"
    execution_dir = case_root / "EXECUTION"
    for directory in (projection_dir, execution_dir):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=False)

    binding = binding_receipt(packet, incarnation, route)
    binding["prepared_packet_execution"] = True
    binding["prepared_by"] = prepared_by
    binding["rematerialized_by_executor"] = False
    write_json(projection_dir / "CUSTOMER_PACKET_BINDING.json", binding)
    trace = _trace_customer_records(packet, projection_dir / "CUSTOMER_FACT_TRACE.json")

    route_name = str(route.get("route") or "")
    native_required = route_name in NATIVE_ENGINE_ROUTES

    status = FAIL
    result: dict[str, Any] = {}
    error = ""
    try:
        rich_result = execute_rich_native_route(
            packet,
            execution_dir,
            incarnation=incarnation,
            route=route,
            operator_id=operator_id,
            now=now,
        )
        if rich_result is RICH_NATIVE_NOT_HANDLED:
            native_result = execute_native_route(
                packet,
                execution_dir,
                incarnation=incarnation,
                route=route,
                operator_id=operator_id,
                now=now,
                online=online,
                generic_executor=_route_execute,
            )
        else:
            native_result = rich_result

        if native_result is NATIVE_ROUTE_NOT_HANDLED:
            if native_required:
                raise RuntimeError(
                    f"{incarnation} requires native engine {NATIVE_ENGINE_ROUTES[route_name]} but native dispatch did not handle it"
                )
            result = _route_execute(
                packet,
                execution_dir,
                incarnation=incarnation,
                route=route,
                operator_id=operator_id,
                now=now,
                online=online,
            )
        else:
            result = dict(native_result)

        if native_required:
            expected_engine = NATIVE_ENGINE_ROUTES[route_name]
            observed_engine = str(result.get("native_engine_identity") or result.get("executor") or "")
            if expected_engine not in observed_engine:
                raise RuntimeError(
                    f"{incarnation} native routing identity mismatch: expected {expected_engine}, observed {observed_engine or '<none>'}"
                )
            if result.get("surrogate_fallback_used") is True:
                raise RuntimeError(f"{incarnation} illegally used a surrogate fallback")

        blind = _blind_review(case_root, result, trace)
        if not blind["passed"]:
            raise RuntimeError("blind professional evidence review failed")
        status = PASS
    except NotImplementedError as exc:
        status = BLOCKED
        error = str(exc)
    except Exception as exc:
        status = FAIL
        error = f"{type(exc).__name__}: {exc}"
        (case_root / "EXECUTION_ERROR.txt").write_text(error + "\n\n" + traceback.format_exc(), encoding="utf-8")

    receipt = {
        "schema": "dio.professional_evidence.case_receipt.v3",
        "prepared_execution_schema": SCHEMA,
        "incarnation": incarnation,
        "status": status,
        "route": route,
        "packet_fingerprint": packet["packet_fingerprint"],
        "binding_fingerprint": binding["binding_fingerprint"],
        "executed_at": now,
        "executor": result.get("executor"),
        "product_id": result.get("product_id"),
        "terminal_artifact_kind": result.get("terminal_artifact_kind"),
        "product_pipeline_executed": result.get("product_pipeline_executed") is True,
        "domain_action_executed": result.get("domain_action_executed") is True,
        "native_engine_required": native_required,
        "native_engine_expected": NATIVE_ENGINE_ROUTES.get(route_name),
        "native_engine_identity": result.get("native_engine_identity"),
        "native_capability_preserved": result.get("native_capability_preserved") is True if native_required else None,
        "surrogate_fallback_allowed": False if native_required else None,
        "surrogate_fallback_used": result.get("surrogate_fallback_used") is True if native_required else None,
        "prepared_by": prepared_by,
        "rematerialized_by_executor": False,
        "examiner_data_used_during_execution": False,
        "golden_fixture_used": False,
        "customer_packet_only": True,
        "human_review_required": True,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "market_validation_claimed": False,
        "authority_created": False,
        "external_effects": False,
        "error": error,
        "artifacts": _artifact_inventory(case_root),
    }
    write_json(case_root / OUTER_RECEIPT, receipt)
    return receipt


__all__ = ["SCHEMA", "execute_prepared_customer_case"]
