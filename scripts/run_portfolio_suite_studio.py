#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.portfolio_suite_studio import (  # noqa: E402
    build_suite_model,
    load_json,
    render_suite_site,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the DIO six-suite portfolio website from ATLAS membership and governed execution, "
            "customer-surface and production-readiness evidence."
        )
    )
    parser.add_argument("--execution-receipt", type=Path, required=True)
    parser.add_argument("--customer-surface-receipt", type=Path, required=True)
    parser.add_argument("--production-readiness-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "portfolio_suite_studio")
    parser.add_argument(
        "--no-bundle-artifacts",
        action="store_true",
        help="Build the evidence-projected site without copying selected customer artifacts into the site bundle.",
    )
    args = parser.parse_args()

    execution = load_json(args.execution_receipt.resolve())
    customer_surface = load_json(args.customer_surface_receipt.resolve())
    readiness = load_json(args.production_readiness_receipt.resolve())

    model = build_suite_model(
        execution_receipt=execution,
        customer_surface_receipt=customer_surface,
        readiness_receipt=readiness,
    )
    result = render_suite_site(
        model=model,
        execution_receipt=execution,
        customer_surface_receipt=customer_surface,
        readiness_receipt=readiness,
        output_dir=args.output.resolve(),
        bundle_artifacts=not args.no_bundle_artifacts,
    )
    receipt = result["receipt"]

    summary = {
        "acceptance_token": receipt["acceptance_token"],
        "suite_count": receipt["suite_count"],
        "canonical_product_count": receipt["canonical_product_count"],
        "execution_verified_journey_count": receipt["execution_verified_journey_count"],
        "portfolio_production_ready": receipt["portfolio_production_ready"],
        "suite_states": receipt["suite_states"],
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
    return 0 if receipt["acceptance_token"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
