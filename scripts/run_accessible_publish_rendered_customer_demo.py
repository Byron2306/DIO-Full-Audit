#!/usr/bin/env python3
"""Run a synthetic Accessible Publish case for rendered contrast and focus review."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261102_V8"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    source_html = """<!doctype html>
<html lang="en-ZA"><head><meta charset="utf-8"><title>Rendered accessibility review</title>
<style>.low-contrast { color: #aaa; background: #fff; }
button:focus-visible { outline: none; box-shadow: none; }</style></head>
<body><main><h1>Rendered accessibility review</h1>
<p class="low-contrast">This text is intentionally too light for its white background.</p>
<label for="email">Email address</label><input id="email" type="email">
<button type="button">Continue</button>
</main><script>document.addEventListener('DOMContentLoaded', () => { const b=document.createElement('button'); b.type='button'; b.className='low-contrast'; b.textContent='Dynamic action'; document.querySelector('main').append(b); });</script></body></html>"""
    packet = {
        "owner_authorized": True,
        "case_id": "SYNTHETIC-ACCESSIBLE-PUBLISH-RENDERED",
        "title": "Accessible Publish rendered review",
        "document_title": "Rendered accessibility review",
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
    rendered = review["rendered_browser_review"]
    checks = rendered["issues"]
    if (rendered.get("runtime_state") != "STATIC_AND_SCRIPTED_DOM_NETWORK_BLOCKED"
            or rendered.get("contrast_failure_count", 0) < 1
            or rendered.get("focus_failure_count", 0) < 1
            or not any(row["check"] == "rendered_text_contrast" and row["state"] == "ACTION_REQUIRED" for row in checks)
            or not any(row["check"] == "keyboard_focus_visibility" and row["state"] == "ACTION_REQUIRED" for row in checks)
            or rendered.get("script_execution_isolated") is not True
            or rendered.get("script_network_blocked") is not True
            or rendered.get("script_generated_focusable_delta", 0) < 1
            or receipt.get("release_authorized") is not False
            or receipt.get("conformance_claim") != "NONE"
            or execution.get("release_authorized") is not False
            or execution.get("external_effects") is not False):
        raise ValueError("Accessible Publish rendered review missed a deliberate issue or crossed its held boundary")
    evidence = {
        "schema": "dio.accessible_publish.rendered_execution_evidence.v2",
        "requested_product": "Accessible Publish",
        "run": OUT.relative_to(ROOT).as_posix(),
        "customer_execution_sha256": sha(OUT / "CUSTOMER_EXECUTION_RECEIPT.json"),
        "customer_package_sha256": sha(OUT / "ACCESSIBLE_PUBLISH_RECEIPT.json"),
        "review_sha256": sha(OUT / "ACCESSIBILITY_REVIEW.json"),
        "rendered_review_sha256": sha(OUT / "RENDERED_ACCESSIBILITY_REVIEW.json"),
        "runtime_state": rendered["runtime_state"],
        "scripted_runtime_state": rendered["scripted_runtime_state"],
        "scripted_focusable_control_count": rendered["scripted_focusable_control_count"],
        "script_generated_focusable_delta": rendered["script_generated_focusable_delta"],
        "contrast_failure_count": rendered["contrast_failure_count"],
        "focus_failure_count": rendered["focus_failure_count"],
        "viewport_count": rendered["viewport_count"],
        "horizontal_overflow_viewport_count": rendered["horizontal_overflow_viewport_count"],
        "network_blocked": True,
        "scripts_disabled": False,
        "script_execution_isolated": rendered["script_execution_isolated"],
        "script_network_blocked": rendered["script_network_blocked"],
        "script_observation_window_ms": rendered["scripted_observation_window_ms"],
        "release_authorized": False,
        "external_effects": False,
        "conformance_claim": "NONE",
    }
    evidence_path = OUT / "RENDERED_ACCESSIBILITY_EXECUTION_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
