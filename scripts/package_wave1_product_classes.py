#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT_BOOTSTRAP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_BOOTSTRAP))

from scripts import _package_wave1_product_classes_legacy as legacy  # noqa: E402
from scripts.product_class_packaging_truth import truth_gate_package  # noqa: E402


ROOT = legacy.ROOT
PACKAGE_ROOT = legacy.PACKAGE_ROOT
DELIVERABLE_ROOT = legacy.DELIVERABLE_ROOT
SITE_ROOT = legacy.SITE_ROOT
PUBLIC_ROOT_URL = legacy.PUBLIC_ROOT_URL
PRODUCTS = legacy.PRODUCTS
_legacy_package_one = legacy.package_one


def package_one(name: str, row: dict[str, Any], plan: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    result = _legacy_package_one(name, row, plan, spec)
    return truth_gate_package(
        root=ROOT,
        package_root=PACKAGE_ROOT,
        deliverable_root=DELIVERABLE_ROOT,
        site_root=SITE_ROOT,
        result=result,
    )


def build_index_page(packages: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f"<tr><td><strong>{item['name']}</strong></td><td>structural proof</td><td>typed route required</td><td>public launch held</td></tr>"
        for item in packages
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DIO Product Class Registry</title>
  <style>
    body {{ margin:0; font-family:Arial, Helvetica, sans-serif; color:#14202e; background:#f7f9fc; }}
    header, main {{ max-width:1100px; margin:0 auto; padding:28px 5vw; }}
    header {{ background:white; border-bottom:1px solid #c8d3df; }}
    h1 {{ color:#0d3b66; }}
    .notice {{ padding:16px; background:#fff3cd; border:1px solid #e5c07b; margin:20px 0; }}
    table {{ width:100%; border-collapse:collapse; background:white; }}
    th,td {{ border:1px solid #c8d3df; padding:10px; text-align:left; }}
    th {{ background:#eaf1f8; }}
    a {{ color:#0d3b66; font-weight:700; }}
  </style>
</head>
<body>
<header><a href="{PUBLIC_ROOT_URL}">DIO Workflows</a><h1>DIO Product Class Registry</h1></header>
<main>
  <div class="notice"><strong>Evidence boundary:</strong> these Wave 1 entries are structural product profiles, not execution-proven public products. Individual product pages remain held until a typed route has run successfully and a public-safe proof artifact exists.</div>
  <table><thead><tr><th>Product class</th><th>Evidence</th><th>Route</th><th>Release</th></tr></thead><tbody>{rows}</tbody></table>
</main>
</body>
</html>
"""


def build_report(receipt: dict[str, Any]) -> str:
    lines = [
        "# Wave 1 Product Class Structural Packaging",
        "",
        f"Generated: `{receipt['generated_at']}`",
        "",
        "## Result",
        "",
        "Wave 1 generated structural product profiles and synthetic demonstrations. This does **not** prove that the typed fulfilment routes executed successfully, and it does not authorize public launch.",
        "",
        "| Product class | Evidence level | Public launch | Structural package |",
        "| --- | --- | --- | --- |",
    ]
    for item in receipt.get("packages", []):
        lines.append(f"| {item['name']} | structural proof | held | `{item['zip_path']}` |")
    lines.extend([
        "",
        "## Next Gate",
        "",
        "Each class requires an approved typed route, a successful controlled execution receipt, a reviewed output artifact, and a public-safe proof artifact before it may be promoted as a controlled-pilot public product.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    previous_package = legacy.package_one
    previous_index = legacy.build_index_page
    previous_report = legacy.build_report
    legacy.package_one = package_one
    legacy.build_index_page = build_index_page
    legacy.build_report = build_report
    try:
        return legacy.main()
    finally:
        legacy.package_one = previous_package
        legacy.build_index_page = previous_index
        legacy.build_report = previous_report


if __name__ == "__main__":
    raise SystemExit(main())
