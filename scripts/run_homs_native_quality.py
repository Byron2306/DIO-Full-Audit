#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.native_product_quality import ACCEPTANCE_TOKEN, audit_homs_exam  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify buyer-grade native HyMark artifacts for one HOMS Exam job.")
    parser.add_argument("--native-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    receipt = audit_homs_exam(args.native_receipt)
    output = args.output or (args.native_receipt.parent / "DIO_NATIVE_PRODUCT_QUALITY_RECEIPT.json")
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "product": receipt["product"],
        "native_engine": receipt["native_engine"],
        "artifact_quality_verified": receipt["artifact_quality_verified"],
        "site_promotion_allowed": receipt["site_promotion_allowed"],
        "acceptance_token": receipt["acceptance_token"],
        "failed_checks": [name for name, passed in receipt["checks"].items() if not passed],
        "artifacts": {
            name: {
                "bytes": row.get("bytes"),
                "word_count": row.get("word_count"),
                "path": row.get("path"),
            }
            for name, row in receipt["artifacts"].items()
        },
        "receipt": str(output),
        "commercial_validation": receipt["commercial_validation"],
        "external_release": receipt["external_release"],
        "human_release": receipt["human_release"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if receipt["acceptance_token"] == ACCEPTANCE_TOKEN else 2


if __name__ == "__main__":
    raise SystemExit(main())
