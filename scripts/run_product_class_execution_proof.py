#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.accreditation_execution_proof import controlled_accreditation_fixture, run_accreditation_execution_proof  # noqa: E402
from products.agentauthority_execution_proof import controlled_agentauthority_fixture, run_agentauthority_execution_proof  # noqa: E402
from products.contractproof_execution_proof import run_contractproof_execution_proof  # noqa: E402
from products.evidence_profile_execution_proof import (  # noqa: E402
    _profiles_by_product,
    controlled_evidence_fixture,
    run_evidence_profile_execution_proof,
)
from products.obligationfamily.runner import FAMILY_DEFINITIONS  # noqa: E402
from products.product_class_execution_proof import run_execution_proof  # noqa: E402
from products.regops_execution_proof import controlled_regops_fixture, run_regops_execution_proof  # noqa: E402
from products.vamp_profile_execution_proof import (  # noqa: E402
    controlled_vamp_fixture,
    run_vamp_profile_execution_proof,
    vamp_profiles_by_product,
)


CONTRACTPROOF_PRODUCT_ID = "dio_contractproof"
REGOPS_PRODUCT_ID = "dio_regops"
ACCREDITATION_PRODUCT_ID = "dio_accreditation"
AGENTAUTHORITY_PRODUCT_ID = "dio_agentauthority"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _golden_fixture(product_id: str) -> dict:
    if product_id == CONTRACTPROOF_PRODUCT_ID:
        return {"fixture_kind": "dio.phase11_1.gauntlet.v1", "inbound_owner": "vesper"}
    if product_id == REGOPS_PRODUCT_ID:
        return controlled_regops_fixture()
    if product_id == ACCREDITATION_PRODUCT_ID:
        return controlled_accreditation_fixture()
    if product_id == AGENTAUTHORITY_PRODUCT_ID:
        return controlled_agentauthority_fixture()

    definition = FAMILY_DEFINITIONS.get(product_id)
    if definition is not None:
        root = ROOT / "config" / "products" / "golden" / definition["slug"]
        source = _load_json(root / "reference_source.json")
        evidence_payload = _load_json(root / "reference_evidence.json")
        return {"source": source, "evidence_inputs": evidence_payload.get("evidence_records") or []}

    profile_id = _profiles_by_product().get(product_id)
    if profile_id is not None:
        return controlled_evidence_fixture(profile_id)
    vamp_profile_id = vamp_profiles_by_product().get(product_id)
    if vamp_profile_id is not None:
        return controlled_vamp_fixture(vamp_profile_id)
    raise ValueError(f"no controlled execution fixture is registered for product: {product_id}")


def _run(product_id: str, fixture: dict, *, output_dir: Path, operator_id: str, now: str, job_id: str | None):
    if product_id == CONTRACTPROOF_PRODUCT_ID:
        if fixture.get("fixture_kind") != "dio.phase11_1.gauntlet.v1" or fixture.get("inbound_owner") != "vesper":
            raise ValueError("ContractProof proof CLI requires the Vesper-owned Phase 11.1 controlled fixture")
        return run_contractproof_execution_proof(output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id == REGOPS_PRODUCT_ID:
        return run_regops_execution_proof(fixture, output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id == ACCREDITATION_PRODUCT_ID:
        return run_accreditation_execution_proof(fixture, output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id == AGENTAUTHORITY_PRODUCT_ID:
        return run_agentauthority_execution_proof(fixture, output_dir=output_dir, operator_id=operator_id, now=now)
    if product_id in FAMILY_DEFINITIONS:
        return run_execution_proof(product_id, fixture, output_dir=output_dir, operator_id=operator_id, now=now, job_id=job_id)
    if product_id in _profiles_by_product():
        return run_evidence_profile_execution_proof(product_id, fixture, output_dir=output_dir, operator_id=operator_id, now=now, job_id=job_id)
    if product_id in vamp_profiles_by_product():
        return run_vamp_profile_execution_proof(product_id, fixture, output_dir=output_dir, operator_id=operator_id, now=now, job_id=job_id)
    raise ValueError(f"no execution-proof adapter is registered for product: {product_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded DIO product-class processor and emit hash-verified controlled execution proof.")
    parser.add_argument("--product-id", required=True)
    fixture_group = parser.add_mutually_exclusive_group(required=True)
    fixture_group.add_argument("--fixture", type=Path, help="JSON controlled execution fixture")
    fixture_group.add_argument("--golden", action="store_true", help="Use the canonical/deterministic controlled fixture")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--job-id")
    parser.add_argument("--now", default=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    args = parser.parse_args()

    fixture = _golden_fixture(args.product_id) if args.golden else _load_json(args.fixture)
    result = _run(args.product_id, fixture, output_dir=args.output_dir, operator_id=args.operator_id, now=args.now, job_id=args.job_id)
    proof = result["proof"]
    summary = {
        "schema": proof["schema"],
        "product_id": proof["product_id"],
        "atlas_product_class": proof.get("atlas_product_class"),
        "adapter_family": proof["adapter_family"],
        "execution_proof_state": proof["execution_proof_state"],
        "executor_id": proof["executor_id"],
        "controlled_processor_execution": proof["controlled_processor_execution"],
        "human_review_gate": proof["human_review_gate"],
        "external_release_gate": proof["external_release_gate"],
        "public_launch_ready": proof["public_launch_ready"],
        "proof_fingerprint": proof["proof_fingerprint"],
        "output_dir": result["output_dir"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
