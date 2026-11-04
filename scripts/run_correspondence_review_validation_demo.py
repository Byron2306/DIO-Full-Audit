#!/usr/bin/env python3
"""Run both correspondence products and validate their blank review handoffs."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/CORRESPONDENCE_EDITOR_REVIEW_VALIDATION_20261102_V4"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    from products.customer_product_router import run_customer_product
    from validate_correspondence_editorial_review import validate

    packet = json.loads((ROOT / "config/customer_products/examples/correspondence.json").read_text(encoding="utf-8"))
    packet["owner_authorized"] = True
    executions = []
    for product in ("Professional Correspondence", "Professional Correspondence Studio"):
        folder = "professional-correspondence" if product == "Professional Correspondence" else "professional-correspondence-studio"
        run_dir = OUT / folder
        result = run_customer_product(product, packet, run_dir, render_pdf=False)
        package = json.loads((run_dir / "CUSTOMER_PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
        output_map = {row["path"]: run_dir / row["path"] for row in package.get("outputs", [])}
        worksheet = output_map["CORRESPONDENCE_EDITOR_REVIEW.csv"]
        bindings = output_map["CORRESPONDENCE_SOURCE_BYTE_BINDINGS.json"]
        guide = output_map["CORRESPONDENCE_EDITOR_REVIEW_GUIDE.md"]
        review_html = output_map["CORRESPONDENCE_EDITOR_REVIEW.html"]
        validation = validate(worksheet, bindings)
        validation_path = run_dir / "CORRESPONDENCE_EDITOR_REVIEW_VALIDATION.json"
        validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if (validation.get("state") != "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED"
                or validation.get("send_authorized") is not False
                or result.get("release_authorized") is not False
                or result.get("external_effects") is not False):
            raise ValueError(f"{product} review validator failed to hold the blank worksheet")
        executions.append({
            "product_name": product,
            "customer_execution_sha256": sha(run_dir / "CUSTOMER_EXECUTION_RECEIPT.json"),
            "customer_package_sha256": sha(run_dir / "CUSTOMER_PACKAGE_RECEIPT.json"),
            "worksheet_sha256": sha(worksheet), "bindings_sha256": sha(bindings),
            "guide_sha256": sha(guide), "review_html_sha256": sha(review_html),
            "validation_sha256": sha(validation_path),
            "validation_state": validation["state"],
            "send_authorized": validation["send_authorized"],
        })
    evidence = {
        "schema": "dio.professional_correspondence.review_validation_evidence.v1",
        "run": OUT.relative_to(ROOT).as_posix(),
        "products": executions,
        "all_blank_reviews_held": all(row["validation_state"] == "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED" for row in executions),
        "all_send_authority_false": all(row["send_authorized"] is False for row in executions),
        "synthetic_acceptance_input": True,
    }
    evidence_path = OUT / "CORRESPONDENCE_REVIEW_VALIDATION_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
