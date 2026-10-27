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


def _verify_provider_artifacts(result: dict[str, Any], execution_dir: Path) -> dict[str, str]:
    """Verify the provider's existing commitments before discovering derivatives.

    Rehashing whatever survived a route is not verification of that route's
    declared outputs. A returned proof fingerprint also binds its on-disk
    artifact inventory, including required machine-readable domain output.
    """
    import hashlib
    import json
    from products.professional_evidence_projection import sha256

    verified: dict[str, str] = {}
    receipt = result.get("receipt") or {}
    containers: list[Any] = [receipt]
    expected_proof = receipt.get("proof_fingerprint")
    if expected_proof:
        matched = False
        for path in execution_dir.rglob("*MANIFEST*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("proof_fingerprint") != expected_proof:
                continue
            core = {k: v for k, v in value.items() if k != "proof_fingerprint"}
            digest = "sha256:" + hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            if digest != expected_proof:
                raise ValueError("native artifact proof manifest hash mismatch")
            containers.append(value)
            matched = True
        if not matched:
            raise ValueError("native artifact proof manifest is missing")

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, dict):
            raw_path = value.get("path") or value.get("filename") or value.get("file_name") or value.get("raw_path")
            digest = str(value.get("sha256") or "").removeprefix("sha256:")
            if raw_path and len(digest) == 64 and "://" not in str(raw_path):
                path = Path(str(raw_path))
                if not path.is_absolute():
                    direct = execution_dir / path
                    candidates = [direct] if direct.is_file() else list(execution_dir.rglob(path.name)) if path.parent == Path(".") else []
                    # Some native receipts deliberately retain an explicit path
                    # relative to the repository, not the execution directory.
                    if not candidates and path.is_file():
                        candidates = [path]
                else:
                    candidates = [path]
                if not candidates or not any(p.is_file() for p in candidates):
                    raise ValueError(f"native artifact is missing: {raw_path}")
                matches = [p.resolve() for p in candidates if p.is_file() and sha256(p) == digest]
                if not matches:
                    raise ValueError(f"native artifact hash mismatch: {raw_path}")
                for path in matches:
                    verified[str(path)] = digest
            for child in value.values():
                if isinstance(child, (list, dict)):
                    visit(child)

    for value in containers:
        visit(value)
    return verified


def _finish_native_artifacts(packet: dict[str, Any], execution_dir: Path, incarnation: str, result: dict[str, Any]) -> dict[str, Any]:
    from presence_core.shared_production_finish import render_held_artifacts_for_review
    from products.professional_evidence_projection import sha256

    verified = _verify_provider_artifacts(result, execution_dir)
    # Prefer the editable/semantic rendition of the same native document while
    # retaining distinct source documents. Internal JSON receipts are not prose.
    priority = {".html": 0, ".htm": 0, ".docx": 1, ".md": 2, ".txt": 3, ".pdf": 4, ".csv": 5, ".pptx": 6}
    selected: dict[str, Path] = {}
    for path in sorted(execution_dir.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in priority:
            continue
        key = str(path.relative_to(execution_dir).with_suffix("")).casefold()
        previous = selected.get(key)
        if previous is None or priority[path.suffix.casefold()] < priority[previous.suffix.casefold()]:
            selected[key] = path
    sources = [
        {"artifact_id": f"NATIVE-{index:04d}", "kind": "native_customer_deliverable", "path": str(path), "file_name": str(path.relative_to(execution_dir)), "sha256": verified.get(str(path.resolve())) or sha256(path), "binding_state": "PROVIDER_DECLARED_HASH_VERIFIED" if str(path.resolve()) in verified else "POST_ROUTE_DISCOVERED_DERIVATIVE", "release_state": "HELD"}
        for index, path in enumerate(selected.values(), 1)
    ]
    return render_held_artifacts_for_review(
        state_root=execution_dir / "SHARED_PRODUCTION_FINISH", case_id=str(packet.get("case_id") or incarnation),
        source_sha256=str(packet["packet_fingerprint"]).removeprefix("sha256:"), product_name=incarnation, artifacts=sources,
    )


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
        result["shared_production_finish"] = _finish_native_artifacts(packet, execution_dir, incarnation, result)
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
        "shared_production_finish": result.get("shared_production_finish"),
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
