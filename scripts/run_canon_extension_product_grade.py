from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canon_extension_product_grade import (
    PROOF_VERIFIED,
    PROOF_VERIFIED_TOKEN,
    PRODUCT_GRADE_VERIFIED,
    VERIFIED_TOKEN,
    run_canon_extension_product_grade_gauntlet,
)
from products.product_grade_gauntlet import run_product_grade_gauntlet

CANONICAL_SUMMARY_PATH = (
    ROOT
    / "state"
    / "product_grade"
    / "canon_extensions"
    / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
)


def _summary_is_publishable(receipt: dict) -> bool:
    extensions = receipt.get("extensions")
    if not (
        receipt.get("acceptance_token") == VERIFIED_TOKEN
        and receipt.get("proof_acceptance_token") == PROOF_VERIFIED_TOKEN
        and receipt.get("extension_count") == 15
        and receipt.get("product_grade_verified_count") == 15
        and receipt.get("canon_extension_proof_verified_count") == 15
        and receipt.get("all_product_grade_verified") is True
        and receipt.get("all_canon_extension_proof_verified") is True
        and receipt.get("commercial_validation") == "UNPROVED"
        and receipt.get("authority_created") is False
        and receipt.get("external_effects") is False
        and isinstance(extensions, dict)
        and len(extensions) == 15
    ):
        return False
    for row in extensions.values():
        if not isinstance(row, dict):
            return False
        if row.get("status") != PRODUCT_GRADE_VERIFIED or row.get("proof_status") != PROOF_VERIFIED:
            return False
        if row.get("critical_blockers"):
            return False
        if row.get("customers_will_pay") != "UNPROVED" or row.get("verified_payment") != "UNPROVED":
            return False
    return True


def persist_verified_summary(receipt: dict, path: Path = CANONICAL_SUMMARY_PATH) -> bool:
    if not _summary_is_publishable(receipt):
        return False
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run truth-bound ProductGrade verification across all 15 DIO canon extensions."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for canon-extension and supporting Studio ProductGrade receipts.",
    )
    parser.add_argument(
        "--require-proof",
        action="store_true",
        help="Return non-zero unless all 15 canon extensions have verified receipt-bound canon proof.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Return non-zero unless all 15 canon extensions reach full PRODUCT_GRADE_VERIFIED.",
    )
    args = parser.parse_args()
    output_dir = Path(args.output).resolve()
    studio_receipt = run_product_grade_gauntlet(
        output_dir=output_dir / "studio_product_grade",
        root=ROOT,
    )
    receipt = run_canon_extension_product_grade_gauntlet(
        output_dir=output_dir,
        root=ROOT,
        studio_product_grade_receipt=studio_receipt,
    )
    summary_persisted = persist_verified_summary(receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["proof_acceptance_token"])
    print(receipt["acceptance_token"])
    if summary_persisted:
        print(f"DIO_CANON_EXTENSION_CONTROL_DECK_SUMMARY_WRITTEN:{CANONICAL_SUMMARY_PATH}")
    if args.require_proof and receipt["proof_acceptance_token"] != PROOF_VERIFIED_TOKEN:
        return 2
    if args.require_all and receipt["acceptance_token"] != VERIFIED_TOKEN:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
