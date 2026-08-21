#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.professional_evidence_native_routes import NATIVE_ENGINE_ROUTES, load_native_contract  # noqa: E402
from products.professional_evidence_vesper_gate import execute_customer_case_via_vesper  # noqa: E402


def main() -> int:
    contract = load_native_contract()
    by_incarnation = {
        str(row["incarnation"]): (route_name, row)
        for route_name, row in (contract.get("routes") or {}).items()
    }

    parser = argparse.ArgumentParser(description="Run one canonical mature product through Vesper and require its declared native engine.")
    parser.add_argument("--product", required=True, choices=sorted(by_incarnation))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--operator-id", default="native-route-canary")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    route_name, route_contract = by_incarnation[args.product]
    expected = str(route_contract["native_engine"])
    if NATIVE_ENGINE_ROUTES.get(route_name) != expected:
        raise RuntimeError("native route runtime map does not match the versioned contract")

    receipt = execute_customer_case_via_vesper(
        args.product,
        output,
        operator_id=args.operator_id,
        online=args.online,
    )

    checks = {
        "status_pass": receipt.get("status") == "PASS_FULL_PIPELINE",
        "vesper_front_door": receipt.get("vesper_web_chat_front_door_verified") is True,
        "quarantined_bytes_consumed": receipt.get("product_consumed_vesper_quarantined_bytes") is True,
        "native_engine_required": receipt.get("native_engine_required") is True,
        "native_engine_identity": expected in str(receipt.get("native_engine_identity") or receipt.get("executor") or ""),
        "native_capability_preserved": receipt.get("native_capability_preserved") is True,
        "surrogate_fallback_forbidden": receipt.get("surrogate_fallback_allowed") is False,
        "surrogate_fallback_unused": receipt.get("surrogate_fallback_used") is False,
        "authority_not_created": receipt.get("authority_created") is False,
        "external_effects_absent": receipt.get("external_effects") is False,
    }
    passed = all(checks.values())
    result = {
        "product": args.product,
        "route": route_name,
        "expected_native_engine": expected,
        "observed_executor": receipt.get("executor"),
        "observed_native_engine_identity": receipt.get("native_engine_identity"),
        "terminal_artifact_kind": receipt.get("terminal_artifact_kind"),
        "passed": passed,
        "checks": checks,
        "error": receipt.get("error") or "",
        "receipt": str(output / args.product.casefold().replace(" ", "-") / "PROFESSIONAL_EVIDENCE_RECEIPT.json"),
    }
    print(json.dumps(result, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
