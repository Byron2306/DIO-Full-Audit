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
from products.canon_extension_native_profiles import NATIVE_CANON_EXTENSION_PROFILES
from products.professional_evidence_corpus import CASES


_STUDIO_NATIVE_CLOSURES = {
    "Article Publication Studio": [
        "sophia_source_review",
        "evidex_proof",
        "document_studio_publication_pack",
        "nichefoundry_positioning",
    ],
    "Finance Readiness Studio": [
        "sophia_assumption_boundary",
        "vamp_milestone_map",
        "evidex_readiness_gap_map",
        "document_studio_finance_pack",
        "nichefoundry_positioning",
    ],
    "Professional Correspondence Studio": [
        "vesper_release_preparation",
        "evidex_intake_structure",
        "document_studio_correspondence_pack",
    ],
    "Site Studio": [
        "market_command_positioning",
        "nichefoundry_positioning",
        "evidex_proof",
        "document_studio_sales_assets",
        "vesper_release_preparation",
    ],
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def build_proof_production_matrix(root: Path = ROOT) -> dict[str, Any]:
    registry = build_phase8_binding_registry(Path(root))
    native_extensions = {
        str(profile["name"]): profile
        for profile in NATIVE_CANON_EXTENSION_PROFILES
    }
    rows: list[dict[str, Any]] = []
    for binding in registry["bindings"]:
        contract = binding["offer_contract"]
        plan = binding["capability_plan"]
        required = [row["capability_id"] for row in plan if row.get("execution_required")]
        product_name = binding["product_name"]
        native_extension = native_extensions.get(product_name)
        if product_name in CASES:
            customer_case_coverage = "CANONICAL_CASE_AVAILABLE"
            controlled_evidence_path = "vesper_customer_case_x3"
            recommended_customer_route = binding["fulfilment_profile"]["route_id"]
            specialist_capabilities: list[str] = []
        elif product_name in _STUDIO_NATIVE_CLOSURES:
            customer_case_coverage = "STUDIO_NATIVE_CLOSURE_AVAILABLE"
            controlled_evidence_path = "studio_native_closure"
            recommended_customer_route = "studio_native_closure"
            specialist_capabilities = list(_STUDIO_NATIVE_CLOSURES[product_name])
        elif native_extension:
            customer_case_coverage = "NATIVE_SPECIALIST_CASE_AVAILABLE"
            controlled_evidence_path = "native_extension_product_grade"
            recommended_customer_route = "native_extension_product_grade"
            specialist_capabilities = [
                "lingua_semantic_custody",
                "beast_mechanical_product_grade",
                "unseen_input_generalisation",
            ]
        else:
            customer_case_coverage = "CASE_EXTENSION_REQUIRED"
            controlled_evidence_path = "product_grade_extension"
            recommended_customer_route = binding["fulfilment_profile"]["route_id"]
            specialist_capabilities = []
        blockers = ["fresh_held_customer_artifact_required"]
        if customer_case_coverage == "CASE_EXTENSION_REQUIRED":
            blockers.append("customer_case_extension_required")
        if binding["product_compiler_manifest"]["state"] != "CANONICAL_MANIFEST_PRESENT":
            blockers.append("canonical_product_manifest_mapping_required")
        rows.append({
            "product_id": binding["product_id"],
            "product_name": product_name,
            "suite": binding["suite"],
            "native_route": binding["fulfilment_profile"]["route_id"],
            "required_capabilities": required,
            "available_on_approved_request": [row["capability_id"] for row in plan if not row.get("execution_required")],
            "controlled_evidence_path": controlled_evidence_path,
            "customer_case_coverage": customer_case_coverage,
            "recommended_customer_route": recommended_customer_route,
            "route_composition": binding["fulfilment_profile"]["organ_composition"],
            "specialist_quality_capabilities": specialist_capabilities,
            "sellable_quality_state": "HELD_EVIDENCE_REQUIRED",
            "sellable_quality_blockers": blockers,
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
