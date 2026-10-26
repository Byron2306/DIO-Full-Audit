from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.evidence_profile_execution_proof import _verify_result
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
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile
from products.unpromoted_high_risk_profile import (
    HIGH_RISK_PROFILE_IDS,
    run_high_risk_evidence_review,
    validate_no_engine_boundary,
)


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
PROFILE_ROOT = ROOT / "config" / "products" / "profiles"


def high_risk_profiles_by_product() -> dict[str, str]:
    result: dict[str, str] = {}
    for profile_id in sorted(HIGH_RISK_PROFILE_IDS):
        profile = load_unpromoted_evidence_profile(profile_id)
        product_id = str(profile.get("product_id") or "")
        if not product_id or product_id in result:
            raise ProductClassExecutionProofError(f"invalid high-risk profile product identity: {profile_id}")
        result[product_id] = profile_id
    return result


def controlled_high_risk_fixture(profile_id: str) -> dict[str, Any]:
    if profile_id not in HIGH_RISK_PROFILE_IDS:
        raise ProductClassExecutionProofError(f"unsupported high-risk controlled fixture: {profile_id}")
    return {
        "fixture_kind": "dio.controlled_high_risk_review_fixture.v1",
        "profile_id": profile_id,
        "intake_authority_approved": True,
        "source_authority_scope": "controlled_fixture_only",
        "requirements": [
            {
                "requirement_key": "CTRL-1",
                "statement": f"The selected {profile_id} control requirement has current reviewable evidence.",
                "kind": "control",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
            {
                "requirement_key": "CTRL-2",
                "statement": f"A second {profile_id} control requirement is challenged by bounded conflicting evidence.",
                "kind": "control",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
        ],
        "review_evidence_inputs": [
            {
                "evidence_kind": "controlled_source_record",
                "source_ref": f"{profile_id}://controlled-fixture/support",
                "sha256": "a" * 64,
                "target_requirement_keys": ["CTRL-1"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "controlled_challenge_record",
                "source_ref": f"{profile_id}://controlled-fixture/challenge",
                "sha256": "b" * 64,
                "target_requirement_keys": ["CTRL-2"],
                "relation": "contradicts",
                "severity": "material",
                "hypothesis": "The controlled challenge record conflicts with the selected high-risk criterion.",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
        ],
        "issues": [],
    }


def run_high_risk_execution_proof(
    product_id: str,
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("high-risk review-route proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("intake_authority_approved") is not True:
        raise ProductClassExecutionProofError("high-risk controlled fixture requires approved intake authority")

    profile_id = high_risk_profiles_by_product().get(product_id)
    if profile_id is None:
        raise ProductClassExecutionProofError(f"no high-risk review-route proof adapter for product: {product_id}")
    if fixture.get("profile_id") != profile_id:
        raise ProductClassExecutionProofError(f"high-risk fixture profile mismatch for {profile_id}")

    profile = load_unpromoted_evidence_profile(profile_id)
    boundary = validate_no_engine_boundary(profile_id)
    if boundary.get("engine_assigned") is not False or boundary.get("engine_invoked") is not False:
        raise ProductClassExecutionProofError(f"{profile_id}: no-engine boundary drifted")
    if boundary.get("execution_proof_created") is not False:
        raise ProductClassExecutionProofError(f"{profile_id}: domain execution proof must remain false")

    requirements = fixture.get("requirements")
    evidence_inputs = fixture.get("review_evidence_inputs")
    issues = fixture.get("issues") or []
    if not isinstance(requirements, list) or not isinstance(evidence_inputs, list) or not isinstance(issues, list):
        raise ProductClassExecutionProofError(f"{profile_id}: high-risk controlled fixture is incomplete")

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    source_path = output_dir / "CONTROLLED_SOURCE.json"
    case_source = {
        "source": {
            "fixture_kind": fixture.get("fixture_kind"),
            "profile_id": profile_id,
            "authority_scope": fixture.get("source_authority_scope"),
            "domain_engine_assigned": False,
        },
        "evidence": [],
    }
    _write_json(source_path, case_source)
    case = new_case(
        product=product_id,
        job_id=job_id or f"proof-{profile_id}",
        source=case_source,
        source_path=source_path,
        evidence_inputs=["controlled authorised high-risk requirement", "controlled governed evidence"],
        expected_outputs=["controlled evidence review", "open issue register", "human decision receipt"],
        required_authorities=["fixture_owner", "evidence_reviewer", "authorised_domain_decision_owner"],
        intake_state="approved",
        now=now,
    )
    result = run_high_risk_evidence_review(
        case,
        profile_id=profile_id,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    observed_boundary = result.get("route_boundary") or {}
    if observed_boundary != boundary:
        raise ProductClassExecutionProofError(f"{profile_id}: returned no-engine boundary drifted")
    receipt, artifacts = _verify_result(product_id=product_id, profile=profile, output_dir=output_dir, result=result)
    artifacts.append({"artifact_type": "controlled_source", "filename": source_path.name, "sha256": _sha_file(source_path)})

    profile_path = PROFILE_ROOT / f"{profile_id}.json"
    proof = {
        "schema": PROOF_SCHEMA,
        "product_id": product_id,
        "profile_id": profile_id,
        "atlas_product_class": profile_id.replace("_", " ").title(),
        "adapter_family": "high_risk_controlled_review_no_engine",
        "profile": str(profile_path.relative_to(ROOT)),
        "profile_sha256": "sha256:" + _sha_file(profile_path),
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": f"profile.processor.{profile_id}.evidence_review_only",
        "executor_id": "controlled_evidence_review_v1",
        "executor_ref": "products/evidence_review.py",
        "suggested_engine": None,
        "domain_engine_assigned": False,
        "domain_engine_invoked": False,
        "domain_execution_proved": False,
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "processor_receipt_schema": receipt.get("schema"),
        "processor_receipt_internal_state": receipt.get("internal_processing"),
        "human_review_gate": receipt.get("human_review_gate"),
        "external_release_gate": receipt.get("external_release_gate"),
        "route_boundary": boundary,
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "artifacts": artifacts,
        "claim_ceiling": (
            "This receipt proves only that the bounded shared evidence-review processor executed for this high-risk "
            "profile over the recorded controlled fixture. No domain engine was assigned or invoked and no domain "
            "execution proof was created. It does not prove control effectiveness, compliance, assurance, incident "
            "resolution, remediation approval, risk acceptance, deployment/release approval, external action, "
            "public-launch authority, or external release."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
