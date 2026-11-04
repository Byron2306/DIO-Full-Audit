#!/usr/bin/env python3
"""Run a synthetic Accessible Publish packet with valid and broken semantics."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261101_V3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    source_html = """<!doctype html>
<html lang="en-ZA"><head><meta charset="utf-8"><title>Accessible form review</title></head>
<body><main><h1>Accessible form review</h1>
<label>Email address <input id="email" type="email"></label>
<input type="hidden" name="csrf" value="synthetic">
<div aria-hidden="true"><button id="hidden-action">Hidden action</button></div>
<span id="account-label">Account reference</span><input id="account" aria-labelledby="account-label">
<input id="broken" aria-labelledby="missing-label">
<a href="/documents"></a>
<div id="duplicate">First id</div><div id="duplicate">Second id</div>
</main></body></html>"""
    packet = {
        "owner_authorized": True,
        "case_id": "SYNTHETIC-ACCESSIBLE-PUBLISH-SEMANTICS",
        "title": "Accessible Publish semantics review",
        "document_title": "Accessible form review",
        "primary_language": "en-ZA",
        "source_html": source_html,
        "image_descriptions": {},
        "decorative_images": [],
        "controlled_synthetic_demo": True,
    }
    from products.customer_product_router import run_customer_product

    execution = run_customer_product("Accessible Publish", packet, OUT, render_pdf=False)
    receipt = json.loads((OUT / "ACCESSIBLE_PUBLISH_RECEIPT.json").read_text(encoding="utf-8"))
    review = json.loads((OUT / "ACCESSIBILITY_REVIEW.json").read_text(encoding="utf-8"))
    before = review["before"]
    checks = [row for row in before["issues"]]
    if (before.get("form_control_count") != 3 or before.get("hidden_control_count") != 1
            or any(row["check"] == "form_control_name" and "email" in row["detail"] for row in checks)
            or any(row["check"] == "form_control_name" and "account" in row["detail"] for row in checks)
            or not any(row["check"] == "aria_labelledby_reference" and "broken" in row["detail"] for row in checks)
            or not any(row["check"] == "link_purpose" and row["state"] == "ACTION_REQUIRED" for row in checks)
            or not any(row["check"] == "duplicate_id" and row["state"] == "ACTION_REQUIRED" for row in checks)
            or not any(row["check"] == "focusable_content_hidden_from_accessibility_tree" and row["state"] == "ACTION_REQUIRED" and "hidden-action" in row["detail"] for row in checks)
            or receipt.get("release_authorized") is not False
            or execution.get("release_authorized") is not False
            or execution.get("external_effects") is not False):
        raise ValueError("Accessible Publish semantics review failed its control/held-release boundary")
    evidence = {
        "schema": "dio.accessible_publish.semantic_inventory_execution.v1",
        "requested_product": "Accessible Publish",
        "run": OUT.relative_to(ROOT).as_posix(),
        "customer_execution_sha256": sha(OUT / "CUSTOMER_EXECUTION_RECEIPT.json"),
        "customer_package_sha256": sha(OUT / "ACCESSIBLE_PUBLISH_RECEIPT.json"),
        "review_sha256": sha(OUT / "ACCESSIBILITY_REVIEW.json"),
        "form_controls_detected": before["form_control_count"],
        "hidden_controls_excluded": before["hidden_control_count"],
        "implicit_label_recognized": True,
        "valid_aria_labelledby_recognized": True,
        "broken_aria_labelledby_flagged": True,
        "empty_link_flagged": True,
        "duplicate_ids_flagged": True,
        "focusable_descendant_of_aria_hidden_flagged": True,
        "release_authorized": False,
        "external_effects": False,
        "conformance_claim": "NONE",
    }
    evidence_path = OUT / "SEMANTIC_INVENTORY_EXECUTION_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
