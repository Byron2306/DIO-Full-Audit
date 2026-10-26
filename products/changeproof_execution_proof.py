from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.ai_trust.runner import EXECUTOR_ID, run_ai_trust
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
PRODUCT_ID = "dio_modelchangeproof"
ATLAS_PRODUCT_CLASS = "changeproof"
FIXTURE_PATH = ROOT / "config" / "products" / "golden" / "modelchangeproof" / "reference_case.json"
MANIFEST_PATH = ROOT / "config" / "products" / "manifests" / "modelchangeproof.json"
FRAMEWORK_PATH = ROOT / "config" / "profiles" / "frameworks" / "model_change_assurance.json"
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
DECISION_PATH = ROOT / "config" / "product_class_equivalence_decisions" / "changeproof.json"
EXPECTED_INCLUDES = {
    "baseline_identity",
    "current_identity",
    "model_change",
    "prompt_change",
    "policy_change",
    "connector_change",
    "environment_change",
    "reevaluation",
}
EXPECTED_EXCLUDES = {
    "generic_enterprise_change_management",
    "residual_risk_acceptance",
    "automatic_promotion",
    "public_launch_authority",
    "external_release_authority",
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def controlled_changeproof_fixture() -> dict[str, Any]:
    return _read(FIXTURE_PATH)


def _equivalence_contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    routes = _read(ROUTES_PATH)
    reconciliation = _read(RECONCILIATION_PATH)
    decision = _read(DECISION_PATH)
    route = (routes.get("product_classes") or {}).get(ATLAS_PRODUCT_CLASS)
    candidate = (reconciliation.get("equivalence_candidates") or {}).get(ATLAS_PRODUCT_CLASS)
    if not isinstance(route, dict) or not isinstance(candidate, dict):
        raise ProductClassExecutionProofError("ChangeProof candidate route/reconciliation contract is missing")
    if route.get("route_kind") != "profile_extension" or route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError("ChangeProof route must remain non-auto-promotable")
    if candidate.get("candidate_product_id") != PRODUCT_ID or candidate.get("candidate_manifest") != str(MANIFEST_PATH.relative_to(ROOT)):
        raise ProductClassExecutionProofError("ChangeProof reconciliation candidate identity drifted")
    if candidate.get("state") != "equivalence_review_required":
        raise ProductClassExecutionProofError("ChangeProof source reconciliation history drifted")
    if decision.get("schema") != "dio.product_class_equivalence_decision.v1":
        raise ProductClassExecutionProofError("ChangeProof operator equivalence decision is missing or unsupported")
    if decision.get("atlas_product_class") != ATLAS_PRODUCT_CLASS or decision.get("candidate_product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("ChangeProof operator decision identity mismatch")
    if decision.get("candidate_manifest") != str(MANIFEST_PATH.relative_to(ROOT)):
        raise ProductClassExecutionProofError("ChangeProof operator decision manifest mismatch")
    if decision.get("source_reconciliation_state") != "equivalence_review_required" or decision.get("decision") != "scope_equivalent":
        raise ProductClassExecutionProofError("ChangeProof operator did not approve bounded scope equivalence")
    scope = decision.get("approved_scope") or {}
    if scope.get("kind") != "bounded_ai_model_system_change_assurance":
        raise ProductClassExecutionProofError("ChangeProof approved scope kind drifted")
    if set(scope.get("includes") or []) != EXPECTED_INCLUDES or set(scope.get("excludes") or []) != EXPECTED_EXCLUDES:
        raise ProductClassExecutionProofError("ChangeProof approved scope boundaries drifted")
    for field in ("auto_promotable", "authority_created", "public_launch_authorized", "external_release_authorized"):
        if decision.get(field) is not False:
            raise ProductClassExecutionProofError(f"ChangeProof operator decision illegally promotes {field}")
    return route, candidate, decision


def run_changeproof_execution_proof(
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("ChangeProof execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("source_type") != "ai_model_change":
        raise ProductClassExecutionProofError("ChangeProof controlled fixture requires source_type=ai_model_change")
    route, candidate, decision = _equivalence_contract()

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    fixture_path = output_dir / "CONTROLLED_CHANGEPROOF_SOURCE.json"
    _write_json(fixture_path, fixture)
    result = run_ai_trust(PRODUCT_ID, fixture, output_dir=output_dir, operator_id=operator_id, now=now)
    receipt = result.get("receipt") or {}
    manifest = result.get("proof_manifest") or {}
    envelope = result.get("envelope") or {}

    if receipt.get("schema") != "dio.ai_trust_execution_receipt.v1" or receipt.get("product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("ChangeProof ModelChangeProof receipt identity drifted")
    if receipt.get("executor_id") != EXECUTOR_ID or EXECUTOR_ID != "ai_trust_internal_runner_v1":
        raise ProductClassExecutionProofError("ChangeProof executor identity drifted")
    if receipt.get("human_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError("ChangeProof human/release gate drifted")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise ProductClassExecutionProofError("ChangeProof execution illegally created authority/effects")

    if manifest.get("schema") != "dio.ai_trust_proof_manifest.v1" or manifest.get("product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("ChangeProof proof manifest identity drifted")
    if manifest.get("authority_created") is not False or manifest.get("external_effects") is not False or manifest.get("external_release") is not False:
        raise ProductClassExecutionProofError("ChangeProof proof manifest crossed an authority/release boundary")

    if envelope.get("schema") != "dio.ai_trust_envelope.v1" or envelope.get("product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("ChangeProof trust envelope identity drifted")
    if envelope.get("human_gate") != "NEEDS_YOU" or envelope.get("external_release") != "REFUSE":
        raise ProductClassExecutionProofError("ChangeProof envelope human/release boundary drifted")
    if envelope.get("authority_created") is not False or envelope.get("external_effects") is not False:
        raise ProductClassExecutionProofError("ChangeProof envelope illegally created authority/effects")

    drift_fields = {str(row.get("field")) for row in envelope.get("drift_events") or []}
    if not {"model_fingerprint", "prompt_fingerprint"}.issubset(drift_fields):
        raise ProductClassExecutionProofError("ChangeProof controlled fixture did not expose expected model/prompt drift")
    dimensions = {row.get("dimension"): row.get("state") for row in envelope.get("dimensions") or []}
    if dimensions.get("drift") != "CONTESTED" or dimensions.get("evaluation") != "STALE" or dimensions.get("integrity") != "CONTESTED":
        raise ProductClassExecutionProofError("ChangeProof expected drift/evaluation/integrity challenge states were not preserved")

    artifacts: list[dict[str, Any]] = []
    for row in manifest.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        path = output_dir / filename
        if not filename or not path.is_file() or _sha_file(path) != row.get("sha256"):
            raise ProductClassExecutionProofError(f"ChangeProof artifact verification failed: {filename}")
        artifacts.append({"artifact_type": row.get("artifact_type"), "filename": filename, "sha256": row.get("sha256")})
    for filename, artifact_type in (
        ("PROOF_MANIFEST.json", "proof_manifest"),
        ("AI_TRUST_RECEIPT.json", "processor_receipt"),
        (fixture_path.name, "controlled_source"),
    ):
        path = output_dir / filename
        if not path.is_file():
            raise ProductClassExecutionProofError(f"ChangeProof persisted artifact is missing: {filename}")
        artifacts.append({"artifact_type": artifact_type, "filename": filename, "sha256": _sha_file(path)})

    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "product_id": PRODUCT_ID,
        "atlas_product_class": ATLAS_PRODUCT_CLASS,
        "adapter_family": "ai_trust_changeproof_scope_equivalence",
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "manifest_sha256": "sha256:" + _sha_file(MANIFEST_PATH),
        "framework": str(FRAMEWORK_PATH.relative_to(ROOT)),
        "framework_sha256": "sha256:" + _sha_file(FRAMEWORK_PATH),
        "equivalence_decision": str(DECISION_PATH.relative_to(ROOT)),
        "equivalence_decision_sha256": "sha256:" + _sha_file(DECISION_PATH),
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": "product.executor.modelchangeproof",
        "executor_id": EXECUTOR_ID,
        "executor_ref": "products/ai_trust/runner.py",
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "processor_receipt_schema": receipt.get("schema"),
        "processor_receipt_internal_state": "COMPLETE",
        "human_review_gate": receipt.get("human_gate"),
        "external_release_gate": receipt.get("external_release_gate"),
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "drift_fields": sorted(drift_fields),
        "challenge_states": {
            "drift": dimensions.get("drift"),
            "evaluation": dimensions.get("evaluation"),
            "integrity": dimensions.get("integrity"),
        },
        "artifacts": artifacts,
        "route_snapshot": {
            "route_kind": route.get("route_kind"),
            "auto_promotable": route.get("auto_promotable"),
            "candidate_reconciliation_state": candidate.get("state"),
            "operator_decision": decision.get("decision"),
            "approved_scope_kind": (decision.get("approved_scope") or {}).get("kind"),
            "candidate_product_id": candidate.get("candidate_product_id"),
        },
        "claim_ceiling": (
            "This receipt proves the operator-approved ChangeProof scope as bounded AI/model-system change assurance using the "
            "existing ModelChangeProof processor over the recorded controlled fixture. It proves comparison of baseline/current "
            "identity and bounded model, prompt, policy, connector and environment change evidence plus reevaluation state. It "
            "does not extend to generic enterprise change management, accept residual risk, authorize promotion, approve a model, "
            "create external effects, authorize public launch, or grant external release."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
