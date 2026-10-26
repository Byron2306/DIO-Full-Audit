from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from products.assuranceroom.runner import run_controlled_assuranceroom_review
from products.auditproof.runner import run_controlled_auditproof_review
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
from products.unpromoted_evidence_profile import (
    load_unpromoted_evidence_profile,
    run_unpromoted_evidence_review,
)
from products.vendorproof.runner import run_controlled_vendorproof_review


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
PROFILE_ROOT = ROOT / "config" / "products" / "profiles"

EVIDENCE_PROFILE_IDS = (
    "vendorproof",
    "auditproof",
    "assuranceroom",
    "impactproof",
    "projectproof",
    "certificationproof",
    "diligenceroom",
    "donorproof",
    "programmeproof",
    "qualityproof",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _profiles_by_product() -> dict[str, str]:
    result: dict[str, str] = {}
    for profile_id in EVIDENCE_PROFILE_IDS:
        profile = _read_json(PROFILE_ROOT / f"{profile_id}.json")
        product_id = str(profile.get("product_id") or "")
        if not product_id or product_id in result:
            raise ProductClassExecutionProofError(f"invalid evidence-profile product identity: {profile_id}")
        result[product_id] = profile_id
    return result


def _profile_contract(product_id: str) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    product_map = _profiles_by_product()
    profile_id = product_map.get(product_id)
    if profile_id is None:
        raise ProductClassExecutionProofError(f"no evidence-profile execution-proof adapter for product: {product_id}")

    profile = _read_json(PROFILE_ROOT / f"{profile_id}.json")
    routes = _read_json(ROUTES_PATH)
    reconciliation = _read_json(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(profile_id)
    extension = (reconciliation.get("genuine_profile_extensions") or {}).get(profile_id)
    if not isinstance(route, dict) or not isinstance(extension, dict):
        raise ProductClassExecutionProofError(f"{profile_id}: route/reconciliation contract is missing")
    if route.get("route_kind") != "profile_extension":
        raise ProductClassExecutionProofError(f"{profile_id}: evidence profile must remain a profile_extension route")
    if route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError(f"{profile_id}: evidence profile cannot become auto-promotable")
    if route.get("suggested_engine") != "evidex" or extension.get("suggested_engine") != "evidex":
        raise ProductClassExecutionProofError(f"{profile_id}: expected Evidex evidence-review routing contract")
    for field in ("authority_created", "external_effects", "external_release"):
        if profile.get(field) is not False:
            raise ProductClassExecutionProofError(f"{profile_id}: profile illegally promotes {field}")
    return profile_id, profile, route, extension


def controlled_evidence_fixture(profile_id: str) -> dict[str, Any]:
    if profile_id not in EVIDENCE_PROFILE_IDS:
        raise ProductClassExecutionProofError(f"unsupported controlled evidence fixture profile: {profile_id}")
    return {
        "fixture_kind": "dio.controlled_product_class_fixture.v1",
        "profile_id": profile_id,
        "intake_authority_approved": True,
        "case_source": {
            "source": {
                "fixture_kind": "controlled_non_customer_source",
                "profile_id": profile_id,
                "authority_scope": "controlled_fixture_only",
            },
            "evidence": [],
        },
        "requirements": [
            {
                "requirement_key": "REQ-1",
                "statement": f"The selected {profile_id} criterion is supported by current reviewable evidence.",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
            {
                "requirement_key": "REQ-2",
                "statement": f"A second {profile_id} criterion is tested against conflicting controlled evidence.",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
        ],
        "review_evidence_inputs": [
            {
                "evidence_kind": "controlled_source_record",
                "source_ref": f"{profile_id}://controlled-fixture/support",
                "sha256": "a" * 64,
                "target_requirement_keys": ["REQ-1"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "controlled_challenge_record",
                "source_ref": f"{profile_id}://controlled-fixture/challenge",
                "sha256": "b" * 64,
                "target_requirement_keys": ["REQ-2"],
                "relation": "contradicts",
                "severity": "material",
                "hypothesis": "The controlled challenge record conflicts with the selected criterion.",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
        ],
        "issues": [],
    }


def _run_profile_review(
    profile_id: str,
    case: dict[str, Any],
    *,
    requirements: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    specialised: dict[str, Callable[..., dict[str, Any]]] = {
        "vendorproof": run_controlled_vendorproof_review,
        "auditproof": run_controlled_auditproof_review,
        "assuranceroom": run_controlled_assuranceroom_review,
    }
    runner = specialised.get(profile_id)
    if runner is not None:
        return runner(
            case,
            requirements=requirements,
            evidence_inputs=evidence_inputs,
            issues=issues,
            output_dir=output_dir,
            operator_id=operator_id,
            now=now,
        )
    load_unpromoted_evidence_profile(profile_id)
    return run_unpromoted_evidence_review(
        case,
        profile_id=profile_id,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )


def _verify_result(
    *,
    product_id: str,
    profile: dict[str, Any],
    output_dir: Path,
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = result.get("receipt") or {}
    proof_manifest = result.get("proof_manifest") or {}
    profile_id = str(profile["profile_id"])
    prefix = str(profile.get("artifact_prefix") or profile_id).upper().replace("-", "_")

    if receipt.get("schema") != "dio.evidence_review.controlled_processing_receipt.v1":
        raise ProductClassExecutionProofError(f"{profile_id}: unexpected controlled-processing receipt schema")
    if receipt.get("processor_id") != "controlled_evidence_review_v1":
        raise ProductClassExecutionProofError(f"{profile_id}: controlled processor identity mismatch")
    if receipt.get("product_id") != product_id or receipt.get("profile_id") != profile_id:
        raise ProductClassExecutionProofError(f"{profile_id}: controlled processor identity drifted")
    if receipt.get("internal_processing") != "COMPLETE":
        raise ProductClassExecutionProofError(f"{profile_id}: controlled evidence processor did not complete")
    if receipt.get("generic_executor_gate") != "refuse":
        raise ProductClassExecutionProofError(f"{profile_id}: generic executor boundary drifted")
    if receipt.get("human_review_gate") != "NEEDS_YOU":
        raise ProductClassExecutionProofError(f"{profile_id}: human review gate drifted")
    if receipt.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError(f"{profile_id}: external release gate drifted")
    for field in ("domain_decision_created", "domain_score_created", "execution_performed", "authority_created", "external_effects", "external_release"):
        if receipt.get(field) is not False:
            raise ProductClassExecutionProofError(f"{profile_id}: controlled review illegally promotes {field}")
    if any((receipt.get("forbidden_outcomes_created") or {}).values()):
        raise ProductClassExecutionProofError(f"{profile_id}: forbidden product outcome was created")

    if proof_manifest.get("schema") != "dio.evidence_review.controlled_proof_manifest.v1":
        raise ProductClassExecutionProofError(f"{profile_id}: unexpected controlled proof manifest schema")
    if proof_manifest.get("provider_id") != "controlled_evidence_review_v1":
        raise ProductClassExecutionProofError(f"{profile_id}: controlled proof provider mismatch")
    if proof_manifest.get("product_id") != product_id or proof_manifest.get("profile_id") != profile_id:
        raise ProductClassExecutionProofError(f"{profile_id}: controlled proof identity drifted")
    for field in ("execution_performed", "authority_created", "external_effects", "external_release"):
        if proof_manifest.get(field) is not False:
            raise ProductClassExecutionProofError(f"{profile_id}: proof manifest illegally promotes {field}")

    receipt_path = output_dir / f"{prefix}_PROCESSING_RECEIPT.json"
    proof_path = output_dir / "PROOF_MANIFEST.json"
    if not receipt_path.is_file() or not proof_path.is_file():
        raise ProductClassExecutionProofError(f"{profile_id}: persisted controlled review receipt/proof is missing")
    if _read_json(receipt_path) != receipt or _read_json(proof_path) != proof_manifest:
        raise ProductClassExecutionProofError(f"{profile_id}: persisted controlled review receipt/proof drifted")

    artifacts: list[dict[str, Any]] = []
    for row in proof_manifest.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        path = output_dir / filename
        if not filename or not path.is_file():
            raise ProductClassExecutionProofError(f"{profile_id}: declared review artifact is missing: {filename}")
        observed = _sha_file(path)
        if observed != row.get("sha256"):
            raise ProductClassExecutionProofError(f"{profile_id}: review artifact hash mismatch: {filename}")
        artifacts.append({"artifact_type": row.get("artifact_type"), "filename": filename, "sha256": observed})
    artifacts.extend(
        [
            {"artifact_type": "processor_receipt", "filename": receipt_path.name, "sha256": _sha_file(receipt_path)},
            {"artifact_type": "proof_manifest", "filename": proof_path.name, "sha256": _sha_file(proof_path)},
        ]
    )
    return receipt, artifacts


def run_evidence_profile_execution_proof(
    product_id: str,
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("evidence-profile execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict):
        raise ProductClassExecutionProofError("evidence-profile fixture must be a JSON object")
    if fixture.get("intake_authority_approved") is not True:
        raise ProductClassExecutionProofError("controlled evidence fixture requires explicit intake_authority_approved=true")

    profile_id, profile, route, extension = _profile_contract(product_id)
    fixture_profile = str(fixture.get("profile_id") or "")
    if fixture_profile != profile_id:
        raise ProductClassExecutionProofError(
            f"controlled fixture profile mismatch: expected {profile_id}, found {fixture_profile or '<empty>'}"
        )
    requirements = fixture.get("requirements")
    review_evidence = fixture.get("review_evidence_inputs")
    issues = fixture.get("issues") or []
    case_source = fixture.get("case_source")
    if not isinstance(requirements, list) or not isinstance(review_evidence, list) or not isinstance(issues, list) or not isinstance(case_source, dict):
        raise ProductClassExecutionProofError("controlled evidence fixture requires case_source, requirements, review_evidence_inputs and issues")

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    source_path = output_dir / "CONTROLLED_SOURCE.json"
    _write_json(source_path, case_source)
    case = new_case(
        product=product_id,
        job_id=job_id or f"proof-{profile_id}",
        source=case_source,
        source_path=source_path,
        evidence_inputs=["controlled authorised criteria", "controlled supporting evidence"],
        expected_outputs=["requirement-evidence matrix", "issue register", "open-question list", "controlled review pack"],
        required_authorities=["fixture_owner", "evidence_reviewer", "authorised_domain_decision_owner"],
        intake_state="approved",
        now=now,
    )
    result = _run_profile_review(
        profile_id,
        case,
        requirements=requirements,
        evidence_inputs=review_evidence,
        issues=issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    receipt, artifacts = _verify_result(product_id=product_id, profile=profile, output_dir=output_dir, result=result)
    artifacts.append({"artifact_type": "controlled_source", "filename": source_path.name, "sha256": _sha_file(source_path)})

    profile_path = PROFILE_ROOT / f"{profile_id}.json"
    proof = {
        "schema": PROOF_SCHEMA,
        "product_id": product_id,
        "profile_id": profile_id,
        "adapter_family": "controlled_evidence_review",
        "profile": str(profile_path.relative_to(ROOT)),
        "profile_sha256": "sha256:" + _sha_file(profile_path),
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": f"profile.processor.{profile_id}",
        "executor_id": "controlled_evidence_review_v1",
        "executor_ref": "products/evidence_review.py",
        "suggested_engine": route.get("suggested_engine"),
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "processor_receipt_schema": receipt.get("schema"),
        "processor_receipt_internal_state": receipt.get("internal_processing"),
        "human_review_gate": receipt.get("human_review_gate"),
        "external_release_gate": receipt.get("external_release_gate"),
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "artifacts": artifacts,
        "claim_ceiling": (
            "This receipt proves that the bounded controlled evidence-review processor executed over the recorded "
            "non-customer fixture and produced the hash-verified review artifacts listed here. It does not prove the "
            "substantive domain conclusion, human decision, customer source authority, external action, customer "
            "validation, public-launch authority, or external release."
        ),
        "route_snapshot": {
            "route_kind": route.get("route_kind"),
            "suggested_engine": route.get("suggested_engine"),
            "auto_promotable": route.get("auto_promotable"),
            "reconciliation_suggested_engine": extension.get("suggested_engine"),
        },
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
