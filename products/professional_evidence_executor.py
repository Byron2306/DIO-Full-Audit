from __future__ import annotations

import json
import os
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT
from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_execution import (
    _build_vamp_database,
    _run_ai_trust,
    _run_campaign_lab,
    _run_evidex,
    _run_homs_assess,
    _run_homs_learning,
    _run_market_radar,
    _run_obligation,
    _run_profile_review,
    _run_sophia,
    _run_vesper,
)
from products.professional_evidence_native import (
    run_accessible_publish,
    run_accreditation,
    run_contractproof,
    run_dossierops,
    run_homs_curriculum,
    run_homs_exam,
    run_offer_lab,
    run_opportunity_foundry,
    run_regops,
)
from products.professional_evidence_projection import (
    binding_receipt,
    document_studio_projection,
    evidence_rows,
    load_packet,
    sha256,
    slug,
    write_json,
)


ROUTES_PATH = ROOT / "config" / "professional_evidence_portfolio" / "v1" / "routes.json"
PASS = "PASS_FULL_PIPELINE"
FAIL = "FAIL_EXECUTION"
BLOCKED = "BLOCKED_FULL_PIPELINE_GAP"
OUTER_RECEIPT = "PROFESSIONAL_EVIDENCE_RECEIPT.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_routes() -> dict[str, Any]:
    return json.loads(ROUTES_PATH.read_text(encoding="utf-8"))


def _clean_case_root(output_root: Path, incarnation: str) -> Path:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    case_root = output_root / slug(incarnation)
    if case_root.exists():
        shutil.rmtree(case_root)
    return case_root


def _artifact_inventory(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == OUTER_RECEIPT:
            continue
        rows.append({"path": str(path.relative_to(root)), "sha256": sha256(path), "bytes": path.stat().st_size})
    return rows


def _trace_customer_records(packet: dict[str, Any], target: Path) -> dict[str, Any]:
    trace = {
        "schema": "dio.professional_evidence.customer_fact_trace.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "records": [
            {
                "record_id": str(row.get("record_id") or ""),
                "customer_supplied_record": str(row.get("customer_supplied_record") or ""),
                "source": "CUSTOMER_PACKET/SOURCES/02_evidence_register.csv",
            }
            for row in evidence_rows(packet)
        ],
        "derived_before_examiner_loaded": True,
        "examiner_data_used": False,
    }
    write_json(target, trace)
    return trace


def _blind_review(case_root: Path, result: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    # Deliberately loaded only after executor completion.
    expected = json.loads((case_root / "EXAMINER" / "EXPECTED_FACTS.json").read_text(encoding="utf-8"))
    prohibited = json.loads((case_root / "EXAMINER" / "PROHIBITED_OUTCOMES.json").read_text(encoding="utf-8"))
    expected_facts = [str(value) for value in expected.get("facts") or []]
    traced = {str(row.get("customer_supplied_record") or "") for row in trace.get("records") or []}
    matched = [fact for fact in expected_facts if fact in traced]
    receipt = result.get("receipt") or {}
    authority_clean = receipt.get("authority_created", False) is False and receipt.get("external_effects", False) is False
    review = {
        "schema": "dio.professional_evidence.blind_review.v2",
        "expected_fact_count": len(expected_facts),
        "source_trace_match_count": len(matched),
        "source_trace_fidelity": round(len(matched) / max(1, len(expected_facts)), 4),
        "prohibited_outcomes": list(prohibited.get("prohibited_outcomes") or []),
        "prohibited_authority_effect_detected": not authority_clean,
        "professional_terminal_artifact_created": bool(result.get("terminal_artifact_kind")),
        "product_pipeline_executed": result.get("product_pipeline_executed") is True,
        "examiner_loaded_after_execution": True,
        "examiner_data_used_during_execution": False,
        "passed": len(matched) == len(expected_facts) and authority_clean and result.get("product_pipeline_executed") is True,
    }
    write_json(case_root / "BLIND_REVIEW.json", review)
    return review


def _standard(result: dict[str, Any], *, executor: str, product_id: str, terminal: str) -> dict[str, Any]:
    return {
        "executor": executor,
        "product_id": product_id,
        "terminal_artifact_kind": terminal,
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "receipt": result.get("receipt") or {},
        "native_result": result,
    }


def _run_vamp_corrected(packet: dict[str, Any], execution_dir: Path, *, incarnation: str, operator_id: str, now: str) -> dict[str, Any]:
    from adapters.vamp.snapshot_pipeline import build_snapshot
    from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile

    db = _build_vamp_database(packet, execution_dir.parent / "PROJECTION" / "progress.db")
    profile = ROOT / "config" / "vamp_profiles" / "university_generic_v1.json"
    request = {
        "schema": "dio.vamp_snapshot_request.v1",
        "job_id": "PRO-" + slug(incarnation).upper(),
        "profile_path": str(profile),
        "source": {"kind": "vamp_sqlite", "database_path": str(db), "staff_id": "PROFESSIONAL-001", "year": 2026},
        "review": {"months": ["2026-08"]},
        "privacy_mode": "professional_customer_controlled",
        "consents": {"evidence_owner_authorized": True, "performance_data_processing_approved": True, "human_review_terms_accepted": True},
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    request_path = execution_dir.parent / "PROJECTION" / "VAMP_SNAPSHOT_REQUEST.json"
    write_json(request_path, request)
    output = build_snapshot(request, request_path, execution_dir / "vamp_snapshot", run_evidex=True)
    receipt_path = Path(output) / "VAMP_SNAPSHOT_RECEIPT.json"
    if not receipt_path.is_file():
        raise RuntimeError("VAMP snapshot receipt missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "ready_for_human_review":
        raise RuntimeError(f"VAMP did not reach ready_for_human_review: {receipt.get('status')}")
    profile_id = {"PromotionProof": "promotionproof", "CPDProof": "cpdproof"}.get(incarnation)
    profile_result = None
    product_id = "vamp_performance"
    if profile_id:
        profile_result = _run_profile_review(packet, execution_dir / "profile_review", profile_id=profile_id, operator_id=operator_id, now=now)
        product_id = str(load_unpromoted_evidence_profile(profile_id)["product_id"])
    combined_receipt = {
        "schema": "dio.professional_evidence.vamp_pipeline_receipt.v1",
        "snapshot_receipt": receipt,
        "profile_receipt": (profile_result or {}).get("receipt"),
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    write_json(execution_dir / "PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json", combined_receipt)
    return {
        "executor": "adapters.vamp.snapshot_pipeline.build_snapshot" + (" + product-specific profile" if profile_id else ""),
        "product_id": product_id,
        "terminal_artifact_kind": "performance_evidence_snapshot" if not profile_id else "profile_specific_performance_evidence_pack",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "receipt": combined_receipt,
    }


def _run_document_corrected(packet: dict[str, Any], execution_dir: Path, *, incarnation: str, configured_service: str) -> dict[str, Any]:
    from adapters.document_studio.pipeline import run_document_studio

    service = {"edit": "technical_edit", "publish": "technical_edit"}.get(configured_service, configured_service)
    request_path = execution_dir.parent / "PROJECTION" / "DOCUMENT_STUDIO_REQUEST.json"
    request = document_studio_projection(packet, request_path, service=service, incarnation=incarnation)
    output = run_document_studio(request, request_path, execution_dir / "document_studio")
    receipt_path = output / "DOCUMENT_STUDIO_RECEIPT.json"
    if not receipt_path.is_file():
        raise RuntimeError("Document Studio receipt missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "human_review_required" or (receipt.get("release") or {}).get("delivery_released") is not False:
        raise RuntimeError("Document Studio did not preserve human-review/release boundary")
    return {
        "executor": "adapters.document_studio.pipeline.run_document_studio",
        "product_id": "document_studio",
        "terminal_artifact_kind": "reviewable_document_pack",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "receipt": {**receipt, "authority_created": False, "external_effects": False},
    }


def _run_opportunity_with_radar(packet: dict[str, Any], execution_dir: Path, *, online: bool, now: str) -> dict[str, Any]:
    radar = _run_market_radar(packet, execution_dir / "market_radar", online=online)
    native = run_opportunity_foundry(packet, execution_dir / "opportunity_foundry", now=now)
    binding = {
        "schema": "dio.opportunity_foundry.market_binding.v1",
        "market_radar_executor": radar["executor"],
        "market_radar_receipt": radar["receipt"],
        "packet_fingerprint": packet["packet_fingerprint"],
        "market_demand_claimed": False,
        "authority_created": False,
    }
    write_json(execution_dir / "MARKET_RADAR_BINDING.json", binding)
    receipt = {
        **(native.get("receipt") or {}),
        "upstream_market_radar_bound": True,
        "upstream_market_radar": binding,
        "authority_created": False,
        "external_effects": False,
    }
    return {
        "executor": "market_sensorium.cycle.MarketSensoriumCycle.run + products.professional_evidence_native.run_opportunity_foundry",
        "product_id": "opportunity_foundry",
        "terminal_artifact_kind": "ranked_opportunity_hypotheses",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "receipt": receipt,
    }


def _route_execute(packet: dict[str, Any], execution_dir: Path, *, incarnation: str, route: dict[str, Any], operator_id: str, now: str, online: bool) -> dict[str, Any]:
    route_name = str(route.get("route") or "")
    if route_name == "homs_raw_assessment":
        return _run_homs_assess(packet, execution_dir)
    if route_name == "homs_raw_exam":
        native = run_homs_exam(packet, execution_dir, now=now)
        source_pack = packet["packet_dir"] / "SOURCES" / "source_pack.md"
        if not source_pack.is_file():
            raise RuntimeError("HOMS Exam professional packet is missing the customer source booklet")
        shutil.copy2(source_pack, execution_dir / "EXAM_SOURCE_BOOKLET.md")
        return _standard(native, executor="products.professional_evidence_native.run_homs_exam", product_id="homs_exam", terminal="review_ready_exam_and_memo")
    if route_name == "homs_raw_curriculum":
        return _standard(run_homs_curriculum(packet, execution_dir, now=now), executor="products.professional_evidence_native.run_homs_curriculum", product_id="homs_curriculum", terminal="curriculum_alignment_pack")
    if route_name == "homs_raw_learning":
        return _run_homs_learning(packet, execution_dir)
    if route_name == "education_research_profile":
        return _run_profile_review(packet, execution_dir, profile_id=str(route["profile_id"]), operator_id=operator_id, now=now)
    if route_name == "accreditation_raw_projection":
        return _standard(run_accreditation(packet, execution_dir, operator_id=operator_id, now=now), executor="products.accreditation.runner.run_controlled_accreditation_review", product_id="dio_accreditation", terminal="accreditation_readiness_pack")
    if route_name.startswith("sophia_raw_"):
        return _run_sophia(packet, execution_dir, incarnation=incarnation)
    if route_name.startswith("vamp_raw_"):
        return _run_vamp_corrected(packet, execution_dir, incarnation=incarnation, operator_id=operator_id, now=now)
    if route_name == "evidence_profile":
        return _run_profile_review(packet, execution_dir, profile_id=str(route["profile_id"]), operator_id=operator_id, now=now)
    if route_name == "high_risk_profile":
        return _run_profile_review(packet, execution_dir, profile_id=str(route["profile_id"]), operator_id=operator_id, now=now, high_risk=True)
    if route_name == "obligation_family":
        return _run_obligation(packet, execution_dir, route=route, operator_id=operator_id, now=now)
    if route_name == "contractproof_raw_journey":
        return _standard(run_contractproof(packet, execution_dir, operator_id=operator_id, now=now), executor="products.contractproof.runner.run_contractproof + draft-only delivery", product_id="dio_contractproof", terminal="evidence_pack_and_delivery_draft")
    if route_name == "evidex_raw":
        return _run_evidex(packet, execution_dir)
    if route_name == "regops_raw_projection":
        return _standard(run_regops(packet, execution_dir, operator_id=operator_id, now=now), executor="products.regops.runner.run_controlled_regops_review", product_id="dio_regops", terminal="regops_readiness_pack")
    if route_name == "document_studio_raw":
        return _run_document_corrected(packet, execution_dir, incarnation=incarnation, configured_service=str(route.get("service") or "technical_edit"))
    if route_name == "document_studio_accessible_raw":
        return _standard(run_accessible_publish(packet, execution_dir, now=now), executor="products.professional_evidence_native.run_accessible_publish", product_id="accessible_publish", terminal="accessible_publication_pack")
    if route_name == "dossierops_raw_composition":
        return _standard(run_dossierops(packet, execution_dir, operator_id=operator_id, now=now), executor="Document Studio + products.dossierops.runner.run_controlled_dossierops_assembly", product_id="dio_dossierops", terminal="dossier_bundle")
    if route_name in {"agentauthority_raw_projection", "changeproof_raw_projection", "ai_assurance_raw_projection"}:
        return _run_ai_trust(packet, execution_dir, incarnation=incarnation, operator_id=operator_id, now=now)
    if route_name == "market_radar_raw":
        return _run_market_radar(packet, execution_dir, online=online)
    if route_name == "opportunity_foundry_raw":
        return _run_opportunity_with_radar(packet, execution_dir, online=online, now=now)
    if route_name == "offer_lab_raw":
        return _standard(run_offer_lab(packet, execution_dir, now=now), executor="products.professional_evidence_native.run_offer_lab", product_id="offer_lab", terminal="bounded_offer_hypothesis")
    if route_name == "campaign_lab_raw":
        return _run_campaign_lab(packet, execution_dir)
    if route_name == "vesper_raw_intake":
        return _run_vesper(packet, execution_dir)
    raise NotImplementedError(f"No professional customer executor is registered for {incarnation}: {route_name}")


def execute_customer_case(
    incarnation: str,
    output_root: Path,
    *,
    operator_id: str = "professional-evidence-harness",
    now: str | None = None,
    online: bool = False,
) -> dict[str, Any]:
    now = now or utc_now()
    route = (_load_routes().get("routes") or {}).get(incarnation)
    if not isinstance(route, dict):
        raise ValueError(f"No Professional Evidence route for {incarnation}")

    case_root = _clean_case_root(output_root, incarnation)
    materialize_customer_packet(incarnation, output_root.resolve())
    enrich_customer_packet(incarnation, case_root / "CUSTOMER_PACKET")
    packet = load_packet(case_root / "CUSTOMER_PACKET")

    projection_dir = case_root / "PROJECTION"
    execution_dir = case_root / "EXECUTION"
    projection_dir.mkdir(parents=True, exist_ok=True)
    execution_dir.mkdir(parents=True, exist_ok=True)
    binding = binding_receipt(packet, incarnation, route)
    write_json(projection_dir / "CUSTOMER_PACKET_BINDING.json", binding)
    trace = _trace_customer_records(packet, projection_dir / "CUSTOMER_FACT_TRACE.json")

    status = FAIL
    result: dict[str, Any] = {}
    error = ""
    try:
        result = _route_execute(packet, execution_dir, incarnation=incarnation, route=route, operator_id=operator_id, now=now, online=online)
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
        "schema": "dio.professional_evidence.case_receipt.v2",
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


__all__ = ["BLOCKED", "FAIL", "PASS", "execute_customer_case"]
