#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canonical_sellability import (  # noqa: E402
    load_json,
    run_canonical_sellability,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the 47 canonical buyer products through family-level sellability grading with a genuinely unseen "
            "customer case, artifact hash custody, family quality checks, and truth/authority boundaries."
        )
    )
    parser.add_argument("--execution-receipt", type=Path, required=True)
    parser.add_argument("--customer-surface-receipt", type=Path, required=True)
    parser.add_argument("--production-readiness-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "canonical_sellability")
    parser.add_argument("--family", default=None, help="Run one family only for diagnosis. Omit for the full 47-product canonical receipt.")
    parser.add_argument("--online", action="store_true", help="Allow online-capable routes to refresh current public signals if a selected route requires them.")
    parser.add_argument("--reuse-unseen", action="store_true", help="Reuse matching successful unseen-case executions already present under the output root.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero unless the complete 47-product canonical population is sellability verified.")
    args = parser.parse_args()

    receipt = run_canonical_sellability(
        execution_receipt=load_json(args.execution_receipt.resolve()),
        customer_surface_receipt=load_json(args.customer_surface_receipt.resolve()),
        readiness_receipt=load_json(args.production_readiness_receipt.resolve()),
        output_dir=args.output.resolve(),
        online=args.online,
        reuse_unseen=args.reuse_unseen,
        selected_family=args.family,
    )

    summary = {
        "acceptance_token": receipt["acceptance_token"],
        "canonical_buyer_count": receipt["canonical_buyer_count"],
        "full_canonical_buyer_population": receipt["full_canonical_buyer_population"],
        "sellability_verified_count": receipt["sellability_verified_count"],
        "sellability_refuse_count": receipt["sellability_refuse_count"],
        "all_canonical_sellability_verified": receipt["all_canonical_sellability_verified"],
        "family_summary": receipt["family_summary"],
        "human_buyer_review_pending_count": receipt["human_buyer_review_pending_count"],
        "commercial_validation": receipt["commercial_validation"],
        "receipt": str(args.output.resolve() / "CANONICAL_SELLABILITY_RECEIPT.json"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.strict and not receipt["all_canonical_sellability_verified"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
