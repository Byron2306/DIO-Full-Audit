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
from products.unpromoted_vamp_profile import run_unpromoted_vamp_snapshot_review


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
PROFILE_ROOT = ROOT / "config" / "products" / "profiles"
VAMP_PROFILE_IDS = ("promotionproof", "cpdproof")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def vamp_profiles_by_product() -> dict[str, str]:
    result: dict[str, str] = {}
    for profile_id in VAMP_PROFILE_IDS:
        profile = load_unpromoted_evidence_profile(profile_id)
        product_id = str(profile.get("product_id") or "")
        if not product_id or product_id in result:
            raise ProductClassExecutionProofError(f"invalid VAMP profile identity: {profile_id}")
        result[product_id] = profile_id
    return result


def controlled_vamp_fixture(profile_id: str) -> dict[str, Any]:
    if profile_id not in VAMP_PROFILE_IDS:
        raise ProductClassExecutionProofError(f"unsupported VAMP proof fixture profile: {profile_id}")
    return {
        "fixture_kind": "dio.controlled_vamp_product_class_fixture.v1",
        "profile_id": profile_id,
        "intake_authority_approved": True,
        "selected_objective_ids": ["OBJ-1", "OBJ-2", "OBJ-3"],
        "vamp_snapshot": {
            "schema": "dio.vamp_snapshot.v1",
            "job_id": f"VAMP-{profile_id.upper()}-PROOF-001",
            "quality_gates": [
                {"name": "profile_validated", "passed": True, "detail": "controlled proof fixture"},
                {"name": "source_read_only", "passed": True, "detail": "controlled proof fixture"},
                {"name": "ratings_disabled", "passed": True, "detail": "controlled proof fixture"},
                {"name": "provenance_registered", "passed": True, "detail": "controlled proof fixture"},
                {"name": "human_review_required", "passed": True, "detail": "controlled proof fixture"},
            ],
            "release": {
                "status": "ready_for_human_review",
                "rating_generated": False,
                "employment_decision_generated": False,
            },
            "objectives": [
                {
                    "objective_id": "OBJ-1",
                    "domain_code": "KPA1",
                    "title": "Evidence-backed activity",
                    "period": "2026-01",
                    "minimum_required": 1,
                    "accepted_evidence": 1,
                    "candidate_evidence": 0,
                    "declared_no_evidence": False,
                    "coverage_status": "evidence_backed",
                },
                {
                    "objective_id": "OBJ-2",
                    "domain_code": "KPA3",
                    "title": "Partially evidenced activity",
                    "period": "2026-01",
                    "minimum_required": 2,
                    "accepted_evidence": 1,
                    "candidate_evidence": 1,
                    "declared_no_evidence": False,
                    "coverage_status": "partial",
                },
                {
                    "objective_id": "OBJ-3",
                    "domain_code": "KPA5",
                    "title": "Activity with an unresolved evidence gap",
                    "period": "2026-01",
                    "minimum_required": 1,
                    "accepted_evidence": 0,
                    "candidate_evidence": 1,
                    "declared_no_evidence": False,
                    "coverage_status": "gap",
                },
            ],
        },
    }


def _contract(product_id: str) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    profile_id = vamp_profiles_by_product().get(product_id)
    if profile_id is None:
        raise ProductClassExecutionProofError(f"no VAMP execution-proof adapter for product: {product_id}")
    profile = load_unpromoted_evidence_profile(profile_id)
    routes = _read_json(ROUTES_PATH)
    reconciliation = _read_json(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(profile_id)
    extension = (reconciliation.get("genuine_profile_extensions") or {}).get(profile_id)
    if not isinstance(route, dict) or not isinstance(extension, dict):
        raise ProductClassExecutionProofError(f"{profile_id}: VAMP route/reconciliation contract is missing")
    if route.get("route_kind") != "profile_extension" or route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError(f"{profile_id}: VAMP profile route boundary drifted")
    if route.get("suggested_engine") != "vamp" or extension.get("suggested_engine") != "vamp":
        raise ProductClassExecutionProofError(f"{profile_id}: expected VAMP routing contract")
    if profile.get("source_contract") != "vamp_snapshot_evidence_coverage":
        raise ProductClassExecutionProofError(f"{profile_id}: VAMP source contract drifted")
    return profile_id, profile, route, extension


def run_vamp_profile_execution_proof(
    product_id: str,
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("VAMP profile execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("intake_authority_approved") is not True:
        raise ProductClassExecutionProofError("VAMP controlled fixture requires intake_authority_approved=true")

    profile_id, profile, route, extension = _contract(product_id)
    if fixture.get("profile_id") != profile_id:
        raise ProductClassExecutionProofError(f"VAMP controlled fixture profile mismatch for {profile_id}")
    snapshot = fixture.get("vamp_snapshot")
    selected = fixture.get("selected_objective_ids")
    if not isinstance(snapshot, dict) or not isinstance(selected, list):
        raise ProductClassExecutionProofError("VAMP controlled fixture requires vamp_snapshot and selected_objective_ids")

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    source_path = output_dir / "CONTROLLED_VAMP_SNAPSHOT.json"
    _write_json(source_path, snapshot)
    case = new_case(
        product=product_id,
        job_id=job_id or f"proof-{profile_id}",
        source={"source": {"snapshot": source_path.name}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["governed VAMP evidence-coverage snapshot"],
        expected_outputs=["controlled evidence-readiness pack", "issue register", "human review receipt"],
        required_authorities=["fixture_owner", "evidence_reviewer", "authorised_domain_decision_owner"],
        intake_state="approved",
        now=now,
    )
    result = run_unpromoted_vamp_snapshot_review(
        case,
        profile_id=profile_id,
        vamp_snapshot=snapshot,
        selected_objective_ids=selected,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    receipt, artifacts = _verify_result(product_id=product_id, profile=profile, output_dir=output_dir, result=result)
    binding = result.get("vamp_source_binding") or {}
    if binding.get("source_contract") != "vamp_snapshot_evidence_coverage":
        raise ProductClassExecutionProofError(f"{profile_id}: VAMP source binding is missing")
    if binding.get("selected_objective_ids") != selected:
        raise ProductClassExecutionProofError(f"{profile_id}: VAMP selected objective binding drifted")
    for field in ("rating_generated", "employment_decision_generated", "authority_created", "external_effects", "external_release"):
        if binding.get(field) is not False:
            raise ProductClassExecutionProofError(f"{profile_id}: VAMP binding illegally promotes {field}")
    artifacts.append({"artifact_type": "controlled_vamp_snapshot", "filename": source_path.name, "sha256": _sha_file(source_path)})

    profile_path = PROFILE_ROOT / f"{profile_id}.json"
    proof = {
        "schema": PROOF_SCHEMA,
        "product_id": product_id,
        "profile_id": profile_id,
        "adapter_family": "vamp_snapshot_review",
        "profile": str(profile_path.relative_to(ROOT)),
        "profile_sha256": "sha256:" + _sha_file(profile_path),
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": f"profile.processor.{profile_id}.vamp_snapshot",
        "executor_id": "controlled_evidence_review_v1",
        "executor_ref": "products/unpromoted_vamp_profile.py",
        "suggested_engine": "vamp",
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
        "vamp_source_binding": binding,
        "route_snapshot": {
            "route_kind": route.get("route_kind"),
            "suggested_engine": route.get("suggested_engine"),
            "auto_promotable": route.get("auto_promotable"),
            "reconciliation_suggested_engine": extension.get("suggested_engine"),
        },
        "claim_ceiling": (
            "This receipt proves that the governed VAMP snapshot bridge and bounded evidence-review processor executed "
            "over the recorded controlled fixture. It does not prove a promotion decision, CPD award, competence rating, "
            "employment action, customer source authority, public-launch authority, external effect, or external release."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
