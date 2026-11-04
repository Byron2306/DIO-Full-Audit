"""Customer-source DIO AI Assurance composition review with untrusted evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.ai_assurance_execution_proof import COMPONENT_PRODUCT_ID, REVIEW_PROFILE
from products.ai_trust.runner import run_ai_trust
from products.evidence_profile_execution_proof import _verify_result
from products.evidence_review import run_controlled_evidence_review
from products.governed_case import new_case
from products.professional_evidence_projection import write_json


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_source(packet: dict[str, Any], source_ref: str) -> Path:
    relative = Path(source_ref)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"unsafe DIO AI Assurance source_ref: {source_ref}")
    declared = {str(row.get("path")): row for row in packet["manifest"].get("files") or []}
    key = (Path("SOURCES") / relative).as_posix()
    row = declared.get(key)
    path = (packet["packet_dir"] / key).resolve()
    if row is None or not path.is_relative_to(packet["packet_dir"].resolve()) or not path.is_file():
        raise ValueError(f"DIO AI Assurance source is absent from the packet manifest: {source_ref}")
    if _sha(path) != str(row.get("sha256") or ""):
        raise ValueError(f"DIO AI Assurance source hash mismatch: {source_ref}")
    return path


def run_customer_ai_assurance(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    payload_path = packet["packet_dir"] / "SOURCES" / "ai_assurance_payload.json"
    if not payload_path.is_file() or "SOURCES/ai_assurance_payload.json" not in {
        str(row.get("path")) for row in packet["manifest"].get("files") or []
    }:
        raise ValueError("DIO AI Assurance requires manifest-bound SOURCES/ai_assurance_payload.json")
    request = json.loads(payload_path.read_text(encoding="utf-8"))
    payload = request.get("ai_trust_payload")
    if not isinstance(payload, dict) or payload.get("source_type") != "ai_system":
        raise ValueError("ai_trust_payload must describe an ai_system")
    telemetry_source_binding = None
    telemetry_source_path = packet["packet_dir"] / "SOURCES" / "seraph_telemetry.json"
    declared_paths = {str(row.get("path")) for row in packet["manifest"].get("files") or []}
    if telemetry_source_path.is_file() and "SOURCES/seraph_telemetry.json" in declared_paths:
        if payload.get("seraph_telemetry") is not None:
            raise ValueError("Seraph telemetry must be supplied in one manifest-bound location only")
        # Re-verify this file at the point of use, just like the AI source files.
        telemetry_source_path = _safe_source(packet, "seraph_telemetry.json")
        telemetry_document = json.loads(telemetry_source_path.read_text(encoding="utf-8"))
        telemetry = telemetry_document.get("seraph_telemetry")
        if not isinstance(telemetry, dict):
            raise ValueError("manifest-bound seraph_telemetry.json must contain a seraph_telemetry object")
        payload["seraph_telemetry"] = telemetry
        telemetry_source_binding = {
            "source_ref": "SOURCES/seraph_telemetry.json",
            "source_sha256": _sha(telemetry_source_path),
            "declared_case_id": str(telemetry_document.get("case_id") or ""),
            "payload_case_id": str(payload.get("case_id") or ""),
            "case_binding_state": (
                "MATCH" if str(telemetry_document.get("case_id") or "") == str(payload.get("case_id") or "")
                else "DECLARED_CASE_ID_MISSING" if not str(telemetry_document.get("case_id") or "")
                else "DECLARED_CASE_ID_MISMATCH"
            ),
        }
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("at least one file-backed AI system source is required")
    source_files: list[tuple[dict[str, Any], Path]] = []
    seen: set[str] = set()
    for item in sources:
        source_ref = str(item.get("source_ref") or "")
        path = _safe_source(packet, source_ref)
        digest = _sha(path)
        if digest != str(item.get("sha256") or "").removeprefix("sha256:"):
            raise ValueError(f"AI Trust source digest does not match supplied bytes: {source_ref}")
        if source_ref in seen:
            raise ValueError(f"duplicate AI Trust source_ref: {source_ref}")
        seen.add(source_ref)
        source_files.append((item, path))

    output_dir.mkdir(parents=True, exist_ok=True)
    component_dir = output_dir / "component_aitrustproof"
    component = run_ai_trust(COMPONENT_PRODUCT_ID, payload, output_dir=component_dir, operator_id=operator_id, now=now)
    component_receipt = component.get("receipt") or {}
    if (component_receipt.get("human_gate") != "NEEDS_YOU"
            or component_receipt.get("external_release_gate") != "REFUSE"
            or component_receipt.get("authority_created") is not False
            or component_receipt.get("external_effects") is not False):
        raise RuntimeError("AITrustProof component crossed its human/release boundary")

    seraph = component.get("seraph_challenge") or {}
    if seraph.get("coverage_state") != "partial" or seraph.get("verdict") == "CLEAR" or seraph.get("execution_authorized") is not False:
        raise RuntimeError("Seraph challenge boundary drifted")
    telemetry_review = ((seraph.get("evidence_context") or {}).get("seraph_telemetry") or {
        "state": "NOT_REQUESTED", "required": False, "event_count": 0, "audit_count": 0,
        "signature_state": "NOT_ASSESSED", "source_identity_state": "NOT_ASSESSED",
        "claim_boundary": "No telemetry was requested for this case.",
    })
    telemetry_path = component_dir / "SERAPH_CHALLENGE_RECEIPT.json"
    if not telemetry_path.is_file():
        raise RuntimeError("AITrustProof component did not persist its Seraph challenge receipt")

    case = new_case(
        product="dio_assurance",
        job_id="customer-dio-ai-assurance",
        source={"source": {"packet_payload": "SOURCES/ai_assurance_payload.json", "component_product_id": COMPONENT_PRODUCT_ID}, "evidence": []},
        source_path=payload_path,
        evidence_inputs=["customer-supplied AI system source files", "AITrustProof review dossier", "component proof manifest"],
        expected_outputs=["control evidence review matrix", "gaps and exceptions", "assurance review pack"],
        required_authorities=["system_owner", "control_owner", "assurance_reviewer", "release_operator"],
        intake_state="approved",
        now=now,
    )
    requirements = [
        {"requirement_key": "AI-ASSURANCE-INVENTORY", "statement": "Customer supplied an AI system inventory source for review.", "kind": "evidence_input", "mandatory": True},
        {"requirement_key": "AI-ASSURANCE-TRUST-EVALUATION", "statement": "The bounded AI system has an AITrustProof evaluation dossier and component receipt.", "kind": "control", "mandatory": True, "dependency_requirement_keys": ["AI-ASSURANCE-INVENTORY"]},
        {"requirement_key": "AI-ASSURANCE-REVIEW-BOUNDARY", "statement": "Assurance conclusions and external release remain human-authority bound.", "kind": "control", "mandatory": True, "dependency_requirement_keys": ["AI-ASSURANCE-TRUST-EVALUATION"]},
    ]
    telemetry_requested = bool(telemetry_review.get("required") or payload.get("seraph_telemetry") or telemetry_source_binding)
    telemetry_requirement_key = "AI-ASSURANCE-SERAPH-TELEMETRY"
    if telemetry_requested:
        requirements.append({
            "requirement_key": telemetry_requirement_key,
            "statement": "Requested Seraph telemetry and its case binding were reviewed; any chain, signature, identity, or coverage gaps remain visible for human review.",
            "kind": "evidence_input",
            "mandatory": bool(telemetry_review.get("required")),
        })
    evidence = []
    for source, path in source_files:
        evidence.append({
            "evidence_kind": "customer_ai_system_source",
            "source_ref": source["source_ref"],
            "sha256": _sha(path),
            "target_requirement_keys": ["AI-ASSURANCE-INVENTORY"],
            "relation": "supports",
            "authority_grade": "self_asserted",
            "trust_state": "captured_untrusted",
            "freshness_state": "unknown",
        })
    for filename, requirement in [
        ("AI_TRUST_DOSSIER.json", "AI-ASSURANCE-TRUST-EVALUATION"),
        ("PROOF_MANIFEST.json", "AI-ASSURANCE-REVIEW-BOUNDARY"),
    ]:
        path = component_dir / filename
        evidence.append({
            "evidence_kind": "derived_ai_trust_component_artifact",
            "source_ref": f"component_aitrustproof/{filename}",
            "sha256": _sha(path),
            "target_requirement_keys": [requirement],
            "relation": "supports",
            "authority_grade": "self_asserted",
            "trust_state": "captured_untrusted",
            "freshness_state": "unknown",
        })
    issues = []
    if telemetry_requested:
        evidence.append({
            "evidence_kind": "seraph_telemetry_review_receipt",
            "source_ref": "component_aitrustproof/SERAPH_CHALLENGE_RECEIPT.json",
            "sha256": _sha(telemetry_path),
            "target_requirement_keys": [telemetry_requirement_key],
            "relation": "supports",
            "authority_grade": "self_asserted",
            "trust_state": "captured_untrusted",
            "freshness_state": "unknown",
        })
        if telemetry_source_binding:
            evidence.append({
                "evidence_kind": "customer_seraph_telemetry_source",
                "source_ref": telemetry_source_binding["source_ref"],
                "sha256": telemetry_source_binding["source_sha256"],
                "target_requirement_keys": [telemetry_requirement_key],
                "relation": "supports",
                "authority_grade": "self_asserted",
                "trust_state": "captured_untrusted",
                "freshness_state": "unknown",
            })
        binding_state = (telemetry_source_binding or {}).get("case_binding_state")
        assessment_state = str(telemetry_review.get("state") or "NOT_ASSESSED")
        signature_state = str(telemetry_review.get("signature_state") or "NOT_ASSESSED")
        if binding_state in {"DECLARED_CASE_ID_MISMATCH", "DECLARED_CASE_ID_MISSING"} or assessment_state in {"INVALID_CHAIN", "INVALID_SIGNATURE"} or signature_state in {"INVALID", "INVALID_SIGNATURE"}:
            issues.append({
                "requirement_key": telemetry_requirement_key,
                "challenge_type": "contradiction",
                "severity": "material",
                "hypothesis": f"Seraph telemetry review contains a material defect: case_binding={binding_state or 'not supplied'}, chain_assessment={assessment_state}, signature={signature_state}.",
            })
        elif telemetry_review.get("required") and assessment_state in {"NOT_SUPPLIED", "NOT_REQUESTED", "MISSING"}:
            issues.append({
                "requirement_key": telemetry_requirement_key,
                "challenge_type": "missing_evidence",
                "severity": "material",
                "hypothesis": "Seraph telemetry is required for this review but no telemetry evidence was supplied.",
            })
    review = run_controlled_evidence_review(
        case, profile=REVIEW_PROFILE, requirements=requirements, evidence_inputs=evidence, issues=issues,
        output_dir=output_dir, operator_id=operator_id, now=now,
    )
    review_receipt, review_artifacts = _verify_result(
        product_id="dio_assurance", profile=REVIEW_PROFILE, output_dir=output_dir, result=review,
    )
    pack = review.get("review_pack") or {}
    matrix = pack.get("requirement_evidence_matrix") or []
    for row in matrix:
        for binding in row.get("source_provenance") or []:
            if binding.get("trust_state") != "captured_untrusted" or binding.get("freshness_state") != "unknown":
                raise RuntimeError("DIO AI Assurance composition promoted customer or derived evidence trust")
    receipt = {
        "schema": "dio.dio_ai_assurance.customer_execution.v1",
        "product_id": "dio_assurance",
        "component_product_id": COMPONENT_PRODUCT_ID,
        "case_id": str(payload.get("case_id") or ""),
        "source_count": len(source_files),
        "source_bindings": [{"source_ref": row[0]["source_ref"], "sha256": _sha(row[1])} for row in source_files],
        "component_receipt_sha256": _sha(component_dir / "AI_TRUST_RECEIPT.json"),
        "seraph_verdict": seraph.get("verdict"),
        "seraph_coverage_state": seraph.get("coverage_state"),
        "seraph_telemetry_review": {
            "assessment": telemetry_review,
            "challenge_receipt_path": "component_aitrustproof/SERAPH_CHALLENGE_RECEIPT.json",
            "challenge_receipt_sha256": _sha(telemetry_path),
            "customer_source_binding": telemetry_source_binding,
            "claim_boundary": "The exact telemetry file bytes are rechecked against the packet manifest. Its declared wrapper case ID is compared with the AI payload case ID, while chain records are independently checked against the payload case ID. Any mismatch remains an explicit review finding; this does not establish trusted source identity, completeness, live state, or execution authority.",
        },
        "review_receipt": review_receipt,
        "review_artifacts": review_artifacts,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "assurance_opinion_created": False,
        "compliance_certification_created": False,
        "control_effectiveness_certification_created": False,
        "model_approval_created": False,
        "risk_acceptance_created": False,
        "authority_created": False,
        "external_effects": False,
        "synthetic_acceptance_case": packet.get("synthetic_acceptance_not_customer_evidence") is True,
        "claim_boundary": "Hash binding verifies the bytes supplied for this run. Customer statements and derived AITrustProof outputs remain untrusted with unknown freshness until an authorised reviewer validates them. This is a review pack, not an assurance opinion or certification.",
    }
    write_json(output_dir / "DIO_AI_ASSURANCE_CUSTOMER_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}
