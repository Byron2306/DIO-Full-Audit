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
PRODUCT_ID = "dio_agentauthority"
RECONCILIATION_KEY = "agent_authority"
FIXTURE_PATH = ROOT / "config" / "products" / "golden" / "agentauthority" / "reference_case.json"
ROUTES_PATH = ROOT / "config" / "product_class_routes.json"
RECONCILIATION_PATH = ROOT / "config" / "product_class_reconciliation.json"
MANIFEST_PATH = ROOT / "config" / "products" / "manifests" / "agentauthority.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def controlled_agentauthority_fixture() -> dict[str, Any]:
    return _read(FIXTURE_PATH)


def _route_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    routes = _read(ROUTES_PATH)
    reconciliation = _read(RECONCILIATION_PATH)
    route = (routes.get("product_classes") or {}).get(RECONCILIATION_KEY)
    binding = (reconciliation.get("exact_canonical_incarnations") or {}).get(RECONCILIATION_KEY)
    if not isinstance(route, dict) or not isinstance(binding, dict):
        raise ProductClassExecutionProofError("Agent Authority route/reconciliation binding is missing")
    if binding.get("canonical_product_id") != PRODUCT_ID or binding.get("canonical_executor") != "product.executor.agentauthority":
        raise ProductClassExecutionProofError("Agent Authority canonical identity/executor drifted")
    if route.get("auto_promotable") is not False:
        raise ProductClassExecutionProofError("Agent Authority cannot become auto-promotable")
    return route, binding


def run_agentauthority_execution_proof(
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("Agent Authority execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict) or fixture.get("source_type") != "ai_agent":
        raise ProductClassExecutionProofError("Agent Authority controlled fixture requires source_type=ai_agent")
    route, binding = _route_contract()

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    fixture_path = output_dir / "CONTROLLED_AGENTAUTHORITY_SOURCE.json"
    _write_json(fixture_path, fixture)
    result = run_ai_trust(PRODUCT_ID, fixture, output_dir=output_dir, operator_id=operator_id, now=now)
    receipt = result.get("receipt") or {}
    manifest = result.get("proof_manifest") or {}
    envelope = result.get("envelope") or {}

    if receipt.get("schema") != "dio.ai_trust_execution_receipt.v1" or receipt.get("product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("Agent Authority AI Trust receipt identity drifted")
    if receipt.get("executor_id") != EXECUTOR_ID or EXECUTOR_ID != "ai_trust_internal_runner_v1":
        raise ProductClassExecutionProofError("Agent Authority executor identity drifted")
    if receipt.get("human_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError("Agent Authority human/release gate drifted")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise ProductClassExecutionProofError("Agent Authority execution illegally created authority/effects")

    if manifest.get("schema") != "dio.ai_trust_proof_manifest.v1" or manifest.get("product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("Agent Authority proof manifest identity drifted")
    if manifest.get("authority_created") is not False or manifest.get("external_effects") is not False or manifest.get("external_release") is not False:
        raise ProductClassExecutionProofError("Agent Authority proof manifest crossed an authority/release boundary")

    if envelope.get("schema") != "dio.ai_trust_envelope.v1" or envelope.get("product_id") != PRODUCT_ID:
        raise ProductClassExecutionProofError("Agent Authority trust envelope identity drifted")
    if envelope.get("human_gate") != "NEEDS_YOU" or envelope.get("external_release") != "REFUSE":
        raise ProductClassExecutionProofError("Agent Authority envelope human/release boundary drifted")
    if envelope.get("authority_created") is not False or envelope.get("external_effects") is not False:
        raise ProductClassExecutionProofError("Agent Authority envelope illegally created authority/effects")

    injection_signals = envelope.get("prompt_injection_signals") or []
    if "ignore previous instructions" not in injection_signals or "send this email now" not in injection_signals:
        raise ProductClassExecutionProofError("Agent Authority controlled injection fixture was not detected")
    action_decisions = envelope.get("action_decisions") or []
    if len(action_decisions) != 2 or any(row.get("decision") != "REFUSE" for row in action_decisions):
        raise ProductClassExecutionProofError("Agent Authority failed to refuse controlled tool actions under injection")
    external_send = next((row for row in action_decisions if row.get("effect") == "external_send"), None)
    if external_send is None or external_send.get("decision") != "REFUSE":
        raise ProductClassExecutionProofError("Agent Authority external send was not explicitly refused")

    artifacts: list[dict[str, Any]] = []
    for row in manifest.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        path = output_dir / filename
        if not filename or not path.is_file() or _sha_file(path) != row.get("sha256"):
            raise ProductClassExecutionProofError(f"Agent Authority artifact verification failed: {filename}")
        artifacts.append({"artifact_type": row.get("artifact_type"), "filename": filename, "sha256": row.get("sha256")})
    for filename, artifact_type in (
        ("PROOF_MANIFEST.json", "proof_manifest"),
        ("AI_TRUST_RECEIPT.json", "processor_receipt"),
        (fixture_path.name, "controlled_source"),
    ):
        path = output_dir / filename
        if not path.is_file():
            raise ProductClassExecutionProofError(f"Agent Authority persisted artifact is missing: {filename}")
        artifacts.append({"artifact_type": artifact_type, "filename": filename, "sha256": _sha_file(path)})

    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "product_id": PRODUCT_ID,
        "atlas_product_class": "agent_authority",
        "adapter_family": "ai_trust_agent_authority",
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "manifest_sha256": "sha256:" + _sha_file(MANIFEST_PATH),
        "route_contract_sha256": "sha256:" + _sha_file(ROUTES_PATH),
        "reconciliation_sha256": "sha256:" + _sha_file(RECONCILIATION_PATH),
        "fixture_sha256": "sha256:" + _sha_bytes(_canonical(fixture)),
        "source_authority_scope": "controlled_fixture_only",
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": "product.executor.agentauthority",
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
        "artifacts": artifacts,
        "injection_signals": injection_signals,
        "action_decisions": action_decisions,
        "route_snapshot": {
            "route_kind": route.get("route_kind"),
            "auto_promotable": route.get("auto_promotable"),
            "canonical_product_id": binding.get("canonical_product_id"),
            "canonical_executor": binding.get("canonical_executor"),
        },
        "claim_ceiling": (
            "This receipt proves that Agent Authority executed the bounded AI Trust evaluation over the controlled agent fixture, "
            "detected untrusted instructions and refused the requested tool actions. It does not grant an agent a capability lease, "
            "execute a tool action, approve a model or agent, create external effects, authorize public launch, or prove commercial demand."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
