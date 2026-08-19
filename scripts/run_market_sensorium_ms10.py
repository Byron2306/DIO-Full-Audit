#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.operator_convergence import audit_operator_convergence, apply_ms10_gate  # noqa: E402

OUT = ROOT / "state" / "market_sensorium" / "MARKET_SENSORIUM_MS10_RECEIPT.json"


def main() -> int:
    summary = audit_operator_convergence(ROOT)
    gate = apply_ms10_gate(summary)
    receipt = {
        "schema": "dio.market_sensorium.ms10_operator_surface_convergence_runner.v1",
        "ms9_acceptance": summary.get("ms9_acceptance"),
        "ms10_implementation": "DIO_MARKET_SENSORIUM_OPERATOR_SURFACE_CONVERGENCE_IMPLEMENTED",
        "ms10_acceptance": gate,
        "ms10_truth": {
            "surface_count": summary.get("surface_count"),
            "all_surfaces_canonical_truth_bound": summary.get("all_surfaces_canonical_truth_bound"),
            "all_surfaces_current_repo_bound": summary.get("all_surfaces_current_repo_bound"),
            "all_surface_servers_current_and_local": summary.get("all_surface_servers_current_and_local"),
            "all_sensorium_features_visible": summary.get("all_sensorium_features_visible"),
            "existing_operator_capabilities_preserved": summary.get("existing_operator_capabilities_preserved"),
            "control_deck_action_plane_preserved": summary.get("control_deck_action_plane_preserved"),
            "market_command_action_plane_preserved": summary.get("market_command_action_plane_preserved"),
            "goldeneye_portfolio_projection_current_repo_bound": summary.get("goldeneye_portfolio_projection_current_repo_bound"),
            "goldeneye_phase9_stale_server_retired": summary.get("goldeneye_phase9_stale_server_retired"),
            "independent_sensorium_truth_engines_created": summary.get("independent_sensorium_truth_engines_created"),
            "best_target_claimed": False,
            "market_demand_claimed": False,
            "willingness_to_pay_proved": False,
            "commercial_success_proved": False,
            "authority_created": False,
        },
        "summary": {"operator_convergence": summary},
        "authority_created": False,
        "external_effects": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
