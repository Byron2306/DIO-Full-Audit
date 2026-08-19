#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import market_sensorium.cycle as cycle_module  # noqa: E402
from market_sensorium.revalidation import (  # noqa: E402
    STRICT_RESOLVER_VERSION,
    resolve_discovery_candidates_revalidated,
)

# Keep the cycle API stable while replacing its resolver with the stricter MS-1.2
# evidence path. This also means the existing systemd/CLI entrypoint gets the
# revalidation behaviour without granting any new authority.
cycle_module.resolve_discovery_candidates = resolve_discovery_candidates_revalidated
MarketSensoriumCycle = cycle_module.MarketSensoriumCycle


def _apply_ms1_gate(receipt: dict) -> dict:
    """Apply the evidence-bearing MS-1 gate after strict entity revalidation."""
    summary = receipt.get("summary") or {}
    resolution = summary.get("discovery_resolution") or {}
    supersession = summary.get("seed_supersession") or {}
    resolved = int(resolution.get("candidates_resolved") or 0)
    unique_targets = int(resolution.get("unique_resolved_target_hypotheses") or 0)
    seed_supersession = bool(supersession.get("seed_supersession_observed"))
    strict_complete = bool(resolution.get("strict_revalidation_complete"))
    entity_confusion = int(resolution.get("entity_role_confusion") or 0)

    if not strict_complete or entity_confusion != 0:
        gate = "PENDING_STRICT_ENTITY_REVALIDATION"
    elif resolved <= 0 or unique_targets <= 0:
        gate = "PENDING_REAL_ENTITY_RESOLUTION"
    elif not seed_supersession:
        gate = "PENDING_REAL_SEED_SUPERSESSION"
    else:
        gate = "DIO_MARKET_SENSORIUM_DISCOVERY_RESOLUTION_AND_SEED_SUPERSESSION_VERIFIED"

    receipt["ms1_implementation"] = "DIO_MARKET_SENSORIUM_STRICT_SOURCE_AWARE_REVALIDATION_IMPLEMENTED"
    receipt["ms1_acceptance"] = gate
    receipt["ms1_real_entity_resolution_observed"] = resolved > 0 and unique_targets > 0
    receipt["ms1_seed_supersession_observed"] = seed_supersession
    receipt["ms1_strict_revalidation_complete"] = strict_complete
    receipt["ms1_entity_role_confusion"] = entity_confusion
    receipt["ms1_truth"] = {
        "resolver_version": resolution.get("resolver_version") or STRICT_RESOLVER_VERSION,
        "candidates_resolved": resolved,
        "unique_resolved_target_hypotheses": unique_targets,
        "rejected_entity_resolutions": int(resolution.get("rejected_entity_resolutions") or 0),
        "invalidated_this_cycle": int(resolution.get("invalidated_this_cycle") or 0),
        "seed_targets_outranked": int(supersession.get("seed_targets_outranked") or 0),
        "domains_with_seed_supersession": int(
            supersession.get("domains_with_seed_supersession") or 0
        ),
        "strict_revalidation_complete": strict_complete,
        "entity_role_confusion": entity_confusion,
        "publisher_auto_promoted": bool(resolution.get("publisher_auto_promoted", False)),
        "youtube_bare_acronym_auto_promoted": bool(
            resolution.get("youtube_bare_acronym_auto_promoted", False)
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

    receipt_path = ROOT / "state" / "market_sensorium" / "MARKET_SENSORIUM_CYCLE_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
