#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from products.registry import ROOT, bootstrap_generic_job, get_profile, product_profiles


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or safely stage a registered DIO product profile without executing it.")
    parser.add_argument("--list", action="store_true", help="List registered product profiles.")
    parser.add_argument("--product", help="Show one product profile by ID.")
    parser.add_argument("--source-job", help="Bootstrap a generic governed workflow from an existing routed job under runs/.")
    parser.add_argument("--state-root", default=str(ROOT / "state" / "product_jobs"), help="Generic product workflow state directory.")
    args = parser.parse_args()

    if args.list:
        rows = [
            {
                "id": product_id,
                "name": profile.get("name"),
                "status": profile.get("status"),
                "runtime_mode": profile.get("runtime_mode"),
                "campaign_enabled": profile.get("campaign_enabled"),
                "customer_facing": profile.get("customer_facing"),
            }
            for product_id, profile in product_profiles().items()
        ]
        print(json.dumps(rows, indent=2))
        return 0

    if args.product:
        print(json.dumps(get_profile(args.product), indent=2))
        return 0

    if args.source_job:
        workflow = bootstrap_generic_job(
            Path(args.source_job),
            Path(args.state_root),
            ROOT / "runs",
        )
        print(json.dumps(workflow, indent=2))
        return 0

    parser.error("Use --list, --product PRODUCT_ID, or --source-job PATH.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
