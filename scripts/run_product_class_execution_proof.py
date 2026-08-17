#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.obligationfamily.runner import FAMILY_DEFINITIONS  # noqa: E402
from products.product_class_execution_proof import run_execution_proof  # noqa: E402


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _golden_fixture(product_id: str) -> dict:
    definition = FAMILY_DEFINITIONS.get(product_id)
    if definition is None:
        raise ValueError(f"no golden execution fixture is registered for product: {product_id}")
    root = ROOT / "config" / "products" / "golden" / definition["slug"]
    source = _load_json(root / "reference_source.json")
    evidence_payload = _load_json(root / "reference_evidence.json")
    return {
        "source": source,
        "evidence_inputs": evidence_payload.get("evidence_records") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded DIO product-class processor and emit hash-verified controlled execution proof."
    )
    parser.add_argument("--product-id", required=True)
    fixture_group = parser.add_mutually_exclusive_group(required=True)
    fixture_group.add_argument("--fixture", type=Path, help="JSON object containing source and evidence_inputs")
    fixture_group.add_argument("--golden", action="store_true", help="Use the canonical controlled golden fixture")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--job-id")
    parser.add_argument("--now", default=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    args = parser.parse_args()

    fixture = _golden_fixture(args.product_id) if args.golden else _load_json(args.fixture)
    result = run_execution_proof(
        args.product_id,
        fixture,
        output_dir=args.output_dir,
        operator_id=args.operator_id,
        now=args.now,
        job_id=args.job_id,
    )
    proof = result["proof"]
    summary = {
        "schema": proof["schema"],
        "product_id": proof["product_id"],
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
