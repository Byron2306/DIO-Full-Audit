#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.portfolio_suite_native_guard import build_and_render_guarded_suite_site  # noqa: E402
from products.portfolio_suite_studio import load_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the DIO six-suite portfolio website from governed execution, customer-surface, "
            "production-readiness and native artifact-quality evidence."
        )
    )
    parser.add_argument("--execution-receipt", type=Path, required=True)
    parser.add_argument("--customer-surface-receipt", type=Path, required=True)
    parser.add_argument("--production-readiness-receipt", type=Path, required=True)
    parser.add_argument(
        "--native-quality-receipt",
        type=Path,
        action="append",
        required=True,
        help=(
            "Native artifact-quality receipt. Repeat once per restored buyer-facing product. "
            "Products without verified native artifact quality are withheld from artifact showcase "
            "and prevent a final Site Studio acceptance token."
        ),
    )
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "portfolio_suite_studio")
    parser.add_argument(
        "--no-bundle-artifacts",
        action="store_true",
        help="Build the review preview without copying quality-verified customer artifacts into the site bundle.",
    )
    args = parser.parse_args()

    execution = load_json(args.execution_receipt.resolve())
    customer_surface = load_json(args.customer_surface_receipt.resolve())
    readiness = load_json(args.production_readiness_receipt.resolve())
    native_quality = [load_json(path.resolve()) for path in args.native_quality_receipt]

    result = build_and_render_guarded_suite_site(
        execution_receipt=execution,
        customer_surface_receipt=customer_surface,
        readiness_receipt=readiness,
        native_quality_receipts=native_quality,
        output_dir=args.output.resolve(),
        bundle_artifacts=not args.no_bundle_artifacts,
    )
    receipt = result["receipt"]
    guard = dict(result.get("guard") or {})

    summary = {
        "acceptance_token": receipt.get("acceptance_token"),
        "suite_count": receipt["suite_count"],
        "canonical_product_count": receipt["canonical_product_count"],
        "execution_verified_journey_count": receipt["execution_verified_journey_count"],
        "portfolio_production_ready": receipt["portfolio_production_ready"],
        "suite_states": receipt["suite_states"],
        "native_artifact_quality_required_count": guard.get("buyer_facing_quality_required_count"),
        "native_artifact_quality_verified_count": guard.get("buyer_facing_quality_verified_count"),
        "native_artifact_quality_missing_count": guard.get("buyer_facing_quality_missing_count"),
        "native_artifact_quality_verified_products": guard.get("verified_products"),
        "page_count": receipt["page_count"],
        "bundled_customer_artifact_count": receipt["bundled_customer_artifact_count"],
        "format_core_visual_asset_count": receipt["format_core_visual_asset_count"],
        "format_core_visual_composition": receipt["format_core_visual_composition"],
        "commercial_validation": receipt["commercial_validation"],
        "customer_site": str(result["customer_site"]),
        "proof_model": str(result["proof_model"]),
        "receipt": str(result["receipt_path"]),
        "publication": receipt["publication"],
        "human_release": receipt["human_release"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if receipt.get("acceptance_token") else 2


if __name__ == "__main__":
    raise SystemExit(main())
