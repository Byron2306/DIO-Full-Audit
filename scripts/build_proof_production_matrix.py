#!/usr/bin/env python3
"""Build the honest execution backlog for all canonical customer artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from presence_core.product_binding_registry import build_phase8_binding_registry
from products.professional_evidence_corpus import CASES


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def build_proof_production_matrix(root: Path = ROOT) -> dict[str, Any]:
    registry = build_phase8_binding_registry(Path(root))
    rows: list[dict[str, Any]] = []
    for binding in registry["bindings"]:
        contract = binding["offer_contract"]
        plan = binding["capability_plan"]
        required = [row["capability_id"] for row in plan if row.get("execution_required")]
        product_name = binding["product_name"]
        rows.append({
            "product_id": binding["product_id"],
            "product_name": product_name,
            "suite": binding["suite"],
            "native_route": binding["fulfilment_profile"]["route_id"],
            "required_capabilities": required,
            "available_on_approved_request": [row["capability_id"] for row in plan if not row.get("execution_required")],
            "controlled_evidence_path": "vesper_customer_case_x3" if product_name in CASES else "product_grade_extension",
            "named_artifact_proof": contract["proof"]["product_artifact_proof"],
            "proof_production_state": "NEEDS_HELD_ARTIFACT_RUN",
            "next_required_receipts": ["format_core_review_artifact", "production_studio_review_manifest", "held_customer_artifact_receipt"],
            "external_release_authorized": False,
            "commercial_validation": "UNPROVED",
        })
    rows.sort(key=lambda row: row["product_name"].casefold())
    base = {"schema": "dio.proof_production_matrix.v1", "offer_count": len(rows), "offers": rows, "authority_created": False, "external_effects": False}
    return {**base, "matrix_sha256": hashlib.sha256(_canonical(base)).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    matrix = build_proof_production_matrix()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(matrix, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"offer_count": matrix["offer_count"], "matrix_sha256": matrix["matrix_sha256"], "output": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
