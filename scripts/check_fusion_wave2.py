#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from frameworks.engine import load_catalog

EXPECTED_SOURCE_SYSTEMS = {
    "legalis",
    "homs",
    "phoenix",
    "commerce_autorelease",
    "market_command",
    "dio_product_platform",
}
EXPECTED_PRODUCTS = {
    "dio_assurance",
    "dio_agent_authority",
    "dio_vendorproof",
    "dio_accreditation",
    "dio_tenderproof",
    "dio_grantproof",
    "dio_research_integrity",
    "dio_regops",
    "dio_capitalroom",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DIO Fusion Wave 2 Framework Engine readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    blockers: list[dict[str, str]] = []

    fusion1_path = workspace / "receipts" / "fusion-wave1-latest.json"
    if not fusion1_path.is_file():
        blockers.append({"code": "FUSION_WAVE1_RECEIPT_MISSING", "message": str(fusion1_path)})
        fusion1 = {}
    else:
        try:
            fusion1 = json.loads(fusion1_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            blockers.append({"code": "FUSION_WAVE1_RECEIPT_INVALID", "message": str(exc)})
            fusion1 = {}
    if fusion1.get("state") != "FUSION_WAVE1_READY":
        blockers.append({"code": "FUSION_WAVE1_NOT_READY", "message": f"Observed state: {fusion1.get('state')!r}"})

    try:
        catalog = load_catalog(core / "config" / "dio_framework_catalog.json")
    except Exception as exc:
        blockers.append({"code": "FRAMEWORK_CATALOG_INVALID", "message": f"{type(exc).__name__}: {exc}"})
        catalog = {"frameworks": []}

    frameworks = catalog.get("frameworks") or []
    source_systems = {str(row.get("source_system")) for row in frameworks}
    missing_systems = sorted(EXPECTED_SOURCE_SYSTEMS - source_systems)
    if missing_systems:
        blockers.append({"code": "FRAMEWORK_SOURCE_FAMILY_MISSING", "message": ", ".join(missing_systems)})

    product_framework = next((row for row in frameworks if row.get("framework_id") == "dio.product.platform"), None)
    product_scope = set(((product_framework or {}).get("scope") or {}).get("products") or [])
    missing_products = sorted(EXPECTED_PRODUCTS - product_scope)
    if missing_products:
        blockers.append({"code": "PRODUCT_FRAMEWORK_COVERAGE_MISSING", "message": ", ".join(missing_products)})

    for framework in frameworks:
        for rule in framework.get("requirements") or []:
            forbidden = {"kernel_authorized", "external_release_authorized", "execution_authorized", "execute", "gate_state"}
            present = forbidden.intersection(rule)
            if present:
                blockers.append({
                    "code": "FRAMEWORK_RULE_AUTHORITY_ESCALATION_FIELD",
                    "message": f"{framework.get('framework_id')}:{rule.get('rule_id')} contains {sorted(present)}",
                })

    state = "FUSION_WAVE2_READY" if not blockers else "BLOCKED"
    receipt = {
        "schema": "dio.fusion.wave2.receipt.v1",
        "state": state,
        "depends_on": {
            "fusion_wave1_state": fusion1.get("state"),
            "fusion_wave1_receipt": str(fusion1_path),
        },
        "frameworks": len(frameworks),
        "source_systems": sorted(source_systems),
        "product_routes_covered": sorted(product_scope),
        "laws": {
            "requirements_do_not_create_authority": True,
            "frameworks_do_not_execute": True,
            "specialist_sources_remain_traceable": True,
        },
        "blockers": blockers,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": state,
        "frameworks": len(frameworks),
        "source_systems": len(source_systems),
        "blockers": blockers,
        "receipt": str(out),
    }, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
