#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.portfolio_production_readiness import (  # noqa: E402
    evaluate_portfolio_production_readiness,
    load_receipt,
    write_portfolio_production_readiness_receipt,
)
from products.product_grade_sellability_gauntlet import run_product_sellability_gauntlet  # noqa: E402


def _run_full57(output: Path, *, online: bool) -> Path:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_portfolio_customer_surface_gauntlet.py"),
        "--wave",
        "full57",
        "--output",
        str(output),
    ]
    if online:
        command.append("--online")
    completed = subprocess.run(command, cwd=ROOT)
    receipt = output / "PORTFOLIO_CUSTOMER_SURFACE_GAUNTLET_RECEIPT.json"
    if completed.returncode != 0 or not receipt.is_file():
        raise RuntimeError(f"full57 customer-surface gauntlet failed with exit code {completed.returncode}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure DIO portfolio production readiness without collapsing buyer sellability, internal operational readiness, "
            "or commercial validation into one claim. Fresh production-readiness runs refresh public market signals by default."
        )
    )
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "portfolio_production_readiness")
    parser.add_argument("--reuse-customer-surface-root", type=Path, default=None)
    parser.add_argument("--reuse-studio-sellability-root", type=Path, default=None)
    parser.add_argument("--canonical-sellability-receipt", type=Path, default=None)
    parser.add_argument("--online", action="store_true", help="Explicitly request current public-signal refresh (fresh runs already do this by default).")
    parser.add_argument("--offline", action="store_true", help="Diagnostic only: suppress current public-signal refresh; Market Radar/Opportunity Foundry may legitimately REFUSE.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero until the complete evidence-scoped portfolio is production-ready.")
    args = parser.parse_args()

    if args.online and args.offline:
        parser.error("--online and --offline cannot be used together")
    fresh_run_online = not args.offline

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    if args.reuse_customer_surface_root:
        customer_surface_path = args.reuse_customer_surface_root.resolve() / "PORTFOLIO_CUSTOMER_SURFACE_GAUNTLET_RECEIPT.json"
        if not customer_surface_path.is_file():
            raise RuntimeError(f"missing reused customer-surface receipt: {customer_surface_path}")
    else:
        customer_surface_path = _run_full57(output / "full57_customer_surface", online=fresh_run_online)

    if args.reuse_studio_sellability_root:
        studio_sellability_path = args.reuse_studio_sellability_root.resolve() / "PRODUCT_SELLABILITY_PORTFOLIO_RECEIPT.json"
        if not studio_sellability_path.is_file():
            raise RuntimeError(f"missing reused Studio sellability receipt: {studio_sellability_path}")
    else:
        studio_root = output / "studio_sellability"
        run_product_sellability_gauntlet(output_dir=studio_root, root=ROOT)
        studio_sellability_path = studio_root / "PRODUCT_SELLABILITY_PORTFOLIO_RECEIPT.json"

    customer_surface = load_receipt(customer_surface_path)
    studio_sellability = load_receipt(studio_sellability_path)
    canonical_sellability = load_receipt(args.canonical_sellability_receipt.resolve()) if args.canonical_sellability_receipt else None

    receipt = evaluate_portfolio_production_readiness(
        customer_surface_receipt=customer_surface,
        studio_sellability_receipt=studio_sellability,
        canonical_sellability_receipt=canonical_sellability,
    )
    receipt_path = write_portfolio_production_readiness_receipt(receipt, output)

    summary = {
        "acceptance_token": receipt["acceptance_token"],
        "portfolio_production_ready": receipt["portfolio_production_ready"],
        "surface_count": receipt["surface_count"],
        "buyer_facing_surface_count": receipt["buyer_facing_surface_count"],
        "buyer_production_ready_count": receipt["buyer_production_ready_count"],
        "buyer_needs_sellability_grade_count": receipt["buyer_needs_sellability_grade_count"],
        "buyer_refuse_count": receipt["buyer_refuse_count"],
        "internal_capability_count": receipt["internal_capability_count"],
        "internal_production_ready_count": receipt["internal_production_ready_count"],
        "internal_refuse_count": receipt["internal_refuse_count"],
        "studio_sellability_verified_count": receipt["studio_sellability_verified_count"],
        "canonical_buyer_production_ready_count": receipt["canonical_buyer_production_ready_count"],
        "canonical_buyer_needs_sellability_grade_count": receipt["canonical_buyer_needs_sellability_grade_count"],
        "family_sellability_backlog": receipt["family_sellability_backlog"],
        "commercial_validation": receipt["commercial_validation"],
        "receipt": str(receipt_path),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.strict and not receipt["portfolio_production_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
