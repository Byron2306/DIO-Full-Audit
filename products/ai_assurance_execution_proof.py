from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.ai_trust.runner import EXECUTOR_ID as AI_TRUST_EXECUTOR_ID, run_ai_trust
from products.evidence_profile_execution_proof import _verify_result as _verify_review_result
from products.evidence_review import run_controlled_evidence_review
from products.governed_case import new_case
from products.product_class_execution_proof import (
    PROOF_SCHEMA,
    ProductClassExecutionProofError,
    _assert_output_dir_is_fresh,
    _canonical,
    _sha_bytes,
    _sha_file,
    _write_json,
    verify_execution_proof,
)
from products.registry import get_profile


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
AI_TRUST_MANIFEST = ROOT / "config" / "products" / "manifests" / "aitrustproof.json"
AI_TRUST_FIXTURE = ROOT / "config" / "products" / "golden" / "aitrustproof" / "reference_case.json"
PORTFOLIO_PATH = ROOT / "config" / "dio_product_portfolio.json"
ATLAS_KEY = "dio_ai_assurance"
PRODUCT_ID = "dio_assurance"
COMPONENT_PRODUCT_ID = "dio_aitrustproof"
REVIEW_PROFILE_ID = "dio_ai_assurance_composition"

REVIEW_PROFILE: dict[str, Any] = {
    "schema": "dio.evidence_review.profile.v1",
    "profile_id": REVIEW_PROFILE_ID,
    "product_id": PRODUCT_ID,
    "category": "ai_governance_assurance_composition_review",
    "default_requirement_kind": "control",
    "required_meta_products": ["meta_evidence", "meta_assurance", "meta_room"],
    "release_guard_meta_product": "meta_authority",
    "artifact_prefix": "DIOAIASSURANCE",
    "review_pack_title": "DIO AI Assurance Controlled Composition Review Pack",
    "human_gate_reason": (
        "Assurance conclusions, compliance determinations, control-effectiveness judgements, risk acceptance, "
        "model approval and external release remain with authorised human assurance and control owners."
    ),
    "forbidden_outcomes": [
        "assurance_opinion",
        "compliance_certification",
        "control_effectiveness_certification",
        "model_approval",
        "risk_acceptance",
        "external_release",
    ],
    "authority_created": False,
    "external_effects": False,
    "external_release": False,
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def controlled_ai_assurance_fixture() -> dict[str, Any]:
    return {
        "fixture_kind": "dio.controlled_ai_assurance_composition_fixture.v1",
        "intake_authority_approved": True,
        "source_authority_scope": "controlled_fixture_only",
        "ai_trust_payload": _read(AI_TRUST_FIXTURE),
    }


def _route_contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    routes = _read(ROUTES_PATH)
    reconciliation = _read(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(ATLAS_KEY)
    binding = (reconciliation.get("resolved_composition_bindings") or {}).get(ATLAS_KEY)
    if not isinstance(route, dict) or not isinstance(binding, dict):
        raise ProductClassExecutionProofError("DIO AI Assurance route/composition binding is missing")
    if route.get("route_kind") != "profile_extension" or route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError("DIO AI Assurance route boundary drifted")
    if route.get("suggested_engine") is not None:
        raise ProductClassExecutionProofError("DIO AI Assurance atlas route cannot silently gain a direct engine")
    if binding.get("canonical_product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("DIO AI Assurance broader canonical product identity drifted")
    if binding.get("reusable_component_product_id") != COMPONENT_PRODUCT_ID:
        raise ProductClassExecutionProofError("DIO AI Assurance reusable AITrustProof component drifted")
    if binding.get("relationship") != "composition_reuse" or binding.get("state") != "identity_equivalence_rejected":
        raise ProductClassExecutionProofError("DIO AI Assurance composition-reuse boundary drifted")
    portfolio_profile = get_profile(PRODUCT_ID)
    if portfolio_profile.get("category") != "ai_governance_assurance":
        raise ProductClassExecutionProofError("DIO Assurance portfolio category drifted")
    return route, binding, portfolio_profile


def _verify_component(component_dir: Path, result: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = result.get("receipt") or {}
    manifest = result.get("proof_manifest") or {}
    envelope = result.get("envelope") or {}
    if receipt.get("schema") != "dio.ai_trust_execution_receipt.v1" or receipt.get("product_id") != COMPONENT_PRODUCT_ID:
        raise ProductClassExecutionProofError("DIO AI Assurance AITrustProof component receipt identity drifted")
    if receipt.get("executor_id") != AI_TRUST_EXECUTOR_ID or AI_TRUST_EXECUTOR_ID != "ai_trust_internal_runner_v1":
        raise ProductClassExecutionProofError("DIO AI Assurance AITrustProof component executor drifted")
    if receipt.get("human_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError("DIO AI Assurance component human/release gate drifted")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise ProductClassExecutionProofError("DIO AI Assurance component illegally created authority/effects")
    if manifest.get("schema") != "dio.ai_trust_proof_manifest.v1" or manifest.get("product_id") != COMPONENT_PRODUCT_ID:
        raise ProductClassExecutionProofError("DIO AI Assurance component proof manifest identity drifted")
    if manifest.get("authority_created") is not False or manifest.get("external_effects") is not False or manifest.get("external_release") is not False:
        raise ProductClassExecutionProofError("DIO AI Assurance component crossed authority/release boundary")
    if envelope.get("schema") != "dio.ai_trust_envelope.v1" or envelope.get("product_id") != COMPONENT_PRODUCT_ID:
        raise ProductClassExecutionProofError("DIO AI Assurance trust envelope identity drifted")
    if envelope.get("human_gate") != "NEEDS_YOU" or envelope.get("external_release") != "REFUSE":
        raise ProductClassExecutionProofError("DIO AI Assurance component envelope boundary drifted")

    artifacts: list[dict[str, Any]] = []
    for row in manifest.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        path = component_dir / filename
        if not filename or not path.is_file() or _sha_file(path) != row.get("sha256"):
            raise ProductClassExecutionProofError(f"DIO AI Assurance component artifact verification failed: {filename}")
        artifacts.append({
            "artifact_type": f"aitrust_component_{str(row.get('artifact_type') or 'artifact').lower()}",
            "filename": str(Path("component_aitrustproof") / filename),
            "sha256": row.get("sha256"),
        })
    for filename, artifact_type in (
        ("PROOF_MANIFEST.json", "aitrust_component_proof_manifest"),
        ("AI_TRUST_RECEIPT.json", "aitrust_component_execution_receipt"),
    ):
        path = component_dir / filename
        if not path.is_file():
            raise ProductClassExecutionProofError(f"DIO AI Assurance component persisted artifact is missing: {filename}")
        artifacts.append({
            "artifact_type": artifact_type,
            "filename": str(Path("component_aitrustproof") / filename),
            "sha256": _sha_file(path),
        })
    return receipt, artifacts


def run_ai_assurance_execution_proof(
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("DIO AI Assurance execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("intake_authority_approved") is not True:
        raise ProductClassExecutionProofError("DIO AI Assurance controlled fixture requires intake_authority_approved=true")
    payload = fixture.get("ai_trust_payload")
    if not isinstance(payload, dict) or payload.get("source_type") != "ai_system":
        raise ProductClassExecutionProofError("DIO AI Assurance controlled fixture requires an ai_system AITrustProof payload")
    route, binding, portfolio_profile = _route_contract()

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    source_path = output_dir / "CONTROLLED_AI_ASSURANCE_SOURCE.json"
    _write_json(source_path, fixture)

    component_dir = output_dir / "component_aitrustproof"
    component_result = run_ai_trust(
        COMPONENT_PRODUCT_ID,
        payload,
        output_dir=component_dir,
        operator_id=operator_id,
        now=now,
    )
    component_receipt, component_artifacts = _verify_component(component_dir, component_result)

    component_dossier = component_dir / "AI_TRUST_DOSSIER.json"
    component_proof = component_dir / "PROOF_MANIFEST.json"
    component_receipt_path = component_dir / "AI_TRUST_RECEIPT.json"
    case = new_case(
        product=PRODUCT_ID,
        job_id="proof-dio-ai-assurance",
        source={
            "source": {
                "fixture": source_path.name,
                "bounded_component_product_id": COMPONENT_PRODUCT_ID,
                "component_receipt": str(component_receipt_path.relative_to(output_dir)),
            },
            "evidence": [],
        },
        source_path=source_path,
        evidence_inputs=["AI system inventory", "AITrustProof dossier", "AITrustProof execution receipt", "AITrustProof proof manifest"],
        expected_outputs=["control-evidence matrix", "gap and exception register", "review queue", "assurance evidence pack"],
        required_authorities=["system_owner", "control_owner", "assurance_reviewer", "release_operator"],
        intake_state="approved",
        now=now,
    )
    review_result = run_controlled_evidence_review(
        case,
        profile=REVIEW_PROFILE,
        requirements=[
            {
                "requirement_key": "AI-ASSURANCE-INVENTORY",
                "statement": "A bounded AI system identity and inventory record is present for assurance review.",
                "kind": "evidence_input",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
            {
                "requirement_key": "AI-ASSURANCE-TRUST-EVALUATION",
                "statement": "The bounded AI system has a hash-bound AITrustProof evaluation dossier and execution receipt.",
                "kind": "control",
                "mandatory": True,
                "dependency_requirement_keys": ["AI-ASSURANCE-INVENTORY"],
            },
            {
                "requirement_key": "AI-ASSURANCE-REVIEW-BOUNDARY",
                "statement": "AI assurance conclusions and release remain explicitly human-authority bound.",
                "kind": "control",
                "mandatory": True,
                "dependency_requirement_keys": ["AI-ASSURANCE-TRUST-EVALUATION"],
            },
        ],
        evidence_inputs=[
            {
                "evidence_kind": "ai_trust_dossier_binding",
                "source_ref": "aitrustproof://controlled/dossier",
                "sha256": _sha_file(component_dossier),
                "target_requirement_keys": ["AI-ASSURANCE-INVENTORY"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "ai_trust_execution_receipt_binding",
                "source_ref": "aitrustproof://controlled/execution-receipt",
                "sha256": _sha_file(component_receipt_path),
                "target_requirement_keys": ["AI-ASSURANCE-TRUST-EVALUATION"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "ai_trust_proof_manifest_binding",
                "source_ref": "aitrustproof://controlled/proof-manifest",
                "sha256": _sha_file(component_proof),
                "target_requirement_keys": ["AI-ASSURANCE-REVIEW-BOUNDARY"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
        ],
        issues=[],
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    review_receipt, review_artifacts = _verify_review_result(
        product_id=PRODUCT_ID,
        profile=REVIEW_PROFILE,
        output_dir=output_dir,
        result=review_result,
    )
    states = {
        row.get("requirement_key"): row.get("review_state")
        for row in (review_result.get("review_pack") or {}).get("requirement_evidence_matrix") or []
    }
    if states != {
        "AI-ASSURANCE-INVENTORY": "SUPPORTED",
        "AI-ASSURANCE-REVIEW-BOUNDARY": "SUPPORTED",
        "AI-ASSURANCE-TRUST-EVALUATION": "SUPPORTED",
    }:
        raise ProductClassExecutionProofError(f"DIO AI Assurance control-evidence composition did not resolve as expected: {states}")

    artifacts = component_artifacts + review_artifacts
    artifacts.append({"artifact_type": "controlled_source", "filename": source_path.name, "sha256": _sha_file(source_path)})
    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "product_id": PRODUCT_ID,
        "atlas_product_class": ATLAS_KEY,
        "adapter_family": "ai_assurance_composition_reuse",
        "portfolio_profile_sha256": "sha256:" + _sha_file(PORTFOLIO_PATH),
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "component_manifest": str(AI_TRUST_MANIFEST.relative_to(ROOT)),
        "component_manifest_sha256": "sha256:" + _sha_file(AI_TRUST_MANIFEST),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": "composition.processor.dio_ai_assurance",
        "executor_id": "ai_trust_internal_runner_v1+controlled_evidence_review_v1",
        "executor_ref": "products/ai_trust/runner.py + products/evidence_review.py",
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "component_product_id": COMPONENT_PRODUCT_ID,
        "component_executor_id": component_receipt.get("executor_id"),
        "component_execution_proved": True,
        "identity_equivalence_rejected": True,
        "composition_review_processor": "controlled_evidence_review_v1",
        "processor_receipt_schema": review_receipt.get("schema"),
        "processor_receipt_internal_state": review_receipt.get("internal_processing"),
        "human_review_gate": review_receipt.get("human_review_gate"),
        "external_release_gate": review_receipt.get("external_release_gate"),
        "control_evidence_states": states,
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "artifacts": artifacts,
        "route_snapshot": {
            "route_kind": route.get("route_kind"),
            "auto_promotable": route.get("auto_promotable"),
            "relationship": binding.get("relationship"),
            "canonical_product_id": binding.get("canonical_product_id"),
            "reusable_component_product_id": binding.get("reusable_component_product_id"),
            "identity_state": binding.get("state"),
            "portfolio_status": portfolio_profile.get("status"),
        },
        "claim_ceiling": (
            "This receipt proves that the bounded AITrustProof component executed over the controlled AI-system fixture and that its "
            "hash-bound dossier, execution receipt and proof manifest were consumed by a broader DIO Assurance control-evidence review. "
            "AITrustProof is not an identity alias for DIO Assurance. This proof creates no assurance opinion, compliance certification, "
            "control-effectiveness certification, model approval, risk acceptance, external effect, public-launch authority or external release."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {
        "proof": proof,
        "component_result": component_result,
        "processor_result": review_result,
        "output_dir": str(output_dir),
    }
