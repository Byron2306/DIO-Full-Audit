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
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile, run_unpromoted_evidence_review
from products.unpromoted_homs_profile import run_unpromoted_homs_curriculum_artifact_review
from products.unpromoted_sophia_profile import run_unpromoted_sophia_artifact_review


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
PROFILE_ROOT = ROOT / "config" / "products" / "profiles"
HOMS_PACK_ROOT = ROOT / "deliverables" / "homs_learning_studio" / "grade_10_physical_sciences_term_3_motion"

PROFILE_ENGINES = {
    "homs_moderate": "homs",
    "homs_curriculum": "homs",
    "sophia_integrity": "sophia",
    "sophia_research": "sophia",
    "sophia_supervisor": "sophia",
    "sophia_tutor": "sophia",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def profiles_by_product() -> dict[str, str]:
    result: dict[str, str] = {}
    for profile_id in PROFILE_ENGINES:
        profile = load_unpromoted_evidence_profile(profile_id)
        product_id = str(profile.get("product_id") or "")
        if not product_id or product_id in result:
            raise ProductClassExecutionProofError(f"invalid HOMS/Sophia product identity: {profile_id}")
        result[product_id] = profile_id
    return result


def _profile_contract(product_id: str) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    profile_id = profiles_by_product().get(product_id)
    if profile_id is None:
        raise ProductClassExecutionProofError(f"no HOMS/Sophia execution-proof adapter for product: {product_id}")
    profile = load_unpromoted_evidence_profile(profile_id)
    routes = _read_json(ROUTES_PATH)
    reconciliation = _read_json(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(profile_id)
    extension = (reconciliation.get("genuine_profile_extensions") or {}).get(profile_id)
    if not isinstance(route, dict) or not isinstance(extension, dict):
        raise ProductClassExecutionProofError(f"{profile_id}: route/reconciliation contract is missing")
    if route.get("route_kind") != "profile_extension" or route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError(f"{profile_id}: route boundary drifted")
    expected_engine = PROFILE_ENGINES[profile_id]
    if route.get("suggested_engine") != expected_engine or extension.get("suggested_engine") != expected_engine:
        raise ProductClassExecutionProofError(f"{profile_id}: expected {expected_engine} routing contract")
    for field in ("authority_created", "external_effects", "external_release"):
        if profile.get(field) is not False:
            raise ProductClassExecutionProofError(f"{profile_id}: profile illegally promotes {field}")
    return profile_id, profile, route, extension


def _generic_fixture(profile_id: str) -> dict[str, Any]:
    return {
        "fixture_kind": "dio.controlled_product_class_fixture.v1",
        "profile_id": profile_id,
        "intake_authority_approved": True,
        "source_authority_scope": "controlled_fixture_only",
        "requirements": [
            {
                "requirement_key": "REQ-1",
                "statement": f"The selected {profile_id} criterion is supported by current controlled review evidence.",
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


def _homs_curriculum_fixture() -> dict[str, Any]:
    return {
        "fixture_kind": "dio.controlled_homs_learning_pack_fixture.v1",
        "profile_id": "homs_curriculum",
        "intake_authority_approved": True,
        "source_authority_scope": "canonical_controlled_homs_learning_pack",
        "manifest": _read_json(HOMS_PACK_ROOT / "LEARNING_PACK_MANIFEST.json"),
        "validation": _read_json(HOMS_PACK_ROOT / "HOMS_LEARNING_PACK_VALIDATION.json"),
        "build_receipt": _read_json(HOMS_PACK_ROOT / "HOMS_LEARNING_PACK_BUILD_RECEIPT.json"),
        "selected_document_paths": [
            "documents/HOMS_G10_T3_MOTION_LEARNER_GUIDE.docx",
            "documents/HOMS_G10_T3_MOTION_MINI_ASSESSMENT.docx",
        ],
    }


def _sophia_receipt_fixture(profile_id: str) -> dict[str, Any]:
    return {
        "fixture_kind": "dio.controlled_sophia_review_receipt_fixture.v1",
        "profile_id": profile_id,
        "intake_authority_approved": True,
        "source_authority_scope": "controlled_fixture_only",
        "sophia_receipt": {
            "schema": "dio.sophia_review_receipt.v1",
            "job_id": f"SOPHIA-PROOF-{profile_id.upper()}",
            "status": "needs_human_review",
            "source": {
                "name": "controlled-fixture.md",
                "sha256": "1" * 64,
                "parser": "plain_text",
                "word_count": 1200,
                "full_text_copied_to_pack": False,
            },
            "metrics": {
                "literature_queries": 2,
                "candidate_sources": 5,
                "claims_reviewed": 4,
                "reference_entries": 7,
                "reference_findings": 1,
                "reviewer_commentary_status": "completed",
                "reviewer_provider": "controlled_fixture",
                "reviewer_model": "controlled_fixture",
                "reviewer_grounding_passed": True,
            },
            "remote_processing": {
                "gemini_review_approved": True,
                "performed": True,
                "characters_transmitted": 4200,
            },
            "outputs": [
                {"name": "CLAIM_SOURCE_LEDGER.json", "sha256": "2" * 64},
                {"name": "REFERENCE_AUDIT.json", "sha256": "3" * 64},
                {"name": "REVIEWER_COMMENTARY.json", "sha256": "4" * 64},
                {"name": "HUMAN_APPROVAL.md", "sha256": "5" * 64},
            ],
            "delivery_released": False,
        },
        "selected_output_names": ["CLAIM_SOURCE_LEDGER.json", "REFERENCE_AUDIT.json"],
    }


def controlled_education_research_fixture(profile_id: str) -> dict[str, Any]:
    if profile_id == "homs_curriculum":
        return _homs_curriculum_fixture()
    if profile_id in {"sophia_integrity", "sophia_research"}:
        return _sophia_receipt_fixture(profile_id)
    if profile_id in {"homs_moderate", "sophia_supervisor", "sophia_tutor"}:
        return _generic_fixture(profile_id)
    raise ProductClassExecutionProofError(f"unsupported HOMS/Sophia controlled fixture: {profile_id}")


def _new_controlled_case(
    *,
    product_id: str,
    profile_id: str,
    fixture: dict[str, Any],
    output_dir: Path,
    now: str,
    job_id: str | None,
) -> tuple[dict[str, Any], Path]:
    source_path = output_dir / "CONTROLLED_SOURCE.json"
    case_source = {
        "source": {
            "fixture_kind": fixture.get("fixture_kind"),
            "profile_id": profile_id,
            "authority_scope": fixture.get("source_authority_scope"),
        },
        "evidence": [],
    }
    _write_json(source_path, case_source)
    case = new_case(
        product=product_id,
        job_id=job_id or f"proof-{profile_id}",
        source=case_source,
        source_path=source_path,
        evidence_inputs=["controlled bounded source/evidence receipt"],
        expected_outputs=["controlled review pack", "proof manifest", "processing receipt"],
        required_authorities=["fixture_owner", "domain_reviewer", "authorised_domain_decision_owner"],
        intake_state="approved",
        now=now,
    )
    return case, source_path


def run_education_research_execution_proof(
    product_id: str,
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("HOMS/Sophia execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("intake_authority_approved") is not True:
        raise ProductClassExecutionProofError("HOMS/Sophia controlled fixture requires approved intake authority")

    profile_id, profile, route, _ = _profile_contract(product_id)
    if fixture.get("profile_id") != profile_id:
        raise ProductClassExecutionProofError(f"controlled fixture profile mismatch for {profile_id}")

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    case, source_path = _new_controlled_case(
        product_id=product_id,
        profile_id=profile_id,
        fixture=fixture,
        output_dir=output_dir,
        now=now,
        job_id=job_id,
    )

    source_binding: dict[str, Any] | None = None
    if profile_id == "homs_curriculum":
        result = run_unpromoted_homs_curriculum_artifact_review(
            case,
            manifest=fixture.get("manifest") or {},
            validation=fixture.get("validation") or {},
            build_receipt=fixture.get("build_receipt") or {},
            selected_document_paths=list(fixture.get("selected_document_paths") or []),
            output_dir=output_dir,
            operator_id=operator_id,
            now=now,
        )
        source_binding = result.get("homs_source_binding") or {}
        if source_binding.get("upstream_learning_pack_generation_proved") is not True or source_binding.get("upstream_learning_pack_validation_proved") is not True:
            raise ProductClassExecutionProofError("HOMS Curriculum upstream pack generation/validation binding was not proved")
        for field in ("curriculum_correctness_proved", "curriculum_approval_created", "programme_quality_certification_created", "execution_proof_created", "authority_created", "external_effects", "external_release"):
            if source_binding.get(field) is not False:
                raise ProductClassExecutionProofError(f"HOMS Curriculum source bridge illegally promotes {field}")
    elif profile_id in {"sophia_integrity", "sophia_research"}:
        result = run_unpromoted_sophia_artifact_review(
            case,
            profile_id=profile_id,
            sophia_receipt=fixture.get("sophia_receipt") or {},
            selected_output_names=list(fixture.get("selected_output_names") or []),
            output_dir=output_dir,
            operator_id=operator_id,
            now=now,
        )
        source_binding = result.get("sophia_source_binding") or {}
        for field in ("substantive_conclusion_proved", "execution_proof_created", "authority_created", "external_effects", "external_release"):
            if source_binding.get(field) is not False:
                raise ProductClassExecutionProofError(f"{profile_id}: Sophia source bridge illegally promotes {field}")
    else:
        requirements = fixture.get("requirements")
        review_evidence = fixture.get("review_evidence_inputs")
        issues = fixture.get("issues") or []
        if not isinstance(requirements, list) or not isinstance(review_evidence, list) or not isinstance(issues, list):
            raise ProductClassExecutionProofError(f"{profile_id}: controlled review fixture is incomplete")
        result = run_unpromoted_evidence_review(
            case,
            profile_id=profile_id,
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
        "atlas_product_class": profile_id.replace("_", " ").title(),
        "adapter_family": "homs_sophia_controlled_review",
        "profile": str(profile_path.relative_to(ROOT)),
        "profile_sha256": "sha256:" + _sha_file(profile_path),
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": fixture.get("source_authority_scope"),
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": f"profile.processor.{profile_id}.review",
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
        "source_binding": source_binding,
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "artifacts": artifacts,
        "claim_ceiling": (
            "This receipt proves that the bounded HOMS/Sophia review route executed over the recorded controlled source "
            "or governed upstream receipt and produced hash-verified review artifacts. It does not prove curriculum "
            "correctness, moderation or academic-integrity conclusions, supervision/progression decisions, scientific "
            "truth, customer source authority, external action, public-launch authority, or external release."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
