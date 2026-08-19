#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import market_sensorium.cycle as cycle_module  # noqa: E402
from market_sensorium.mail_refresh import refresh_mail_ingress_with_coverage  # noqa: E402
from market_sensorium.revalidation import (  # noqa: E402
    STRICT_RESOLVER_VERSION,
    resolve_discovery_candidates_revalidated,
)
from market_sensorium.temporal_ingest import ingest_existing_prospects_temporal  # noqa: E402

# Keep the cycle API stable while replacing its resolver with the stricter MS-1.2
# evidence path and its prospect ingestion with MS-2 coverage-bound commercial
# time. Neither replacement creates outbound authority.
cycle_module.resolve_discovery_candidates = resolve_discovery_candidates_revalidated
cycle_module.ingest_existing_prospects = ingest_existing_prospects_temporal


def _refresh_mail_with_coverage(self):
    return refresh_mail_ingress_with_coverage(self.root)


cycle_module.MarketSensoriumCycle.refresh_mail_ingress = _refresh_mail_with_coverage
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


def _apply_ms2_gate(receipt: dict) -> dict:
    """Apply the MS-2 commercial-time truth gate.

    A clock value alone cannot become a no-reply observation. Real no-reply truth
    requires prospective continuous inbox coverage; replies remain direct evidence.
    """
    summary = receipt.get("summary") or {}
    prospects = summary.get("prospects") or {}
    commercial = prospects.get("commercial_time") or {}
    sent = int(commercial.get("sent_targets") or prospects.get("sent") or 0)
    replies = int(commercial.get("reply_observed") or 0)
    no_reply = int(commercial.get("no_reply_observed") or 0)
    penalized = int(commercial.get("temporal_penalized_targets") or 0)
    insufficient = int(commercial.get("coverage_insufficient") or 0)
    unsupported = int(commercial.get("unsupported_no_reply_inferences") or 0)
    coverage_state = str(commercial.get("coverage_state") or "UNAVAILABLE").upper()
    coverage_continuous = coverage_state == "CONTINUOUS"
    real_temporal_effect = replies > 0 or penalized > 0

    if sent <= 0:
        gate = "PENDING_SENT_MAIL_EVIDENCE"
    elif unsupported > 0:
        gate = "REFUSE_UNSUPPORTED_NO_REPLY_INFERENCE"
    elif not coverage_continuous:
        gate = "PENDING_MAIL_OBSERVATION_COVERAGE"
    elif insufficient > 0:
        gate = "PENDING_COMPLETE_MAIL_OBSERVATION_COVERAGE"
    elif not real_temporal_effect:
        gate = "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_OBSERVATION_ACTIVE"
    else:
        gate = "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_AND_REPLY_TRUTH_VERIFIED"

    receipt["ms2_implementation"] = "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_TRUTH_IMPLEMENTED"
    receipt["ms2_acceptance"] = gate
    receipt["ms2_truth"] = {
        "coverage_state": coverage_state,
        "coverage_kind": commercial.get("coverage_kind"),
        "continuous_from": commercial.get("continuous_from"),
        "last_successful_sync_at": commercial.get("last_successful_sync_at"),
        "sent_targets": sent,
        "reply_observed": replies,
        "no_reply_observed": no_reply,
        "temporal_penalized_targets": penalized,
        "coverage_insufficient": insufficient,
        "unsupported_no_reply_inferences": unsupported,
        "age_only_silence_inference_allowed": False,
        "silence_requires_observation_coverage": True,
        "retroactive_no_reply_claim_allowed": False,
        "followup_authority_created": False,
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
        help="Pull inbound Outlook mail and extend prospective reply-observation coverage before calculating commercial time.",
    )
    args = parser.parse_args()
    receipt = MarketSensoriumCycle(ROOT).run(
        refresh_public=args.refresh_public,
        refresh_mail=args.refresh_mail,
    )
    receipt = _apply_ms1_gate(receipt)
    receipt = _apply_ms2_gate(receipt)

    receipt_path = ROOT / "state" / "market_sensorium" / "MARKET_SENSORIUM_CYCLE_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
