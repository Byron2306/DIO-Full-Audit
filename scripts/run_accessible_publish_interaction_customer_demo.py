#!/usr/bin/env python3
"""Exercise a synthetic disclosure button in the isolated Accessible Publish review."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261102_V9"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    source_html = """<!doctype html>
<html lang="en-ZA"><head><meta charset="utf-8"><title>Accessible Publish interaction review</title></head>
<body><main><h1>Interaction review</h1>
<button id="details-toggle" type="button" aria-expanded="false" aria-controls="details">Show details</button>
<section id="details" hidden><h2>Details</h2><p>Additional source information becomes visible after activation.</p></section>
<script>
const button=document.querySelector('#details-toggle');
button.addEventListener('click',()=>{
  const panel=document.querySelector('#details');
  const expanded=button.getAttribute('aria-expanded')==='true';
  button.setAttribute('aria-expanded',String(!expanded));
  button.textContent=expanded?'Show details':'Hide details';
  panel.hidden=expanded;
});
</script></main></body></html>"""
    packet = {
        "owner_authorized": True,
        "case_id": "SYNTHETIC-ACCESSIBLE-PUBLISH-BUTTON-INTERACTION",
        "title": "Accessible Publish bounded interaction review",
        "document_title": "Accessible Publish interaction review",
        "primary_language": "en-ZA",
        "source_html": source_html,
        "image_descriptions": {},
        "decorative_images": [],
        "controlled_synthetic_demo": True,
    }
    from products.customer_product_router import run_customer_product

    execution = run_customer_product("Accessible Publish", packet, OUT, render_pdf=False)
    receipt_path = OUT / "ACCESSIBLE_PUBLISH_RECEIPT.json"
    review_path = OUT / "ACCESSIBILITY_REVIEW.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    rendered = review["rendered_browser_review"]
    changes = [row for row in rendered.get("scripted_button_interaction_reviews", [])
               if row.get("text_changed") or row.get("controlled_content_visible")
               or row.get("aria_expanded_before") != row.get("aria_expanded_after")]
    if (rendered.get("scripted_button_interaction_count", 0) < 1
            or not changes
            or not any(row.get("controlled_content_visible") for row in changes)
            or rendered.get("script_network_blocked") is not True
            or receipt.get("release_authorized") is not False
            or receipt.get("conformance_claim") != "NONE"
            or execution.get("release_authorized") is not False
            or execution.get("external_effects") is not False):
        raise ValueError("Accessible Publish bounded interaction review missed the synthetic disclosure or crossed the held boundary")

    evidence = {
        "schema": "dio.accessible_publish.interaction_execution_evidence.v1",
        "product": "Accessible Publish",
        "run": OUT.relative_to(ROOT).as_posix(),
        "controlled_synthetic_demo": True,
        "button_interaction_count": rendered["scripted_button_interaction_count"],
        "button_interaction_change_count": rendered["scripted_button_interaction_change_count"],
        "controlled_content_visible_after_activation": True,
        "network_blocked": True,
        "release_authorized": False,
        "external_effects": False,
        "conformance_claim": "NONE",
        "receipt_sha256": sha(receipt_path),
        "review_sha256": sha(review_path),
    }
    evidence_path = OUT / "INTERACTION_EXECUTION_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
