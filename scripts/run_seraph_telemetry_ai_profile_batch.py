#!/usr/bin/env python3
"""Exercise opt-in, case-bound Seraph telemetry review across AI profiles."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/SERAPH_TELEMETRY_AI_PROFILE_EXECUTIONS_20261108_V8"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _canonical_payload_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _telemetry(case_id: str, *, chain_case_id: str | None = None, required: bool = True) -> dict[str, Any]:
    from products.ai_trust.seraph_telemetry import AUDIT_GENESIS, EVENT_GENESIS

    event = {
        "event_id": f"EVT-{case_id}",
        "event_type": "review_requested",
        "timestamp": "2026-11-01T10:00:00Z",
        "data": {"case_id": chain_case_id or case_id, "trace_id": f"TRACE-{case_id}", "action": "human_review_required"},
        "prev_hash": EVENT_GENESIS,
    }
    event["event_hash"] = _digest({key: event.get(key) for key in ("event_id", "event_type", "timestamp", "data", "prev_hash")})
    audit = {
        "record_id": f"AUD-{case_id}",
        "timestamp": "2026-11-01T10:00:01Z",
        "principal": "customer-review-operator",
        "action": "hold_for_review",
        "targets": [case_id],
        "prev_hash": AUDIT_GENESIS,
        "case_id": case_id,
    }
    audit["record_hash"] = _digest({key: audit.get(key) for key in ("record_id", "timestamp", "principal", "action", "targets", "prev_hash")})
    return {
        "required": required,
        "event_chain": [event],
        "audit_chain": [audit],
        "event_head": event["event_hash"],
        "audit_head": audit["record_hash"],
    }


def _case(product: str, telemetry_mode: str | None, out: Path) -> dict[str, Any]:
    from products.customer_product_router import run_customer_product

    packet_names = {
        "AI IncidentRoom": "ai_incidentroom.json",
        "AssuranceRoom": "assuranceroom.json",
        "CriticalAI Assurance": "criticalai_assurance.json",
        "CyberAssurance": "cyberassurance.json",
        "ControlDrift": "controldrift.json",
        "DORA Vendor Assurance": "dora_vendor_assurance.json",
        "ModelProof": "modelproof.json",
        "ReleaseProof": "releaseproof.json",
    }
    packet_path = ROOT / "config/customer_products/examples" / packet_names[product]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    telemetry = None
    case_id = str(packet["case_id"])
    if telemetry_mode == "valid_unsigned":
        telemetry = _telemetry(case_id)
    elif telemetry_mode == "missing_required":
        telemetry = {"required": True, "event_chain": [], "audit_chain": [], "event_head": "", "audit_head": ""}
    elif telemetry_mode == "case_scope_mismatch":
        telemetry = _telemetry(case_id, chain_case_id="SYNTHETIC-OTHER-CASE-001")
    elif telemetry_mode == "not_required_empty":
        telemetry = {"required": False, "event_chain": [], "audit_chain": []}
    elif telemetry_mode is not None:
        raise ValueError(f"unknown telemetry scenario: {telemetry_mode}")
    if telemetry is not None:
        packet["seraph_telemetry"] = telemetry
    result = run_customer_product(product, packet, out, render_pdf=False)
    receipt_path = out / "CUSTOMER_PACKAGE_RECEIPT.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    telemetry_path = out / "SERAPH_TELEMETRY_REVIEW.json"
    summary = receipt.get("seraph_telemetry_review")
    if telemetry is None:
        if telemetry_path.exists() or summary is not None:
            raise RuntimeError(f"{product}: telemetry was not requested but a telemetry assessment was created")
        state = "NOT_REQUESTED"
        signature = "NOT_ASSESSED"
        challenged = False
    else:
        if not telemetry_path.is_file() or not isinstance(summary, dict):
            raise RuntimeError(f"{product}: telemetry review artifact or receipt binding is missing")
        review = json.loads(telemetry_path.read_text(encoding="utf-8"))
        state = str(review["assessment"]["state"])
        signature = str(review["assessment"]["signature_state"])
        challenged = any(row.get("requirement_key") == "SERAPH-TELEMETRY-INTEGRITY" for row in receipt.get("review_actions", []))
        if summary.get("sha256") != _sha(telemetry_path) or summary.get("state") != state:
            raise RuntimeError(f"{product}: telemetry receipt does not bind the rendered assessment")
        if telemetry.get("required") and (state != "HASH_CHAIN_VERIFIED" or signature != "VERIFIED_UNTRUSTED_KEY") and not challenged:
            raise RuntimeError(f"{product}: required unresolved telemetry did not create a review challenge")
    files = [
        {"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha(path)}
        for path in sorted(out.rglob("*")) if path.is_file()
    ]
    return {
        "product_name": product,
        "status": "EXECUTED_AND_BOUND",
        "case_output_dir": out.name,
        "case_id": packet["case_id"],
        "synthetic_acceptance_input": True,
        "telemetry_requested": telemetry is not None,
        "telemetry_required": bool((telemetry or {}).get("required", False)),
        "telemetry_integrity_state": state,
        "telemetry_signature_state": signature,
        "telemetry_challenge_open": challenged,
        "human_review_required": True,
        "release_authorized": False,
        "external_effects": False,
        "files": files,
    }


def _dio_assurance_case(out: Path) -> dict[str, Any]:
    from products.customer_product_router import run_customer_product

    packet_dir = ROOT / "acceptance_runs/68-product-sellability-20261027/NATIVE_PACKET_CUSTOMER_EXECUTIONS_20261102_V1/dio-ai-assurance-input/CUSTOMER_PACKET"
    result = run_customer_product("DIO AI Assurance", {
        "owner_authorized": True,
        "synthetic_acceptance_not_customer_evidence": True,
        "operator_id": "synthetic-seraph-telemetry-acceptance",
        "as_of": "2026-11-01T12:00:00Z",
        "customer_packet_dir": str(packet_dir),
    }, out, render_pdf=False)
    package = json.loads((out / "NATIVE_CUSTOMER_PACKET_RECEIPT.json").read_text(encoding="utf-8"))
    native = package.get("native_receipt") or {}
    telemetry = native.get("seraph_telemetry_review") or {}
    assessment = telemetry.get("assessment") or {}
    binding = telemetry.get("customer_source_binding") or {}
    if not telemetry or telemetry.get("challenge_receipt_sha256") is None:
        raise RuntimeError("DIO AI Assurance did not expose the bound Seraph telemetry result")
    if not binding.get("source_sha256") or binding.get("declared_case_id") == binding.get("payload_case_id"):
        raise RuntimeError("DIO AI Assurance synthetic case must expose the manifest-bound scope mismatch for review")
    if assessment.get("state") != "INVALID_CHAIN" or native.get("seraph_verdict") == "CLEAR":
        raise RuntimeError("DIO AI Assurance failed to challenge telemetry whose event case scope mismatched the AI payload")
    files = [
        {"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha(path)}
        for path in sorted(out.rglob("*")) if path.is_file()
    ]
    return {
        "product_name": "DIO AI Assurance",
        "status": "EXECUTED_AND_BOUND",
        "case_output_dir": out.name,
        "case_id": native.get("review_receipt", {}).get("case_id"),
        "synthetic_acceptance_input": True,
        "telemetry_requested": True,
        "telemetry_required": bool(assessment.get("required")),
        "telemetry_integrity_state": assessment.get("state"),
        "telemetry_signature_state": assessment.get("signature_state"),
        "telemetry_case_scope": binding,
        "seraph_verdict": native.get("seraph_verdict"),
        "seraph_telemetry_challenge_receipt_sha256": telemetry.get("challenge_receipt_sha256"),
        "human_review_required": True,
        "release_authorized": False,
        "external_effects": False,
        "files": files,
    }


def _agent_authority_case(out: Path) -> dict[str, Any]:
    from products.customer_product_router import run_customer_product

    packet = json.loads((ROOT / "config/customer_products/examples/agent_authority.json").read_text(encoding="utf-8"))
    assessment = packet["agent_assessment"]
    case_id = str(assessment["case_id"])
    telemetry = assessment.get("seraph_telemetry")
    if not isinstance(telemetry, dict):
        telemetry = _telemetry(case_id)
        assessment["seraph_telemetry"] = telemetry
    result = run_customer_product("Agent Authority", packet, out, render_pdf=False)
    package = json.loads((out / "AGENT_AUTHORITY_PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
    review = json.loads((out / "SERAPH_TELEMETRY_REVIEW.json").read_text(encoding="utf-8"))
    trust_dir = out / "agent_authority"
    trust_receipt = json.loads((trust_dir / "AI_TRUST_RECEIPT.json").read_text(encoding="utf-8"))
    proof_manifest = json.loads((trust_dir / "PROOF_MANIFEST.json").read_text(encoding="utf-8"))
    challenge = json.loads((trust_dir / "SERAPH_CHALLENGE_RECEIPT.json").read_text(encoding="utf-8"))
    assessment_result = review.get("assessment") or {}
    source_binding = review.get("source_binding") or {}
    if (assessment_result.get("state") != "HASH_CHAIN_VERIFIED"
            or assessment_result.get("signature_state") != "UNVERIFIED"
            or assessment_result.get("source_identity_state") != "UNVERIFIED"
            or source_binding.get("assessment_file_sha256") != _sha(out / "CUSTOMER_AGENT_ASSESSMENT.json")
            or source_binding.get("challenge_receipt_sha256") != _sha(trust_dir / "SERAPH_CHALLENGE_RECEIPT.json")
            # source_binding hashes the serialized receipt file; receipt_sha256
            # inside that file is the challenge's canonical payload digest.
            # They are deliberately different hash domains.
            or challenge.get("receipt_sha256") is None
            or source_binding.get("challenge_receipt_path") != "agent_authority/SERAPH_CHALLENGE_RECEIPT.json"
            or challenge.get("receipt_sha256") != package.get("seraph_challenge", {}).get("receipt_sha256")
            or trust_receipt.get("seraph_telemetry_review") != proof_manifest.get("seraph_telemetry_review")
            or package.get("seraph_telemetry_review") != review
            or result.get("release_authorized") is not False):
        raise RuntimeError("Agent Authority Seraph telemetry was not fully source-bound or review-held")
    files = [{"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha(path)}
             for path in sorted(out.rglob("*")) if path.is_file()]
    return {
        "product_name": "Agent Authority",
        "status": "EXECUTED_AND_BOUND",
        "case_output_dir": out.name,
        "case_id": case_id,
        "synthetic_acceptance_input": True,
        "telemetry_requested": True,
        "telemetry_required": bool(assessment_result.get("required")),
        "telemetry_integrity_state": assessment_result.get("state"),
        "telemetry_signature_state": assessment_result.get("signature_state"),
        "telemetry_source_identity_state": assessment_result.get("source_identity_state"),
        "telemetry_input_sha256": (trust_receipt.get("seraph_telemetry_review") or {}).get("input_sha256"),
        "telemetry_challenge_receipt_sha256": source_binding.get("challenge_receipt_sha256"),
        "seraph_verdict": package.get("seraph_challenge", {}).get("verdict"),
        "human_review_required": True,
        "release_authorized": False,
        "external_effects": False,
        "files": files,
    }


def _changeproof_case(out: Path) -> dict[str, Any]:
    from products.customer_product_router import run_customer_product

    packet = json.loads((ROOT / "config/customer_products/examples/changeproof.json").read_text(encoding="utf-8"))
    assessment = packet["change_assessment"]
    case_id = str(assessment["case_id"])
    telemetry = _telemetry(case_id)
    assessment["seraph_telemetry"] = telemetry
    result = run_customer_product("ChangeProof", packet, out, render_pdf=False)
    customer = json.loads((out / "AI_TRUST_CUSTOMER_RECEIPT.json").read_text(encoding="utf-8"))
    review = json.loads((out / "SERAPH_TELEMETRY_REVIEW.json").read_text(encoding="utf-8"))
    trust_dir = out / "ai_trust"
    trust_receipt = json.loads((trust_dir / "AI_TRUST_RECEIPT.json").read_text(encoding="utf-8"))
    proof_manifest = json.loads((trust_dir / "PROOF_MANIFEST.json").read_text(encoding="utf-8"))
    challenge = json.loads((trust_dir / "SERAPH_CHALLENGE_RECEIPT.json").read_text(encoding="utf-8"))
    source_file = out / "CUSTOMER_AI_TRUST_ASSESSMENT.json"
    binding = review.get("source_binding") or {}
    summary = customer.get("seraph_telemetry_review") or {}
    if (review.get("assessment", {}).get("state") != "HASH_CHAIN_VERIFIED"
            or review.get("assessment", {}).get("signature_state") != "UNVERIFIED"
            or binding.get("assessment_file_sha256") != _sha(source_file)
            or binding.get("telemetry_input_sha256") != _canonical_payload_digest(telemetry)
            or binding.get("challenge_receipt_sha256") != _sha(trust_dir / "SERAPH_CHALLENGE_RECEIPT.json")
            or binding.get("challenge_receipt_canonical_sha256") != challenge.get("receipt_sha256")
            or summary != trust_receipt.get("seraph_telemetry_review")
            or summary != proof_manifest.get("seraph_telemetry_review")
            or customer.get("seraph_challenge", {}).get("evidence_context", {}).get("seraph_telemetry") != review.get("assessment")
            or result.get("release_authorized") is not False):
        raise RuntimeError("ChangeProof Seraph telemetry was not fully source-bound or review-held")
    files = [{"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha(path)}
             for path in sorted(out.rglob("*")) if path.is_file()]
    return {
        "product_name": "ChangeProof",
        "status": "EXECUTED_AND_BOUND",
        "case_output_dir": out.name,
        "case_id": case_id,
        "synthetic_acceptance_input": True,
        "telemetry_requested": True,
        "telemetry_required": True,
        "telemetry_integrity_state": summary.get("state"),
        "telemetry_signature_state": summary.get("signature_state"),
        "telemetry_source_identity_state": summary.get("source_identity_state"),
        "seraph_verdict": customer.get("seraph_challenge", {}).get("verdict"),
        "human_review_required": True,
        "release_authorized": False,
        "external_effects": False,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"output directory must be empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    cases = [
        ("AI IncidentRoom", "valid_unsigned"),
        ("AssuranceRoom", None),
        ("CriticalAI Assurance", "missing_required"),
        ("CyberAssurance", "valid_unsigned"),
        ("ControlDrift", "case_scope_mismatch"),
        ("DORA Vendor Assurance", "not_required_empty"),
        ("ModelProof", "valid_unsigned"),
        ("ReleaseProof", "not_required_empty"),
    ]
    results = []
    for index, (product, telemetry) in enumerate(cases, 1):
        case_out = out / f"case-{index:02d}-{product.lower().replace(' ', '-') }"
        results.append(_case(product, telemetry, case_out))
    results.append(_dio_assurance_case(out / "case-09-dio-ai-assurance"))
    results.append(_agent_authority_case(out / "case-10-agent-authority"))
    results.append(_changeproof_case(out / "case-11-changeproof"))
    receipt = {
        "schema": "dio.seraph.telemetry.ai_profile_batch.v1",
        "created_on": "2026-11-01",
        "synthetic_acceptance_inputs_only": True,
        "results": results,
        "all_review_boundaries_preserved": all(row["human_review_required"] and row["release_authorized"] is False and row["external_effects"] is False for row in results),
        "product_qualification": "NOT_ESTABLISHED",
        "commercial_validation": "UNPROVED",
    }
    receipt_path = out / "BATCH_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "receipt": str(receipt_path), "receipt_sha256": _sha(receipt_path), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
