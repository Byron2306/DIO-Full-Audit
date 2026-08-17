from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.compiler import compile_manifest
from products.obligationfamily.runner import (
    EXECUTOR_ID as OBLIGATION_EXECUTOR_ID,
    FAMILY_DEFINITIONS,
    run_family_proof,
)


ROOT = Path(__file__).resolve().parents[1]
PROOF_SCHEMA = "dio.product_class.execution_proof.v1"


class ProductClassExecutionProofError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _manifest_for(product_id: str) -> tuple[Path, dict[str, Any]]:
    definition = FAMILY_DEFINITIONS.get(product_id)
    if definition is None:
        raise ProductClassExecutionProofError(f"no execution-proof adapter is registered for product: {product_id}")
    path = ROOT / "config" / "products" / "manifests" / f"{definition['slug']}.json"
    return path, compile_manifest(ROOT, path)


def _resolved_executor(compiled: dict[str, Any], product_id: str) -> dict[str, Any]:
    execution_rows = [
        row
        for row in compiled.get("capability_plan") or []
        if row.get("execution_required") is True and row.get("required") is True
    ]
    if len(execution_rows) != 1:
        raise ProductClassExecutionProofError(
            f"{product_id}: expected exactly one required execution capability, found {len(execution_rows)}"
        )
    row = execution_rows[0]
    if row.get("resolution_state") != "RESOLVED" or not isinstance(row.get("provider"), dict):
        raise ProductClassExecutionProofError(f"{product_id}: required execution capability is not resolved")
    provider = row["provider"]
    if provider.get("execution_capable") is not True:
        raise ProductClassExecutionProofError(f"{product_id}: resolved provider is not execution-capable")
    return {"capability_id": row.get("capability_id"), **provider}


def _assert_output_dir_is_fresh(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ProductClassExecutionProofError(
            f"execution-proof output directory must be empty before invocation: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)


def _verify_obligation_family_result(
    *,
    product_id: str,
    output_dir: Path,
    result: dict[str, Any],
    expected_executor: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = result.get("receipt") or {}
    proof_manifest = result.get("proof_manifest") or {}

    if receipt.get("schema") != "dio.obligation_family.execution_receipt.v1":
        raise ProductClassExecutionProofError(f"{product_id}: unexpected obligation-family receipt schema")
    if receipt.get("product_id") != product_id:
        raise ProductClassExecutionProofError(f"{product_id}: processor receipt product identity mismatch")
    if receipt.get("executor_id") != expected_executor.get("provider_id"):
        raise ProductClassExecutionProofError(f"{product_id}: processor receipt executor identity mismatch")
    if receipt.get("executor_id") != OBLIGATION_EXECUTOR_ID:
        raise ProductClassExecutionProofError(f"{product_id}: unexpected obligation-family executor")
    if receipt.get("internal_processing") != "COMPLETE":
        raise ProductClassExecutionProofError(f"{product_id}: controlled processor did not complete")

    for field in ("authority_created", "external_effects", "external_release"):
        if receipt.get(field) is not False:
            raise ProductClassExecutionProofError(f"{product_id}: execution proof cannot create {field}")
    if receipt.get("human_fulfilment_gate") != "NEEDS_YOU":
        raise ProductClassExecutionProofError(f"{product_id}: human fulfilment gate drifted")
    if receipt.get("external_release_gate") != "REFUSE":
        raise ProductClassExecutionProofError(f"{product_id}: external release gate drifted")

    if proof_manifest.get("schema") != "dio.obligation_family.proof_manifest.v1":
        raise ProductClassExecutionProofError(f"{product_id}: unexpected proof manifest schema")
    if proof_manifest.get("product_id") != product_id:
        raise ProductClassExecutionProofError(f"{product_id}: proof manifest product identity mismatch")
    if proof_manifest.get("authority_created") is not False:
        raise ProductClassExecutionProofError(f"{product_id}: proof manifest cannot create authority")
    if proof_manifest.get("external_release") is not False:
        raise ProductClassExecutionProofError(f"{product_id}: proof manifest cannot grant external release")

    receipt_path = output_dir / "FAMILY_RECEIPT.json"
    proof_path = output_dir / "PROOF_MANIFEST.json"
    if not receipt_path.is_file() or not proof_path.is_file():
        raise ProductClassExecutionProofError(f"{product_id}: processor did not persist required receipt/proof files")

    persisted_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    persisted_proof = json.loads(proof_path.read_text(encoding="utf-8"))
    if persisted_receipt != receipt:
        raise ProductClassExecutionProofError(f"{product_id}: persisted processor receipt differs from returned receipt")
    if persisted_proof != proof_manifest:
        raise ProductClassExecutionProofError(f"{product_id}: persisted proof manifest differs from returned manifest")

    artifacts: list[dict[str, Any]] = []
    for row in proof_manifest.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        artifact_path = output_dir / filename
        if not filename or not artifact_path.is_file():
            raise ProductClassExecutionProofError(f"{product_id}: declared artifact is missing: {filename}")
        observed = _sha_file(artifact_path)
        if observed != row.get("sha256"):
            raise ProductClassExecutionProofError(f"{product_id}: artifact hash mismatch: {filename}")
        artifacts.append(
            {
                "artifact_type": row.get("artifact_type"),
                "filename": filename,
                "sha256": observed,
            }
        )

    artifacts.extend(
        [
            {"artifact_type": "processor_receipt", "filename": receipt_path.name, "sha256": _sha_file(receipt_path)},
            {"artifact_type": "proof_manifest", "filename": proof_path.name, "sha256": _sha_file(proof_path)},
        ]
    )
    return receipt, artifacts


def verify_execution_proof(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    path = output_dir / "PRODUCT_EXECUTION_PROOF.json"
    if not path.is_file():
        raise ProductClassExecutionProofError(f"execution proof is missing: {path}")
    proof = json.loads(path.read_text(encoding="utf-8"))
    if proof.get("schema") != PROOF_SCHEMA:
        raise ProductClassExecutionProofError("unsupported product-class execution proof schema")
    if proof.get("execution_proof_state") != "CONTROLLED_ROUTE_PROVED":
        raise ProductClassExecutionProofError("execution proof is not in CONTROLLED_ROUTE_PROVED state")
    if proof.get("processor_invoked") is not True or proof.get("controlled_processor_execution") is not True:
        raise ProductClassExecutionProofError("execution proof does not attest controlled processor invocation")
    for field in ("authority_created", "external_effects", "external_release", "public_launch_ready"):
        if proof.get(field) is not False:
            raise ProductClassExecutionProofError(f"execution proof illegally promotes {field}")
    for row in proof.get("artifacts") or []:
        filename = str(row.get("filename") or "")
        artifact_path = output_dir / filename
        if not filename or not artifact_path.is_file():
            raise ProductClassExecutionProofError(f"execution-proof artifact is missing: {filename}")
        if _sha_file(artifact_path) != row.get("sha256"):
            raise ProductClassExecutionProofError(f"execution-proof artifact hash mismatch: {filename}")
    return proof


def run_execution_proof(
    product_id: str,
    fixture: dict[str, Any],
    *,
    output_dir: Path,
    operator_id: str,
    now: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ProductClassExecutionProofError("product-class execution proof requires an explicit operator_id")
    if not isinstance(fixture, dict):
        raise ProductClassExecutionProofError("product-class fixture must be a JSON object")

    manifest_path, compiled = _manifest_for(product_id)
    executor = _resolved_executor(compiled, product_id)
    if executor.get("provider_id") != OBLIGATION_EXECUTOR_ID:
        raise ProductClassExecutionProofError(f"{product_id}: adapter/executor mismatch")
    if (compiled.get("gates") or {}).get("external_release", {}).get("state") != "REFUSE":
        raise ProductClassExecutionProofError(f"{product_id}: external release must remain REFUSE during proof execution")

    source = fixture.get("source")
    evidence_inputs = fixture.get("evidence_inputs")
    if not isinstance(source, dict) or not isinstance(evidence_inputs, list):
        raise ProductClassExecutionProofError("obligation-family fixture requires source object and evidence_inputs list")

    output_dir = output_dir.resolve()
    _assert_output_dir_is_fresh(output_dir)
    result = run_family_proof(
        product_id,
        source,
        evidence_inputs,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
        job_id=job_id,
    )
    receipt, artifacts = _verify_obligation_family_result(
        product_id=product_id,
        output_dir=output_dir,
        result=result,
        expected_executor=executor,
    )

    fixture_digest = "sha256:" + _sha_bytes(_canonical(fixture))
    manifest_digest = "sha256:" + _sha_file(manifest_path)
    proof = {
        "schema": PROOF_SCHEMA,
        "product_id": product_id,
        "adapter_family": "obligation_family",
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": manifest_digest,
        "fixture_sha256": fixture_digest,
        "operator_id": operator_id,
        "executed_at": now,
        "execution_capability": executor.get("capability_id"),
        "executor_id": executor.get("provider_id"),
        "executor_ref": executor.get("ref"),
        "processor_invoked": True,
        "controlled_processor_execution": True,
        "execution_proof_state": "CONTROLLED_ROUTE_PROVED",
        "processor_receipt_schema": receipt.get("schema"),
        "processor_receipt_internal_state": receipt.get("internal_processing"),
        "human_review_gate": receipt.get("human_fulfilment_gate"),
        "external_release_gate": receipt.get("external_release_gate"),
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "public_launch_ready": False,
        "artifacts": artifacts,
        "claim_ceiling": (
            "This receipt proves that the bounded typed processor route executed over the recorded controlled fixture "
            "and produced the hash-verified artifacts listed here. It does not prove a human fulfilment decision, "
            "grant or tender award, permit decision, legal opinion, external action, customer validation, public-launch "
            "authority, or external release."
        ),
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    _write_json(output_dir / "PRODUCT_EXECUTION_PROOF.json", proof)
    verify_execution_proof(output_dir)
    return {"proof": proof, "processor_result": result, "output_dir": str(output_dir)}
