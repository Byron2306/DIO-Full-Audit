from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.product_grade import ROOT, VERIFIED, evaluate_product_grade_case

BASELINE_TOKEN = "DIO_PRODUCT_GRADE_BASELINE_MEASURED"
VERIFIED_TOKEN = "DIO_PRODUCT_GRADE_VERIFIED"

MANIFESTS = (
    "site_studio.json",
    "professional_correspondence_studio.json",
    "finance_readiness_studio.json",
    "article_publication_studio.json",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def run_product_grade_gauntlet(*, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    studios: dict[str, Any] = {}
    for filename in MANIFESTS:
        manifest_path = root / "config" / "studio_harvest" / filename
        studio_out = output_dir / filename.removesuffix(".json")
        result = evaluate_product_grade_case(manifest_path=manifest_path, output_dir=studio_out, root=root)
        receipt = result["receipt"]
        studios[receipt["studio_id"]] = {
            "status": receipt["status"],
            "score": receipt["score"],
            "threshold": receipt["threshold"],
            "critical_blockers": receipt["critical_blockers"],
            "buyer_grade_candidate": receipt["buyer_grade_candidate"],
            "primary_artifact_sha256": receipt["primary_artifact_sha256"],
            "receipt_fingerprint": receipt["receipt_fingerprint"],
            "beast_mechanical_pass": bool(receipt["beast_artifact_checks"].get("mechanical_pass")),
            "customers_will_pay": receipt["customers_will_pay"],
            "verified_payment": receipt["verified_payment"],
        }
    verified_count = sum(1 for row in studios.values() if row["status"] == VERIFIED)
    all_verified = verified_count == len(studios)
    receipt = {
        "schema": "dio.product_grade.portfolio_gauntlet_receipt.v1",
        "acceptance_token": VERIFIED_TOKEN if all_verified else BASELINE_TOKEN,
        "studio_count": len(studios),
        "product_grade_verified_count": verified_count,
        "product_grade_refuse_count": len(studios) - verified_count,
        "all_product_grade_verified": all_verified,
        "studios": studios,
        "external_effects": False,
        "authority_created": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": "Portfolio ProductGrade is controlled output verification. Real willingness to pay remains unproved until observed.",
    }
    receipt["portfolio_fingerprint"] = _fingerprint(receipt)
    target = output_dir / "PRODUCT_GRADE_PORTFOLIO_RECEIPT.json"
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
