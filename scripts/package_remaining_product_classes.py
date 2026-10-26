#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT_BOOTSTRAP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_BOOTSTRAP))

from scripts import _package_remaining_product_classes_legacy as legacy  # noqa: E402
from scripts.product_class_packaging_truth import truth_gate_package  # noqa: E402


ROOT = legacy.ROOT
PACKAGE_ROOT = legacy.PACKAGE_ROOT
DELIVERABLE_ROOT = legacy.DELIVERABLE_ROOT
SITE_ROOT = legacy.SITE_ROOT
PUBLIC_ROOT_URL = legacy.PUBLIC_ROOT_URL
_legacy_package_one = legacy.package_one


def package_one(row: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    result = _legacy_package_one(row, plan)
    return truth_gate_package(
        root=ROOT,
        package_root=PACKAGE_ROOT,
        deliverable_root=DELIVERABLE_ROOT,
        site_root=SITE_ROOT,
        result=result,
    )


def build_index_page(cards: list[dict[str, str]]) -> str:
    rows = "\n".join(
        f"<tr><td><strong>{item['name']}</strong></td><td>{item.get('wave','')}</td><td>structural proof</td><td>typed route required</td><td>public launch held</td></tr>"
        for item in cards
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DIO Product Class Registry</title>
  <style>
    body {{ margin:0; font-family:Arial, Helvetica, sans-serif; color:#14202e; background:#f7f9fc; }}
    header, main {{ max-width:1200px; margin:0 auto; padding:28px 5vw; }}
    header {{ background:white; border-bottom:1px solid #c8d3df; }}
    h1 {{ color:#0d3b66; }}
    .notice {{ padding:16px; background:#fff3cd; border:1px solid #e5c07b; margin:20px 0; line-height:1.5; }}
    table {{ width:100%; border-collapse:collapse; background:white; }}
    th,td {{ border:1px solid #c8d3df; padding:10px; text-align:left; vertical-align:top; }}
    th {{ background:#eaf1f8; }}
    a {{ color:#0d3b66; font-weight:700; }}
  </style>
</head>
<body>
<header><a href="{PUBLIC_ROOT_URL}">DIO Workflows</a><h1>DIO Product Class Registry</h1></header>
<main>
  <div class="notice"><strong>Evidence boundary:</strong> product-class packaging proves profile structure, intake shape, authority boundaries and example output forms. It does not prove an executable fulfilment route. Public leaf pages and “Request Pilot” links remain held until a controlled execution receipt and public-safe proof artifact exist.</div>
  <table><thead><tr><th>Product class</th><th>Wave</th><th>Evidence</th><th>Route</th><th>Release</th></tr></thead><tbody>{rows}</tbody></table>
</main>
</body>
</html>
"""


def report(receipt: dict[str, Any]) -> str:
    lines = [
        "# Remaining Product Class Structural Packaging",
        "",
        f"Generated: `{receipt['generated_at']}`",
        "",
        "## Result",
        "",
        f"Generated structural packages for `{receipt['summary']['products_packaged']}` atlas product classes. These packages are **not execution proof** and are not public-launch authorization.",
        "",
        "| Product class | Wave | Risk boundary | Evidence level | Public launch | Structural zip |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in receipt.get("packages", []):
        lines.append(f"| {item['name']} | {item.get('wave','')} | {item.get('risk_family','')} | structural proof | held | `{item['zip_path']}` |")
    lines.extend([
        "",
        "## Operator Boundary",
        "",
        "Do not market these classes as execution-ready. Each class needs an approved typed route, a successful controlled execution receipt, a reviewed output artifact, and a public-safe proof artifact before a public product page may be released.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    previous_package = legacy.package_one
    previous_index = legacy.build_index_page
    previous_report = legacy.report
    legacy.package_one = package_one
    legacy.build_index_page = build_index_page
    legacy.report = report
    try:
        result = legacy.main()
        # The legacy receipt says "all_smoke_passed". Preserve compatibility but make the
        # evidence level explicit in the persisted receipt if it exists.
        if legacy.RECEIPT_PATH.exists():
            receipt = legacy.read_json(legacy.RECEIPT_PATH)
            receipt["schema"] = "dio.remaining_product_classes_packaging_receipt.v2"
            receipt["summary"]["evidence_level"] = "structural_proof"
            receipt["summary"]["execution_proof"] = False
            receipt["summary"]["public_launch_ready"] = False
            receipt["summary"]["all_smoke_passed"] = False
            receipt["summary"]["structural_smoke_passed"] = all(item.get("result") == "structural_proof_packaged" for item in receipt.get("packages", []))
            legacy.write_json(legacy.RECEIPT_PATH, receipt)
        return result
    finally:
        legacy.package_one = previous_package
        legacy.build_index_page = previous_index
        legacy.report = previous_report


if __name__ == "__main__":
    raise SystemExit(main())
