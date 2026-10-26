#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.core import MarketSensoriumStore  # noqa: E402
from market_sensorium.habitat_intelligence import observe_market_habitats  # noqa: E402

STATE_ROOT = ROOT / "state" / "market_sensorium"
DB_PATH = STATE_ROOT / "market_sensorium.sqlite"
MS5_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS5_RECEIPT.json"
MS6_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS6_RECEIPT.json"
MS5_VERIFIED = "DIO_MARKET_SENSORIUM_COMPETITIVE_OFFER_INTELLIGENCE_VERIFIED"


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _apply_ms6_gate(receipt: dict) -> dict:
    summary = receipt.get("summary") or {}
    habitats = summary.get("market_habitats") or {}

    examined = int(habitats.get("habitat_observations_examined") or 0)
    canonical = int(habitats.get("canonical_habitats") or 0)
    source_bound = int(habitats.get("source_bound_habitats") or 0)
    public = int(habitats.get("public_observable_habitats") or 0)
    diversity = int(habitats.get("habitat_type_diversity") or 0)
    needs_you = int(habitats.get("needs_you_habitats") or 0)
    restricted = int(habitats.get("refused_or_terms_restricted_habitats") or 0)
    authority = any(
        bool(habitats.get(key, False))
        for key in (
            "authority_created",
            "outreach_authority_created",
            "posting_authority_created",
            "dm_authority_created",
            "membership_authority_created",
        )
    )
    semantic_confusion = any(
        bool(habitats.get(key, False))
        for key in (
            "public_visibility_is_consent",
            "public_visibility_is_membership",
            "public_visibility_is_posting_authority",
            "public_visibility_is_dm_authority",
            "participant_inference_allowed",
            "member_scraping_allowed",
            "seller_association_is_target_identity",
            "habitat_is_demand",
            "market_demand_claimed",
        )
    )

    if receipt.get("ms5_acceptance") != MS5_VERIFIED:
        gate = "PENDING_VERIFIED_MS5_RECEIPT"
    elif examined <= 0 or canonical <= 0:
        gate = "PENDING_MARKET_HABITAT_EVIDENCE"
    elif source_bound < examined:
        gate = "PENDING_SOURCE_BOUND_MARKET_HABITATS"
    elif public <= 0:
        gate = "PENDING_PUBLIC_OBSERVABLE_HABITAT_EVIDENCE"
    elif diversity < 2:
        gate = "PENDING_MARKET_HABITAT_TYPE_DIVERSITY"
    elif semantic_confusion or authority or bool(habitats.get("external_effects", False)):
        gate = "REFUSE_HABITAT_PERMISSION_OR_TRUTH_INFLATION"
    else:
        gate = "DIO_MARKET_SENSORIUM_MARKET_HABITAT_INTELLIGENCE_VERIFIED"

    receipt["ms6_implementation"] = "DIO_MARKET_SENSORIUM_MARKET_HABITAT_INTELLIGENCE_IMPLEMENTED"
    receipt["ms6_acceptance"] = gate
    receipt["ms6_truth"] = {
        "habitat_observations_examined": examined,
        "canonical_habitats": canonical,
        "source_bound_habitats": source_bound,
        "public_observable_habitats": public,
        "needs_you_habitats": needs_you,
        "refused_or_terms_restricted_habitats": restricted,
        "habitat_type_diversity": diversity,
        "habitat_kind_counts": habitats.get("habitat_kind_counts") or {},
        "permission_state_counts": habitats.get("permission_state_counts") or {},
        "provider_associated_habitats": int(habitats.get("provider_associated_habitats") or 0),
        "public_visibility_is_consent": False,
        "public_visibility_is_membership": False,
        "public_visibility_is_posting_authority": False,
        "public_visibility_is_dm_authority": False,
        "participant_inference_allowed": False,
        "member_scraping_allowed": False,
        "seller_association_is_target_identity": False,
        "habitat_is_demand": False,
        "market_demand_claimed": False,
        "posting_authority_created": False,
        "dm_authority_created": False,
        "membership_authority_created": False,
        "authority_created": False,
    }
    return receipt


def main() -> int:
    prior = _read_json(MS5_RECEIPT)
    ms5_acceptance = str(prior.get("ms5_acceptance") or "")
    if ms5_acceptance != MS5_VERIFIED:
        payload = {
            "schema": "dio.market_sensorium.ms6_market_habitat_runner.v1",
            "ms5_acceptance": ms5_acceptance or "UNAVAILABLE",
            "ms6_implementation": "DIO_MARKET_SENSORIUM_MARKET_HABITAT_INTELLIGENCE_IMPLEMENTED",
            "ms6_acceptance": "PENDING_VERIFIED_MS5_RECEIPT",
            "reason": "The persisted MS-5 receipt does not carry the verified Competitive Offer Intelligence token.",
            "authority_created": False,
            "external_effects": False,
        }
        MS6_RECEIPT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0

    with MarketSensoriumStore(DB_PATH) as store:
        habitats = observe_market_habitats(store)

    receipt = {
        "schema": "dio.market_sensorium.ms6_market_habitat_runner.v1",
        "ms5_acceptance": ms5_acceptance,
        "ms5_source_ms4_acceptance": prior.get("ms4_acceptance"),
        "summary": {"market_habitats": habitats},
        "authority_created": False,
        "external_effects": False,
    }
    receipt = _apply_ms6_gate(receipt)
    MS6_RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
