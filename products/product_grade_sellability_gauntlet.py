from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.product_grade_gauntlet import MANIFESTS
from products.product_grade_sellability import (
    SELLABILITY_VERIFIED,
    evaluate_product_sellability_case,
)
from products.product_grade_v2 import ROOT


BASELINE_TOKEN = "DIO_PRODUCT_SELLABILITY_BASELINE_MEASURED"
VERIFIED_TOKEN = "DIO_PRODUCT_SELLABILITY_VERIFIED"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def run_product_sellability_gauntlet(*, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    studios: dict[str, Any] = {}
    for filename in MANIFESTS:
        manifest_path = root / "config" / "studio_harvest" / filename
        studio_out = output_dir / filename.removesuffix(".json")
        result = evaluate_product_sellability_case(
            manifest_path=manifest_path,
            output_dir=studio_out,
            root=root,
        )
        row = result["receipt"]
        studios[str(row["studio_id"])] = {
            "sellability_status": row["sellability_status"],
            "product_grade_status": row["product_grade_status"],
            "product_grade_score": row["product_grade_score"],
            "critical_blockers": row["critical_blockers"],
            "semantic_visual_projection": row["semantic_visual_projection"]["checks"],
            "receipt_fingerprint": row["receipt_fingerprint"],
            "buyer_grade_candidate": row["buyer_grade_candidate"],
        }

    verified_count = sum(1 for row in studios.values() if row["sellability_status"] == SELLABILITY_VERIFIED)
    all_verified = verified_count == len(studios)
    receipt = {
        "schema": "dio.product_grade.sellability_portfolio_gauntlet_receipt.v1",
        "acceptance_token": VERIFIED_TOKEN if all_verified else BASELINE_TOKEN,
        "studio_count": len(studios),
        "sellability_verified_count": verified_count,
        "sellability_refuse_count": len(studios) - verified_count,
        "all_sellability_verified": all_verified,
        "studios": studios,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "This gauntlet verifies controlled buyer-facing artifacts and semantic-visual custody. "
            "Real willingness to pay and repeatable commercial outcomes remain unproved until observed."
        ),
    }
    receipt["portfolio_fingerprint"] = _fingerprint(receipt)
    target = output_dir / "PRODUCT_SELLABILITY_PORTFOLIO_RECEIPT.json"
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


__all__ = ["run_product_sellability_gauntlet"]
