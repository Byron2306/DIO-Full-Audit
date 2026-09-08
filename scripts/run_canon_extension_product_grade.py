from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canon_extension_materializer import MATERIALIZATION_FILENAME
from products.canon_extension_product_grade import (
    CANON_EXTENSIONS,
    PROOF_VERIFIED_TOKEN,
    VERIFIED_TOKEN,
    run_canon_extension_product_grade_gauntlet,
)
from products.product_grade_gauntlet import run_product_grade_gauntlet


def activate_materialized_provenance() -> None:
    """Point receipt-bound production specs at truthful current materialization receipts.

    The tuple entries are mutable dictionaries. Tests may still exercise historical
    Gamma-style fixture receipts directly, while the production CLI always evaluates
    the current deterministic materialization chain.
    """
    for spec in CANON_EXTENSIONS:
        if spec.get("proof_kind") != "receipt_bound":
            continue
        spec["proof_receipt"] = str(
            Path(str(spec["primary_artifact"])).parent / MATERIALIZATION_FILENAME
        )


def _load_studio_receipt(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid Studio ProductGrade receipt: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Studio ProductGrade receipt must be a JSON object: {path}")
    return value


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
        "--studio-receipt",
        type=Path,
        help=(
            "Existing upstream PRODUCT_GRADE_PORTFOLIO_RECEIPT.json to consume exactly. "
            "When supplied, Studio ProductGrade is not rerun."
        ),
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
    activate_materialized_provenance()
    output_dir = Path(args.output).resolve()
    if args.studio_receipt is not None:
        studio_receipt = _load_studio_receipt(args.studio_receipt.expanduser().resolve())
    else:
        studio_receipt = run_product_grade_gauntlet(
            output_dir=output_dir / "studio_product_grade",
            root=ROOT,
        )
    receipt = run_canon_extension_product_grade_gauntlet(
        output_dir=output_dir,
        root=ROOT,
        studio_product_grade_receipt=studio_receipt,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["proof_acceptance_token"])
    print(receipt["acceptance_token"])
    if args.require_proof and receipt["proof_acceptance_token"] != PROOF_VERIFIED_TOKEN:
        return 2
    if args.require_all and receipt["acceptance_token"] != VERIFIED_TOKEN:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())