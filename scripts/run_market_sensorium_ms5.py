#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.competitive_offers import observe_competitive_offers  # noqa: E402
from market_sensorium.core import MarketSensoriumStore  # noqa: E402

STATE_ROOT = ROOT / "state" / "market_sensorium"
DB_PATH = STATE_ROOT / "market_sensorium.sqlite"
MS4_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS4_RECEIPT.json"
MS5_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS5_RECEIPT.json"
MS4_VERIFIED = "DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_VERIFIED"


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _apply_ms5_gate(receipt: dict) -> dict:
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

    if receipt.get("ms4_acceptance") != MS4_VERIFIED:
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
    prior = _read_json(MS4_RECEIPT)
    ms4_acceptance = str(prior.get("ms4_acceptance") or "")
    if ms4_acceptance != MS4_VERIFIED:
        payload = {
            "schema": "dio.market_sensorium.ms5_competitive_offer_runner.v1",
            "ms4_acceptance": ms4_acceptance or "UNAVAILABLE",
            "ms5_implementation": "DIO_MARKET_SENSORIUM_COMPETITIVE_OFFER_INTELLIGENCE_IMPLEMENTED",
            "ms5_acceptance": "PENDING_VERIFIED_MS4_RECEIPT",
            "reason": "The persisted MS-4 receipt does not carry the verified Commercial Phoenix v2 token.",
            "authority_created": False,
            "external_effects": False,
        }
        MS5_RECEIPT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0

    with MarketSensoriumStore(DB_PATH) as store:
        offers = observe_competitive_offers(ROOT, store)

    receipt = {
        "schema": "dio.market_sensorium.ms5_competitive_offer_runner.v1",
        "ms4_acceptance": ms4_acceptance,
        "ms4_source_ms3_acceptance": prior.get("ms3_acceptance"),
        "summary": {"competitive_offers": offers},
        "authority_created": False,
        "external_effects": False,
    }
    receipt = _apply_ms5_gate(receipt)
    MS5_RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
