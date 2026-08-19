#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.cycle import MarketSensoriumCycle  # noqa: E402


def _apply_ms1_gate(receipt: dict) -> dict:
    """Replace implementation-ready wording with an evidence-bearing MS-1 gate."""
    summary = receipt.get("summary") or {}
    resolution = summary.get("discovery_resolution") or {}
    supersession = summary.get("seed_supersession") or {}
    resolved = int(resolution.get("candidates_resolved") or 0)
    seed_supersession = bool(supersession.get("seed_supersession_observed"))

    if resolved <= 0:
        gate = "PENDING_REAL_ENTITY_RESOLUTION"
    elif not seed_supersession:
        gate = "PENDING_REAL_SEED_SUPERSESSION"
    else:
        gate = "DIO_MARKET_SENSORIUM_DISCOVERY_RESOLUTION_AND_SEED_SUPERSESSION_VERIFIED"

    receipt["ms1_implementation"] = "DIO_MARKET_SENSORIUM_SOURCE_AWARE_RESOLUTION_IMPLEMENTED"
    receipt["ms1_acceptance"] = gate
    receipt["ms1_real_entity_resolution_observed"] = resolved > 0
    receipt["ms1_seed_supersession_observed"] = seed_supersession
    receipt["ms1_truth"] = {
        "resolver_version": resolution.get("resolver_version"),
        "candidates_resolved": resolved,
        "unique_resolved_target_hypotheses": int(
            resolution.get("unique_resolved_target_hypotheses") or 0
        ),
        "seed_targets_outranked": int(supersession.get("seed_targets_outranked") or 0),
        "domains_with_seed_supersession": int(
            supersession.get("domains_with_seed_supersession") or 0
        ),
        "buyer_units_verified": int(resolution.get("buyer_units_verified") or 0),
        "leads_created": int(resolution.get("leads_created") or 0),
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "authority_created": False,
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the read-only DIO Market Sensorium cycle with temporal memory, ATLAS baselines and Hivenance observations."
    )
    parser.add_argument(
        "--refresh-public",
        action="store_true",
        help="Refresh the already-governed YouTube/RSS market intelligence lane before ingesting evidence.",
    )
    parser.add_argument(
        "--refresh-mail",
        action="store_true",
        help="Pull inbound Outlook mail through the already-configured Microsoft Graph lane before calculating reply/silence state.",
    )
    args = parser.parse_args()
    receipt = MarketSensoriumCycle(ROOT).run(
        refresh_public=args.refresh_public,
        refresh_mail=args.refresh_mail,
    )
    receipt = _apply_ms1_gate(receipt)

    # MarketSensoriumCycle already persists the cycle receipt. Rewrite the same
    # top-level projection with the evidence-bearing MS-1 gate so the CLI and
    # persisted JSON cannot report "READY" when real entity resolution is zero.
    receipt_path = ROOT / "state" / "market_sensorium" / "MARKET_SENSORIUM_CYCLE_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
