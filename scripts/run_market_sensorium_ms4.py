#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.commercial_phoenix import run_commercial_phoenix  # noqa: E402
from market_sensorium.core import MarketSensoriumStore  # noqa: E402
from scripts.run_market_sensorium_cycle import _apply_ms4_gate  # noqa: E402

STATE_ROOT = ROOT / "state" / "market_sensorium"
DB_PATH = STATE_ROOT / "market_sensorium.sqlite"
CYCLE_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_CYCLE_RECEIPT.json"
MS4_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS4_RECEIPT.json"
MS3_VERIFIED = "DIO_MARKET_SENSORIUM_DYNAMIC_RANK_MOVEMENT_VERIFIED"


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    prior = _read_json(CYCLE_RECEIPT)
    ms3_acceptance = str(prior.get("ms3_acceptance") or "")
    if ms3_acceptance != MS3_VERIFIED:
        payload = {
            "schema": "dio.market_sensorium.ms4_persisted_ms3_runner.v1",
            "ms3_acceptance": ms3_acceptance or "UNAVAILABLE",
            "ms4_implementation": "DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_IMPLEMENTED",
            "ms4_acceptance": "PENDING_VERIFIED_MS3_RECEIPT",
            "reason": "The persisted cycle receipt does not carry the verified MS-3 acceptance token.",
            "authority_created": False,
            "external_effects": False,
        }
        MS4_RECEIPT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0

    with MarketSensoriumStore(DB_PATH) as store:
        phoenix = run_commercial_phoenix(store)

    receipt = {
        "schema": "dio.market_sensorium.ms4_persisted_ms3_runner.v1",
        "ms3_acceptance": ms3_acceptance,
        "ms3_source_cycle_id": prior.get("cycle_id"),
        "ms3_source_receipt_digest": prior.get("receipt_digest"),
        "summary": {
            "store": {"commercial_phoenix": phoenix},
            "commercial_phoenix": phoenix,
        },
        "authority_created": False,
        "external_effects": False,
    }
    receipt = _apply_ms4_gate(receipt)
    MS4_RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
