#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.cockpit import MS7_VERIFIED, build_commercial_cockpit  # noqa: E402
from market_sensorium.core import MarketSensoriumStore  # noqa: E402

STATE_ROOT = ROOT / "state" / "market_sensorium"
DB_PATH = STATE_ROOT / "market_sensorium.sqlite"
MS7_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS7_RECEIPT.json"
MS8_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS8_RECEIPT.json"


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _apply_ms8_gate(receipt: dict) -> dict:
    cockpit = (receipt.get("summary") or {}).get("commercial_cockpit") or {}
    truth = cockpit.get("truth_summary") or {}
    sections = truth.get("section_counts") or {}
    artifacts = cockpit.get("artifacts") or {}
    ms7 = str(receipt.get("ms7_acceptance") or "")

    violations = int(truth.get("truth_class_violations") or 0)
    complete = bool(truth.get("operator_surface_complete", False))
    temporal = bool(truth.get("ms2_observation_active_or_verified", False))
    linked = int(truth.get("linked_hypothesis_sets_to_visible_movements") or 0)
    section_count = sum(1 for value in sections.values() if int(value or 0) > 0)
    authority = bool(cockpit.get("authority_created", False))
    external = bool(cockpit.get("external_effects", False))
    truth_inflation = any(bool(cockpit.get(key, False)) for key in (
        "best_target_claimed",
        "market_demand_claimed",
        "willingness_to_pay_proved",
        "commercial_success_proved",
        "customer_claimed",
    ))

    if ms7 != MS7_VERIFIED:
        gate = "PENDING_VERIFIED_MS7_RECEIPT"
    elif not temporal:
        gate = "PENDING_COMMERCIAL_TIME_OBSERVATION_STATE"
    elif not complete or section_count < 6:
        gate = "PENDING_COMPLETE_COMMERCIAL_COCKPIT_EVIDENCE"
    elif linked <= 0:
        gate = "PENDING_RANK_TO_HYPOTHESIS_COCKPIT_LINEAGE"
    elif violations > 0 or not bool(truth.get("truth_separation_valid", False)):
        gate = "REFUSE_COCKPIT_TRUTH_CLASS_COLLAPSE"
    elif not artifacts.get("json") or not artifacts.get("html"):
        gate = "PENDING_COCKPIT_OPERATOR_ARTIFACTS"
    elif authority or external or truth_inflation:
        gate = "REFUSE_COCKPIT_AUTHORITY_OR_COMMERCIAL_TRUTH_INFLATION"
    else:
        gate = "DIO_MARKET_SENSORIUM_COMMERCIAL_COCKPIT_VERIFIED"

    receipt["ms8_implementation"] = "DIO_MARKET_SENSORIUM_COMMERCIAL_COCKPIT_RECONSTRUCTION_IMPLEMENTED"
    receipt["ms8_acceptance"] = gate
    receipt["ms8_truth"] = {
        "phase_chain_visible": len(cockpit.get("phase_status") or {}) == 7,
        "commercial_time_visible": bool(cockpit.get("commercial_time")),
        "ranked_targets_visible": int(sections.get("ranked_targets") or 0),
        "rank_movements_visible": int(sections.get("rank_movements") or 0),
        "hypothesis_sets_visible": int(sections.get("hypotheses") or 0),
        "competitive_offers_visible": int(sections.get("offers") or 0),
        "market_habitats_visible": int(sections.get("habitats") or 0),
        "learned_queries_visible": int(sections.get("learned_queries") or 0),
        "rank_to_hypothesis_links_visible": linked,
        "truth_class_violations": violations,
        "truth_separation_valid": bool(truth.get("truth_separation_valid", False)),
        "operator_surface_complete": complete,
        "ms2_observation_active_or_verified": temporal,
        "json_artifact": artifacts.get("json"),
        "html_artifact": artifacts.get("html"),
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "customer_claimed": False,
        "authority_created": False,
    }
    return receipt


def main() -> int:
    prior = _read_json(MS7_RECEIPT)
    ms7_acceptance = str(prior.get("ms7_acceptance") or "")
    if ms7_acceptance != MS7_VERIFIED:
        payload = {
            "schema": "dio.market_sensorium.ms8_commercial_cockpit_runner.v1",
            "ms7_acceptance": ms7_acceptance or "UNAVAILABLE",
            "ms8_implementation": "DIO_MARKET_SENSORIUM_COMMERCIAL_COCKPIT_RECONSTRUCTION_IMPLEMENTED",
            "ms8_acceptance": "PENDING_VERIFIED_MS7_RECEIPT",
            "authority_created": False,
            "external_effects": False,
        }
        MS8_RECEIPT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0

    with MarketSensoriumStore(DB_PATH) as store:
        cockpit = build_commercial_cockpit(ROOT, store)

    receipt = {
        "schema": "dio.market_sensorium.ms8_commercial_cockpit_runner.v1",
        "ms7_acceptance": ms7_acceptance,
        "summary": {"commercial_cockpit": cockpit},
        "authority_created": False,
        "external_effects": False,
    }
    receipt = _apply_ms8_gate(receipt)
    MS8_RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
