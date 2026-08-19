#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.competitive_offers import observe_competitive_offers  # noqa: E402
from market_sensorium.core import MarketSensoriumStore  # noqa: E402
from scripts.run_market_sensorium_cycle import _apply_ms5_gate  # noqa: E402

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
