from __future__ import annotations

import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from products.professional_evidence_final_compat import install_final_gauntlet_compat

# The Vesper prepared executor binds route helpers by value below. Install the
# narrow final-gauntlet compatibility repairs first so those bindings resolve to
# the current product contracts without weakening custody, examiner or release
# boundaries.
install_final_gauntlet_compat()

from products.professional_evidence_red13_compat import install_red13_compat

# The first 13-product kill-list run exposed five second-order seams after the
# initial compatibility layer. Install those repairs before _route_execute is
# imported by value here. They preserve the same Vesper byte custody, blind
# examiner and external-release constitution.
install_red13_compat()

from products.professional_evidence_final3_compat import install_final3_compat

# The remaining root-five run reduced the portfolio to three true seams:
# Sophia's constitutional refusal vocabulary, the missing shared epistemic
# spine module, and Campaign Lab cross-surface semantic distance. The shared
# spine is restored in scripts/dio_epistemic_spine.py; install the two narrow
# execution patches before _route_execute is bound below.
install_final3_compat()

from products.professional_evidence_sophia_boundary_probe import install_sophia_boundary_probe

# Sophia Tutor is the sole remaining failure. Instrument its final learner-visible
# authorship check without altering the pass predicate so one focused rerun exposes
# the exact response and missing signal instead of producing another opaque refusal.
install_sophia_boundary_probe()

from products.professional_evidence_customer_surface_compat import install_customer_surface_compat

# Alpha customer-surface review exposed last-mile composition defects rather than
# new domain-engine gaps: separate Sophia references were not bound into the local
# audit, VAMP used a synthetic KPA outside its own profile vocabulary, HOMS Exam
# stopped at Markdown, Evidex retained template metadata, and Campaign Lab reused a
# single visual source. Install these composition repairs last so they wrap the
# already-corrected governed product routes rather than replacing them.
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

    This function deliberately does not call materialize_customer_packet or
    enrich_customer_packet. The caller owns source capture. In the production
    gauntlet that caller is Vesper Web Chat, which quarantines and rehydrates
    the exact source bytes before this executor is allowed to run.
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

    status = FAIL
    result: dict[str, Any] = {}
    error = ""
    try:
        result = _route_execute(
            packet,
            execution_dir,
            incarnation=incarnation,
            route=route,
            operator_id=operator_id,
            now=now,
            online=online,
        )
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