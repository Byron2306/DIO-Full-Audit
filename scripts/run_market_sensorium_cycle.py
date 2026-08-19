#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import market_sensorium.cycle as cycle_module  # noqa: E402
from market_sensorium.commercial_phoenix import install_commercial_phoenix_runtime  # noqa: E402
from market_sensorium.competitive_offers import observe_competitive_offers  # noqa: E402
from market_sensorium.mail_refresh import refresh_mail_ingress_with_coverage  # noqa: E402
from market_sensorium.rank_transitions import install_rank_transition_runtime  # noqa: E402
from market_sensorium.revalidation import (  # noqa: E402
    STRICT_RESOLVER_VERSION,
    resolve_discovery_candidates_revalidated,
)
from market_sensorium.temporal_ingest import ingest_existing_prospects_temporal  # noqa: E402

# Keep the cycle API stable while replacing its resolver with the stricter MS-1.2
# evidence path and its prospect ingestion with MS-2 coverage-bound commercial
# time. MS-3 wraps the existing rank API to preserve prior state and construct
# source-bound dynamic rank-transition receipts. MS-4 wraps that completed MS-3
# pass and forms rival, source-bound Hivenance commercial hypotheses whose selected
# tests are read-only research only. MS-5 then observes provider-owned public offer
# evidence and explicit asking-price language without promoting either to demand,
# willingness to pay, seller-to-target identity, or execution authority.
cycle_module.resolve_discovery_candidates = resolve_discovery_candidates_revalidated
cycle_module.ingest_existing_prospects = ingest_existing_prospects_temporal
install_rank_transition_runtime(cycle_module.MarketSensoriumStore)
install_commercial_phoenix_runtime(cycle_module.MarketSensoriumStore)


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
    """Apply the MS-2 commercial-time truth gate."""
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


def _apply_ms3_gate(receipt: dict) -> dict:
    """Apply the live evidence-bearing dynamic rank-movement gate."""
    summary = receipt.get("summary") or {}
    store_summary = summary.get("store") or {}
    transitions = store_summary.get("rank_transitions") or {}
    summary["rank_transitions"] = transitions

    recorded = int(transitions.get("transitions_recorded") or 0)
    historical = int(transitions.get("historical_transitions") or 0)
    movements = int(transitions.get("rank_movement_transitions") or 0)
    evidence_bound = int(transitions.get("evidence_bound_transitions") or 0)
    movement_evidence_bound = int(
        transitions.get("rank_movement_evidence_bound_transitions") or 0
    )
    unexplained = int(transitions.get("unexplained_rank_movements") or 0)
    score_only = int(transitions.get("kind_SCORE_DRIVEN_RANK_MOVEMENT") or 0)
    history_preserved = bool(transitions.get("history_preserved", False))
    evidence_source_bound = bool(transitions.get("evidence_source_bound", False))
    evidence_mutated = bool(transitions.get("rank_learning_mutated_evidence", False))

    if recorded <= 0 or historical <= 0:
        gate = "PENDING_SECOND_RANK_OBSERVATION"
    elif evidence_mutated or not history_preserved:
        gate = "REFUSE_RANK_HISTORY_OR_EVIDENCE_MUTATION"
    elif unexplained > 0:
        gate = "REFUSE_UNEXPLAINED_RANK_MOVEMENT"
    elif score_only > 0:
        gate = "REFUSE_SCORE_ONLY_RANK_MOVEMENT"
    elif movements <= 0:
        gate = "PENDING_DYNAMIC_RANK_MOVEMENT"
    elif not evidence_source_bound or movement_evidence_bound < movements:
        gate = "PENDING_SOURCE_BOUND_RANK_MOVEMENT_EVIDENCE"
    else:
        gate = "DIO_MARKET_SENSORIUM_DYNAMIC_RANK_MOVEMENT_VERIFIED"

    receipt["ms3_implementation"] = "DIO_MARKET_SENSORIUM_DYNAMIC_RANK_LINEAGE_IMPLEMENTED"
    receipt["ms3_acceptance"] = gate
    receipt["ms3_truth"] = {
        "transitions_recorded": recorded,
        "historical_transitions": historical,
        "rank_movement_transitions": movements,
        "evidence_bound_transitions": evidence_bound,
        "rank_movement_evidence_bound_transitions": movement_evidence_bound,
        "unexplained_rank_movements": unexplained,
        "score_only_rank_movements": score_only,
        "history_preserved": history_preserved,
        "rank_learning_mutated_evidence": evidence_mutated,
        "evidence_source_bound": evidence_source_bound,
        "persisted_transition_count": int(transitions.get("persisted_transition_count") or 0),
        "market_demand_claimed": False,
        "best_target_claimed": False,
        "authority_created": False,
    }
    return receipt


def _apply_ms4_gate(receipt: dict) -> dict:
    """Apply the Hivenance Commercial Phoenix v2 rival-hypothesis gate."""
    summary = receipt.get("summary") or {}
    store_summary = summary.get("store") or {}
    phoenix = store_summary.get("commercial_phoenix") or {}
    summary["commercial_phoenix"] = phoenix

    movements = int(phoenix.get("movement_events_examined") or 0)
    sets_created = int(phoenix.get("hypothesis_sets_created") or 0)
    hypotheses = int(phoenix.get("hypotheses_created") or 0)
    rival_sets = int(phoenix.get("rival_sets_with_3plus") or 0)
    source_bound = int(phoenix.get("source_bound_hypotheses") or 0)
    michael = int(phoenix.get("michael_validated_hypotheses") or 0)
    loki = int(phoenix.get("loki_challenged_hypotheses") or 0)
    metatron = int(phoenix.get("metatron_synthesized_hypotheses") or 0)
    selected_tests = int(phoenix.get("selected_bounded_tests") or 0)
    unbounded = int(phoenix.get("unbounded_or_authority_tests") or 0)
    without_source = int(phoenix.get("sets_without_source_evidence") or 0)
    truth_claims = int(phoenix.get("truth_claims_created") or 0)
    type_counts = phoenix.get("hypothesis_type_counts") or {}
    type_diversity = sum(1 for value in type_counts.values() if int(value or 0) > 0)
    authority = any(
        bool(phoenix.get(key, False))
        for key in (
            "authority_created",
            "outreach_authority_created",
            "publication_authority_created",
            "spend_authority_created",
            "commerce_authority_created",
        )
    )

    if receipt.get("ms3_acceptance") != "DIO_MARKET_SENSORIUM_DYNAMIC_RANK_MOVEMENT_VERIFIED":
        gate = "PENDING_MS3_DYNAMIC_RANK_INPUT"
    elif movements <= 0:
        gate = "PENDING_REAL_RANK_MOVEMENT_INPUT"
    elif sets_created < movements or rival_sets < sets_created or hypotheses < sets_created * 3:
        gate = "REFUSE_NON_RIVAL_COMMERCIAL_HYPOTHESIS_SET"
    elif without_source > 0 or source_bound < hypotheses:
        gate = "PENDING_SOURCE_BOUND_COMMERCIAL_HYPOTHESES"
    elif michael < hypotheses or loki < hypotheses or metatron < hypotheses:
        gate = "REFUSE_INCOMPLETE_HIVENANCE_TRIUNE_CHALLENGE"
    elif selected_tests < sets_created:
        gate = "PENDING_BOUNDED_RESEARCH_TEST_SELECTION"
    elif unbounded > 0 or truth_claims > 0 or authority:
        gate = "REFUSE_HYPOTHESIS_TRUTH_OR_AUTHORITY_PROMOTION"
    elif type_diversity < 3:
        gate = "PENDING_COMMERCIAL_HYPOTHESIS_DIVERSITY"
    else:
        gate = "DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_VERIFIED"

    receipt["ms4_implementation"] = "DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_IMPLEMENTED"
    receipt["ms4_acceptance"] = gate
    receipt["ms4_truth"] = {
        "movement_events_examined": movements,
        "hypothesis_sets_created": sets_created,
        "hypotheses_created": hypotheses,
        "rival_sets_with_3plus": rival_sets,
        "source_bound_hypotheses": source_bound,
        "michael_validated_hypotheses": michael,
        "loki_challenged_hypotheses": loki,
        "metatron_synthesized_hypotheses": metatron,
        "selected_bounded_tests": selected_tests,
        "unbounded_or_authority_tests": unbounded,
        "hypothesis_type_diversity": type_diversity,
        "hypothesis_type_counts": type_counts,
        "hypothesis_is_fact": False,
        "selected_hypothesis_is_truth": False,
        "selected_test_is_execution_authority": False,
        "truth_claims_created": truth_claims,
        "buyer_unit_verified_by_hypothesis": False,
        "market_demand_claimed": False,
        "best_target_claimed": False,
        "authority_created": False,
    }
    return receipt


def _apply_ms5_gate(receipt: dict) -> dict:
    """Apply the source-bound competitive-offer and advertised-price gate."""
    summary = receipt.get("summary") or {}
    offers = summary.get("competitive_offers") or {}

    observed = int(offers.get("source_bound_offer_observations") or 0)
    canonical = int(offers.get("canonical_competitive_offers") or 0)
    sellers = int(offers.get("unique_sellers_observed_this_run") or 0)
    prices = int(offers.get("explicit_advertised_price_observations") or 0)
    price_errors = int(offers.get("price_normalization_errors") or 0)
    provider_confusion = int(offers.get("provider_role_confusion") or 0)
    source_bound = bool(offers.get("source_bound", False))
    authority = bool(offers.get("authority_created", False))
    external = bool(offers.get("external_effects", False))
    demand = bool(offers.get("market_demand_claimed", False))
    wtp = bool(offers.get("willingness_to_pay_proved", False))
    realised = bool(offers.get("advertised_price_is_realised_price", False))
    market_price = bool(offers.get("advertised_price_is_market_price", False))

    if receipt.get("ms4_acceptance") != "DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_VERIFIED":
        gate = "PENDING_VERIFIED_MS4_RECEIPT"
    elif observed <= 0 or canonical <= 0:
        gate = "PENDING_COMPETITIVE_OFFER_EVIDENCE"
    elif sellers < 2:
        gate = "PENDING_MULTI_SELLER_COMPETITIVE_EVIDENCE"
    elif provider_confusion > 0 or bool(offers.get("publisher_auto_promoted_to_seller", False)):
        gate = "REFUSE_SELLER_SOURCE_ROLE_CONFUSION"
    elif not source_bound:
        gate = "PENDING_SOURCE_BOUND_COMPETITIVE_OFFER_EVIDENCE"
    elif price_errors > 0:
        gate = "REFUSE_ADVERTISED_PRICE_NORMALIZATION_ERROR"
    elif prices <= 0:
        gate = "PENDING_EXPLICIT_ADVERTISED_PRICE_EVIDENCE"
    elif authority or external or demand or wtp or realised or market_price:
        gate = "REFUSE_OFFER_PRICE_TRUTH_OR_AUTHORITY_INFLATION"
    else:
        gate = "DIO_MARKET_SENSORIUM_COMPETITIVE_OFFER_INTELLIGENCE_VERIFIED"

    receipt["ms5_implementation"] = "DIO_MARKET_SENSORIUM_COMPETITIVE_OFFER_INTELLIGENCE_IMPLEMENTED"
    receipt["ms5_acceptance"] = gate
    receipt["ms5_truth"] = {
        "source_bound_offer_observations": observed,
        "canonical_competitive_offers": canonical,
        "unique_sellers_observed_this_run": sellers,
        "explicit_advertised_price_observations": prices,
        "price_state_counts": offers.get("price_state_counts") or {},
        "price_normalization_errors": price_errors,
        "provider_role_confusion": provider_confusion,
        "multi_source_dedupe_groups": int(offers.get("multi_source_dedupe_groups") or 0),
        "persisted_competitive_offer_events": int(offers.get("persisted_competitive_offer_events") or 0),
        "legacy_offer_observation_count": int(offers.get("legacy_offer_observation_count") or 0),
        "advertised_offer_is_demand": False,
        "advertised_price_is_market_price": False,
        "advertised_price_is_realised_price": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "seller_promoted_to_target": False,
        "market_demand_claimed": False,
        "best_offer_claimed": False,
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
    receipt = _apply_ms3_gate(receipt)
    receipt = _apply_ms4_gate(receipt)

    db_path = ROOT / "state" / "market_sensorium" / "market_sensorium.sqlite"
    with cycle_module.MarketSensoriumStore(db_path) as store:
        offers = observe_competitive_offers(ROOT, store)
    receipt.setdefault("summary", {})["competitive_offers"] = offers
    receipt.setdefault("summary", {}).setdefault("store", {})["offers"] = int(
        offers.get("legacy_offer_observation_count") or 0
    )
    receipt = _apply_ms5_gate(receipt)

    receipt_path = ROOT / "state" / "market_sensorium" / "MARKET_SENSORIUM_CYCLE_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
