#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.portfolio_customer_substance import evaluate_receipt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit customer-surface gauntlet outputs for objective buyer-substance sufficiency without claiming buyer acceptance.")
    parser.add_argument("--gauntlet-root", type=Path, required=True)
    parser.add_argument("--strict", action="store_true", help="Return non-zero unless every selected surface is substance-ready with no warnings or refusals.")
    args = parser.parse_args()

    root = args.gauntlet_root.expanduser().resolve()
    receipt_path = root / "PORTFOLIO_CUSTOMER_SURFACE_GAUNTLET_RECEIPT.json"
    if not receipt_path.is_file():
        raise FileNotFoundError(f"customer-surface gauntlet receipt not found: {receipt_path}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    audit = evaluate_receipt(receipt)
    target = root / "PORTFOLIO_CUSTOMER_SUBSTANCE_AUDIT.json"
    target.write_text(json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "source_wave": audit["source_wave"],
        "surface_count": audit["surface_count"],
        "substance_ready_count": audit["substance_ready_count"],
        "substance_partial_count": audit["substance_partial_count"],
        "substance_refuse_count": audit["substance_refuse_count"],
        "all_substance_ready": audit["all_substance_ready"],
        "audit": str(target),
        "rows": [
            {
                "surface": row["surface_name"],
                "state": row["buyer_substance_state"],
                "hard_failures": row["hard_failures"],
                "warnings": row["warnings"],
            }
            for row in audit["rows"]
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.strict and not audit["all_substance_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
