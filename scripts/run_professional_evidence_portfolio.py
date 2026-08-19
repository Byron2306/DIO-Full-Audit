#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.professional_evidence_corpus import validate_corpus  # noqa: E402
from products.professional_evidence_executor import BLOCKED, FAIL, PASS, execute_customer_case  # noqa: E402
from products.professional_evidence_projection import write_json  # noqa: E402


ACCEPTANCE_TOKEN = "DIO_PROFESSIONAL_EVIDENCE_PORTFOLIO_53_VERIFIED"
DEFAULT_OUTPUT = ROOT / "state" / "professional_evidence" / "portfolio_v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_portfolio(
    output: Path,
    *,
    only: list[str] | None = None,
    online: bool = False,
    operator_id: str = "professional-evidence-harness",
) -> dict:
    corpus = validate_corpus(ROOT)
    canonical = list(corpus["incarnations"])
    selected = canonical if not only else [name for name in canonical if name in set(only)]
    unknown = sorted(set(only or []) - set(canonical))
    if unknown:
        raise ValueError(f"Unknown canonical incarnation(s): {unknown}")
    if not selected:
        raise ValueError("No canonical incarnations selected")

    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for index, incarnation in enumerate(selected, 1):
        print(f"[{index:02d}/{len(selected):02d}] {incarnation}", flush=True)
        try:
            receipt = execute_customer_case(
                incarnation,
                output,
                operator_id=operator_id,
                now=utc_now(),
                online=online,
            )
        except Exception as exc:
            # A harness-level error is itself a hard execution failure; preserve it
            # and continue so one broken product cannot hide the other 52.
            receipt = {
                "schema": "dio.professional_evidence.case_receipt.v2",
                "incarnation": incarnation,
                "status": FAIL,
                "executor": None,
                "product_pipeline_executed": False,
                "authority_created": False,
                "external_effects": False,
                "market_validation_claimed": False,
                "error": f"HARNESS_ERROR {type(exc).__name__}: {exc}",
            }
        results.append(receipt)
        print(f"    {receipt['status']}" + (f" :: {receipt.get('error')}" if receipt.get("error") else ""), flush=True)

    counts = {
        PASS: sum(row.get("status") == PASS for row in results),
        FAIL: sum(row.get("status") == FAIL for row in results),
        BLOCKED: sum(row.get("status") == BLOCKED for row in results),
    }
    all_53_selected = len(selected) == 53 and set(selected) == set(canonical)
    all_passed = all_53_selected and counts[PASS] == 53 and counts[FAIL] == 0 and counts[BLOCKED] == 0
    receipt = {
        "schema": "dio.professional_evidence.portfolio_receipt.v1",
        "generated_at": utc_now(),
        "canonical_portfolio_count": 53,
        "selected_count": len(selected),
        "all_53_selected": all_53_selected,
        "online_current_signal_refresh_enabled": online,
        "counts": counts,
        "all_full_pipeline_verified": all_passed,
        "acceptance_token": ACCEPTANCE_TOKEN if all_passed else None,
        "results": results,
        "full_pipeline_gap_kill_list": [
            {"incarnation": row.get("incarnation"), "error": row.get("error")}
            for row in results
            if row.get("status") == BLOCKED
        ],
        "execution_failure_list": [
            {"incarnation": row.get("incarnation"), "error": row.get("error")}
            for row in results
            if row.get("status") == FAIL
        ],
        "customer_packet_only": all(row.get("golden_fixture_used") is False for row in results if "golden_fixture_used" in row),
        "examiner_truth_used_during_execution": False,
        "market_validation_claimed": False,
        "authority_created": False,
        "external_effects": False,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "claim_boundary": (
            "A PASS proves the configured professional product pipeline processed a literal customer-shaped packet "
            "into its bounded review-ready product artifact under the recorded human/release gates. It does not prove "
            "customer acceptance, willingness to pay, professional certification, legal clearance, regulatory approval, "
            "market demand, external delivery, or real-world domain action unless separately evidenced."
        ),
    }
    write_json(output / "PROFESSIONAL_EVIDENCE_PORTFOLIO_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DIO 53-product Professional Evidence Portfolio Gauntlet")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--only", action="append", default=[], help="Run one canonical incarnation; may be supplied repeatedly")
    parser.add_argument("--online", action="store_true", help="Allow current public-signal retrieval required by Market Radar/Opportunity Foundry")
    parser.add_argument("--operator-id", default="professional-evidence-harness")
    parser.add_argument("--strict", action="store_true", help="Return non-zero unless every selected case passes; full acceptance still requires all 53")
    args = parser.parse_args()
    receipt = run_portfolio(args.output, only=args.only or None, online=args.online, operator_id=args.operator_id)
    summary = {
        "acceptance_token": receipt["acceptance_token"],
        "all_full_pipeline_verified": receipt["all_full_pipeline_verified"],
        "selected_count": receipt["selected_count"],
        "counts": receipt["counts"],
        "full_pipeline_gap_kill_list": receipt["full_pipeline_gap_kill_list"],
        "execution_failure_list": receipt["execution_failure_list"],
        "receipt": str(args.output.resolve() / "PROFESSIONAL_EVIDENCE_PORTFOLIO_RECEIPT.json"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    selected_all_pass = receipt["counts"][FAIL] == 0 and receipt["counts"][BLOCKED] == 0 and receipt["counts"][PASS] == receipt["selected_count"]
    return 0 if (not args.strict or selected_all_pass) else 2


if __name__ == "__main__":
    raise SystemExit(main())
