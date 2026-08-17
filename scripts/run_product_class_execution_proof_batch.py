#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.accreditation_execution_proof import controlled_accreditation_fixture, run_accreditation_execution_proof  # noqa: E402
from products.agentauthority_execution_proof import controlled_agentauthority_fixture, run_agentauthority_execution_proof  # noqa: E402
from products.contractproof_execution_proof import run_contractproof_execution_proof  # noqa: E402
from products.dossierops_execution_proof import controlled_dossierops_fixture, run_dossierops_execution_proof  # noqa: E402
from products.education_research_execution_proof import controlled_education_research_fixture, profiles_by_product as education_research_profiles_by_product, run_education_research_execution_proof  # noqa: E402
from products.evidence_profile_execution_proof import _profiles_by_product, controlled_evidence_fixture, run_evidence_profile_execution_proof  # noqa: E402
from products.high_risk_execution_proof import controlled_high_risk_fixture, high_risk_profiles_by_product, run_high_risk_execution_proof  # noqa: E402
from products.obligationfamily.runner import FAMILY_DEFINITIONS  # noqa: E402
from products.product_class_execution_proof import run_execution_proof, verify_execution_proof  # noqa: E402
from products.regops_execution_proof import controlled_regops_fixture, run_regops_execution_proof  # noqa: E402
from products.vamp_profile_execution_proof import controlled_vamp_fixture, run_vamp_profile_execution_proof, vamp_profiles_by_product  # noqa: E402


BATCH_SCHEMA = "dio.product_class.execution_proof_batch.v1"
CONTRACTPROOF_PRODUCT_ID = "dio_contractproof"
REGOPS_PRODUCT_ID = "dio_regops"
ACCREDITATION_PRODUCT_ID = "dio_accreditation"
AGENTAUTHORITY_PRODUCT_ID = "dio_agentauthority"
DOSSIEROPS_PRODUCT_ID = "dio_dossierops"


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


def registered_products() -> tuple[str, ...]:
    products = set(FAMILY_DEFINITIONS)
    products.update(_profiles_by_product())
    products.update(vamp_profiles_by_product())
    products.update(education_research_profiles_by_product())
    products.update(high_risk_profiles_by_product())
    products.update({
        CONTRACTPROOF_PRODUCT_ID,
        REGOPS_PRODUCT_ID,
        ACCREDITATION_PRODUCT_ID,
        AGENTAUTHORITY_PRODUCT_ID,
        DOSSIEROPS_PRODUCT_ID,
    })
    return tuple(sorted(products))


def _obligation_fixture(product_id: str) -> dict[str, Any]:
    definition = FAMILY_DEFINITIONS[product_id]
    root = ROOT / "config" / "products" / "golden" / definition["slug"]
    source = json.loads((root / "reference_source.json").read_text(encoding="utf-8"))
    evidence = json.loads((root / "reference_evidence.json").read_text(encoding="utf-8"))
    return {"source": source, "evidence_inputs": evidence.get("evidence_records") or []}


def _run_one(product_id: str, *, output_dir: Path, operator_id: str, now: str) -> dict[str, Any]:
    if product_id == CONTRACTPROOF_PRODUCT_ID:
        return run_contractproof_execution_proof(output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id == REGOPS_PRODUCT_ID:
        return run_regops_execution_proof(controlled_regops_fixture(), output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id == ACCREDITATION_PRODUCT_ID:
        return run_accreditation_execution_proof(controlled_accreditation_fixture(), output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id == AGENTAUTHORITY_PRODUCT_ID:
        return run_agentauthority_execution_proof(controlled_agentauthority_fixture(), output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id == DOSSIEROPS_PRODUCT_ID:
        return run_dossierops_execution_proof(controlled_dossierops_fixture(), output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id in FAMILY_DEFINITIONS:
        return run_execution_proof(product_id, _obligation_fixture(product_id), output_dir=output_dir, operator_id=operator_id, now=now)
    evidence_profile = _profiles_by_product().get(product_id)
    if evidence_profile is not None:
        return run_evidence_profile_execution_proof(product_id, controlled_evidence_fixture(evidence_profile), output_dir=output_dir, operator_id=operator_id, now=now)
    vamp_profile = vamp_profiles_by_product().get(product_id)
    if vamp_profile is not None:
        return run_vamp_profile_execution_proof(product_id, controlled_vamp_fixture(vamp_profile), output_dir=output_dir, operator_id=operator_id, now=now)
    education_research_profile = education_research_profiles_by_product().get(product_id)
    if education_research_profile is not None:
        return run_education_research_execution_proof(
            product_id,
            controlled_education_research_fixture(education_research_profile),
            output_dir=output_dir,
            operator_id=operator_id,
            now=now,
        )
    high_risk_profile = high_risk_profiles_by_product().get(product_id)
    if high_risk_profile is not None:
        return run_high_risk_execution_proof(
            product_id,
            controlled_high_risk_fixture(high_risk_profile),
            output_dir=output_dir,
            operator_id=operator_id,
            now=now,
        )
    raise RuntimeError(f"batch execution-proof adapter missing: {product_id}")


def run_batch(*, output_root: Path, operator_id: str, now: str) -> dict[str, Any]:
    if not str(operator_id or "").strip():
        raise ValueError("batch execution proof requires an explicit operator_id")
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"batch output root must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for product_id in registered_products():
        product_dir = output_root / product_id
        result = _run_one(product_id, output_dir=product_dir, operator_id=operator_id, now=now)
        proof = verify_execution_proof(product_dir)
        proof_path = product_dir / "PRODUCT_EXECUTION_PROOF.json"
        if proof != result["proof"]:
            raise RuntimeError(f"batch proof verification drifted: {product_id}")
        rows.append(
            {
                "product_id": product_id,
                "atlas_product_class": proof.get("atlas_product_class"),
                "adapter_family": proof["adapter_family"],
                "execution_proof_state": proof["execution_proof_state"],
                "proof_fingerprint": proof["proof_fingerprint"],
                "proof_sha256": "sha256:" + _sha_file(proof_path),
                "relative_path": str(proof_path.relative_to(output_root)),
                "human_review_gate": proof["human_review_gate"],
                "external_release_gate": proof["external_release_gate"],
                "public_launch_ready": proof["public_launch_ready"],
            }
        )

    receipt: dict[str, Any] = {
        "schema": BATCH_SCHEMA,
        "generated_at": now,
        "operator_id": operator_id,
        "registered_proof_adapters": len(rows),
        "controlled_routes_proved": sum(row["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED" for row in rows),
        "all_controlled_routes_proved": all(row["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED" for row in rows),
        "public_launch_ready_products": [row["product_id"] for row in rows if row["public_launch_ready"] is True],
        "products": rows,
        "truth_boundary": (
            "This batch proves only the listed controlled processor routes over controlled fixtures or governed "
            "upstream receipts. For high-risk no-engine profiles the proved route is evidence review only; no domain "
            "engine is assigned or invoked and no domain execution proof is created. Human review, customer source "
            "authority, external effects, public launch, external release, customer validation and repeatable "
            "commercial demand remain separate gates."
        ),
    }
    receipt["batch_fingerprint"] = "sha256:" + _sha_bytes(_canonical(receipt))
    receipt_path = output_root / "BATCH_EXECUTION_PROOF_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute all currently attached DIO product-class proof adapters.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--now", default=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    parser.add_argument("--replace", action="store_true", help="Delete an existing output directory before the controlled batch.")
    args = parser.parse_args()
    out = args.out.expanduser().resolve()
    if args.replace and out.exists():
        shutil.rmtree(out)
    receipt = run_batch(output_root=out, operator_id=args.operator_id, now=args.now)
    print(json.dumps({
        "schema": receipt["schema"],
        "registered_proof_adapters": receipt["registered_proof_adapters"],
        "controlled_routes_proved": receipt["controlled_routes_proved"],
        "all_controlled_routes_proved": receipt["all_controlled_routes_proved"],
        "public_launch_ready_products": receipt["public_launch_ready_products"],
        "batch_fingerprint": receipt["batch_fingerprint"],
        "output_root": str(out),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
