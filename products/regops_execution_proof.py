from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
from products.regops.runner import run_controlled_regops_review


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
AI_FIXTURE_PATH = ROOT / "config" / "products" / "golden" / "airegreadiness" / "reference_case.json"
PRODUCT_ID = "dio_regops"
PROFILE_KEY = "dio_regops"
PROFILE_ID = "profile.regops.mixed_ai_operational_v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def controlled_regops_fixture() -> dict[str, Any]:
    return {
        "fixture_kind": "dio.controlled_regops_fixture.v1",
        "intake_authority_approved": True,
        "profile_id": PROFILE_ID,
        "prerequisites": [
            {
                "prerequisite_id": "OWN-1",
                "statement": "Capability ownership is explicit and evidenced.",
                "mandatory": True,
                "dependency_prerequisite_ids": [],
            },
            {
                "prerequisite_id": "POL-1",
                "statement": "Required operational policy is current and evidenced.",
                "mandatory": True,
                "dependency_prerequisite_ids": [],
            },
        ],
        "evidence_inputs": [
            {
                "evidence_kind": "operational_record",
                "source_ref": "operations://controlled/OWN-1",
                "sha256": "a" * 64,
                "target_prerequisite_ids": ["OWN-1"],
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "policy_record",
                "source_ref": "operations://controlled/POL-1",
                "sha256": "b" * 64,
                "target_prerequisite_ids": ["POL-1"],
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
        ],
        "gaps": [],
        "ai_regulatory_context": _read(AI_FIXTURE_PATH),
    }


def _route_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    routes = _read(ROUTES_PATH)
    reconciliation = _read(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(PROFILE_KEY)
    binding = (reconciliation.get("resolved_composition_bindings") or {}).get(PROFILE_KEY)
    if not isinstance(route, dict) or not isinstance(binding, dict):
        raise ProductClassExecutionProofError("DIO RegOps route/composition binding is missing")
    if binding.get("canonical_product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("DIO RegOps canonical composition identity drifted")
    if binding.get("relationship") != "composition_reuse" or binding.get("state") != "identity_equivalence_rejected":
        raise ProductClassExecutionProofError("DIO RegOps composition-reuse boundary drifted")
    if binding.get("reusable_component_product_id") != "dio_airegreadiness":
        raise ProductClassExecutionProofError("DIO RegOps AIRegReadiness component binding drifted")
    if route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError("DIO RegOps cannot become auto-promotable")
    return route, binding


def run_regops_execution_proof(
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("DIO RegOps execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("intake_authority_approved") is not True:
        raise ProductClassExecutionProofError("DIO RegOps controlled fixture requires intake_authority_approved=true")
    if fixture.get("profile_id") != PROFILE_ID:
        raise ProductClassExecutionProofError("DIO RegOps controlled fixture profile drifted")
    route, binding = _route_contract()

    prerequisites = fixture.get("prerequisites")
    evidence_inputs = fixture.get("evidence_inputs")
    gaps = fixture.get("gaps")
    ai_context = fixture.get("ai_regulatory_context")
    if not isinstance(prerequisites, list) or not isinstance(evidence_inputs, list) or not isinstance(gaps, list) or not isinstance(ai_context, dict):
        raise ProductClassExecutionProofError("DIO RegOps controlled fixture is incomplete")

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    source_path = output_dir / "CONTROLLED_REGOPS_SOURCE.json"
    _write_json(source_path, fixture)
    case = new_case(
        product=PRODUCT_ID,
        job_id="proof-dio-regops",
        source={"source": {"fixture": source_path.name}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["controlled prerequisites", "controlled operational evidence", "bounded AI regulatory context"],
        expected_outputs=["requirement register", "evidence receipt set", "deadline queue", "readiness decision", "professional escalation record"],
        required_authorities=["fixture_owner", "compliance_reviewer", "professional_reviewer_when_required"],
        intake_state="approved",
        now=now,
    )
    result = run_controlled_regops_review(
        case,
        profile_id=PROFILE_ID,
        prerequisites=prerequisites,
        evidence_inputs=evidence_inputs,
        gaps=gaps,
        ai_regulatory_context=ai_context,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    receipt = result.get("receipt") or {}
    manifest = result.get("proof_manifest") or {}
    if receipt.get("schema") != "dio.regops.controlled_processing_receipt.v1" or receipt.get("processor_id") != "regops_controlled_readiness_v1":
        raise ProductClassExecutionProofError("DIO RegOps controlled processor receipt identity drifted")
    if receipt.get("internal_processing") != "COMPLETE":
        raise ProductClassExecutionProofError("DIO RegOps controlled processor did not complete")
    if receipt.get("human_review_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError("DIO RegOps human/release gate drifted")
    for field in ("legal_clearance_created", "professional_decision_created", "filing_authority_created", "authority_created", "execution_performed", "external_effects", "external_release"):
        if receipt.get(field) is not False:
            raise ProductClassExecutionProofError(f"DIO RegOps illegally promotes {field}")
    if receipt.get("ai_regulatory_component_state") != "CONTROLLED_CONTEXT_EVALUATED":
        raise ProductClassExecutionProofError("DIO RegOps bounded AI regulatory component was not evaluated")

    if manifest.get("schema") != "dio.regops.controlled_proof_manifest.v1" or manifest.get("provider_id") != "regops_controlled_readiness_v1":
        raise ProductClassExecutionProofError("DIO RegOps proof manifest identity drifted")
    for field in ("authority_created", "execution_performed", "external_effects", "external_release"):
        if manifest.get(field) is not False:
            raise ProductClassExecutionProofError(f"DIO RegOps proof manifest illegally promotes {field}")

    artifacts: list[dict[str, Any]] = []
    for row in manifest.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        path = output_dir / filename
        if not filename or not path.is_file() or _sha_file(path) != row.get("sha256"):
            raise ProductClassExecutionProofError(f"DIO RegOps artifact verification failed: {filename}")
        artifacts.append({"artifact_type": row.get("artifact_type"), "filename": filename, "sha256": row.get("sha256")})
    for filename, artifact_type in (("PROOF_MANIFEST.json", "proof_manifest"), ("REGOPS_PROCESSING_RECEIPT.json", "processor_receipt"), (source_path.name, "controlled_source")):
        path = output_dir / filename
        if not path.is_file():
            raise ProductClassExecutionProofError(f"DIO RegOps persisted artifact is missing: {filename}")
        artifacts.append({"artifact_type": artifact_type, "filename": filename, "sha256": _sha_file(path)})

    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "product_id": PRODUCT_ID,
        "adapter_family": "regops_controlled_readiness",
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": "product.processor.regops_controlled_readiness",
        "executor_id": "regops_controlled_readiness_v1",
        "executor_ref": "products/regops/runner.py",
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "processor_receipt_schema": receipt.get("schema"),
        "processor_receipt_internal_state": receipt.get("internal_processing"),
        "human_review_gate": receipt.get("human_review_gate"),
        "external_release_gate": receipt.get("external_release_gate"),
        "readiness_state": receipt.get("readiness_state"),
        "ai_regulatory_component_state": receipt.get("ai_regulatory_component_state"),
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "artifacts": artifacts,
        "route_snapshot": {
            "route_kind": route.get("route_kind"),
            "auto_promotable": route.get("auto_promotable"),
            "relationship": binding.get("relationship"),
            "reusable_component_product_id": binding.get("reusable_component_product_id"),
        },
        "claim_ceiling": (
            "This receipt proves that DIO RegOps executed a bounded controlled readiness review over configured prerequisites, "
            "evidence and an AIRegReadiness component context. A readiness ALLOW/REFUSE/NEEDS_YOU state is not legal clearance, "
            "professional advice, filing authority, operational execution, external release, public-launch authority, or commercial proof."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
