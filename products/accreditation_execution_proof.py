from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.accreditation.runner import run_controlled_accreditation_review
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


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
REGULATORY_FIXTURE_PATH = ROOT / "config" / "products" / "golden" / "educationaccreditationproof" / "reference_case.json"
PRODUCT_ID = "dio_accreditation"
ATLAS_CLASS = "homs_accreditation"
FRAMEWORK_ID = "framework.education_accreditation"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def controlled_accreditation_fixture() -> dict[str, Any]:
    return {
        "fixture_kind": "dio.controlled_accreditation_fixture.v1",
        "atlas_product_class": ATLAS_CLASS,
        "intake_authority_approved": True,
        "framework_id": FRAMEWORK_ID,
        "criteria": [
            {
                "criterion_id": "ACC-1",
                "statement": "Programme evidence is mapped to the selected accreditation criterion.",
                "mandatory": True,
                "dependency_criterion_ids": [],
            },
            {
                "criterion_id": "ACC-2",
                "statement": "Open accreditation gaps are explicitly retained for human review.",
                "mandatory": True,
                "dependency_criterion_ids": [],
            },
        ],
        "evidence_inputs": [
            {
                "evidence_kind": "programme_record",
                "source_ref": "programme://controlled/evidence-1",
                "sha256": "a" * 64,
                "target_criterion_ids": ["ACC-1"],
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        ],
        "gaps": [
            {
                "criterion_id": "ACC-2",
                "challenge_type": "missing_evidence",
                "severity": "material",
                "hypothesis": "Controlled proof fixture intentionally retains an unresolved accreditation gap.",
            }
        ],
        "regulatory_context": _read(REGULATORY_FIXTURE_PATH),
    }


def _route_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    routes = _read(ROUTES_PATH)
    reconciliation = _read(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(ATLAS_CLASS)
    binding = (reconciliation.get("resolved_composition_bindings") or {}).get(ATLAS_CLASS)
    if not isinstance(route, dict) or not isinstance(binding, dict):
        raise ProductClassExecutionProofError("HOMS Accreditation route/composition binding is missing")
    if binding.get("canonical_product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("HOMS Accreditation canonical composition identity drifted")
    if binding.get("relationship") != "composition_reuse" or binding.get("state") != "identity_equivalence_rejected":
        raise ProductClassExecutionProofError("HOMS Accreditation composition-reuse boundary drifted")
    if binding.get("reusable_component_product_id") != "dio_educationaccreditationproof":
        raise ProductClassExecutionProofError("HOMS Accreditation reusable component binding drifted")
    if route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError("HOMS Accreditation cannot become auto-promotable")
    return route, binding


def run_accreditation_execution_proof(
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("Accreditation execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("intake_authority_approved") is not True:
        raise ProductClassExecutionProofError("Accreditation controlled fixture requires intake_authority_approved=true")
    if fixture.get("atlas_product_class") != ATLAS_CLASS or fixture.get("framework_id") != FRAMEWORK_ID:
        raise ProductClassExecutionProofError("Accreditation controlled fixture identity/framework drifted")
    route, binding = _route_contract()

    criteria = fixture.get("criteria")
    evidence_inputs = fixture.get("evidence_inputs")
    gaps = fixture.get("gaps")
    regulatory_context = fixture.get("regulatory_context")
    if not isinstance(criteria, list) or not isinstance(evidence_inputs, list) or not isinstance(gaps, list) or not isinstance(regulatory_context, dict):
        raise ProductClassExecutionProofError("Accreditation controlled fixture is incomplete")

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    source_path = output_dir / "CONTROLLED_ACCREDITATION_SOURCE.json"
    _write_json(source_path, fixture)
    case = new_case(
        product=PRODUCT_ID,
        job_id="proof-homs-accreditation",
        source={"source": {"fixture": source_path.name}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["controlled accreditation criteria", "controlled programme evidence", "bounded regulatory context"],
        expected_outputs=["standards-evidence matrix", "gap register", "corrective-action tracker", "review pack", "signatory receipt"],
        required_authorities=["fixture_owner", "quality_assurance_reviewer", "authorised_signatory"],
        intake_state="approved",
        now=now,
    )
    result = run_controlled_accreditation_review(
        case,
        framework_id=FRAMEWORK_ID,
        criteria=criteria,
        evidence_inputs=evidence_inputs,
        gaps=gaps,
        regulatory_context=regulatory_context,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    receipt = result.get("receipt") or {}
    manifest = result.get("proof_manifest") or {}
    if receipt.get("schema") != "dio.accreditation.controlled_processing_receipt.v1" or receipt.get("processor_id") != "accreditation_controlled_review_v1":
        raise ProductClassExecutionProofError("Accreditation controlled processor receipt identity drifted")
    if receipt.get("internal_processing") != "COMPLETE":
        raise ProductClassExecutionProofError("Accreditation controlled processor did not complete")
    if receipt.get("human_review_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError("Accreditation human/release gate drifted")
    for field in (
        "signatory_receipt_created",
        "accreditation_decision_created",
        "institutional_attestation_created",
        "regulator_acceptance_created",
        "authority_created",
        "execution_performed",
        "external_effects",
        "external_release",
    ):
        if receipt.get(field) is not False:
            raise ProductClassExecutionProofError(f"Accreditation illegally promotes {field}")
    if receipt.get("regulated_component_state") != "CONTROLLED_CONTEXT_EVALUATED":
        raise ProductClassExecutionProofError("Accreditation regulated component was not evaluated")

    if manifest.get("schema") != "dio.accreditation.controlled_proof_manifest.v1" or manifest.get("provider_id") != "accreditation_controlled_review_pack_v1":
        raise ProductClassExecutionProofError("Accreditation proof manifest identity drifted")
    for field in ("authority_created", "execution_performed", "external_effects", "external_release"):
        if manifest.get(field) is not False:
            raise ProductClassExecutionProofError(f"Accreditation proof manifest illegally promotes {field}")

    artifacts: list[dict[str, Any]] = []
    for row in manifest.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        path = output_dir / filename
        if not filename or not path.is_file() or _sha_file(path) != row.get("sha256"):
            raise ProductClassExecutionProofError(f"Accreditation artifact verification failed: {filename}")
        artifacts.append({"artifact_type": row.get("artifact_type"), "filename": filename, "sha256": row.get("sha256")})
    for filename, artifact_type in (
        ("PROOF_MANIFEST.json", "proof_manifest"),
        ("ACCREDITATION_PROCESSING_RECEIPT.json", "processor_receipt"),
        (source_path.name, "controlled_source"),
    ):
        path = output_dir / filename
        if not path.is_file():
            raise ProductClassExecutionProofError(f"Accreditation persisted artifact is missing: {filename}")
        artifacts.append({"artifact_type": artifact_type, "filename": filename, "sha256": _sha_file(path)})

    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "product_id": PRODUCT_ID,
        "atlas_product_class": ATLAS_CLASS,
        "adapter_family": "accreditation_controlled_review",
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": "product.processor.accreditation_controlled_review",
        "executor_id": "accreditation_controlled_review_v1",
        "executor_ref": "products/accreditation/runner.py",
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "processor_receipt_schema": receipt.get("schema"),
        "processor_receipt_internal_state": receipt.get("internal_processing"),
        "human_review_gate": receipt.get("human_review_gate"),
        "external_release_gate": receipt.get("external_release_gate"),
        "regulated_component_state": receipt.get("regulated_component_state"),
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
        },
        "claim_ceiling": (
            "This receipt proves that the HOMS Accreditation atlas composition executed a bounded DIO Accreditation "
            "criterion/evidence review with the EducationAccreditationProof component context. It does not prove an "
            "accreditation decision, institutional attestation, regulator acceptance, signatory approval, external release, "
            "public-launch authority, or commercial validation."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
