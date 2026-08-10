#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.mandos_feedback import campaign_feedback, hivenance_outcome_overlay  # noqa: E402


CONFIG = ROOT / "config" / "dio_marketing_integration.json"
CAMPAIGN_ROOT = ROOT / "campaigns" / "dio_market_loop" / "wave4" / "campaigns"

NEXT_ACTION = {
    "TEST": "prepare one bounded channel test and require operator release",
    "REFINE": "improve query precision, source diversity, or resolve Mandos outcome contradiction before release",
    "HOLD": "collect stronger observations or resolve repeated verified failure before producing more campaign assets",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_market_module(hivenance_root: Path):
    module_path = hivenance_root / "agents" / "market_intelligence.py"
    if not module_path.exists():
        raise FileNotFoundError(f"Hivenance market-intelligence agent module not found: {module_path}")
    spec = importlib.util.spec_from_file_location("hivenance_market_intelligence", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the Hivenance market-intelligence agents.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def empty_mandos_feedback() -> dict[str, Any]:
    return {
        "schema": "dio.mandos_campaign_feedback.v1",
        "campaign_id": None,
        "outcomes": [],
        "patterns": [],
        "economics": {"revenue_minor": 0, "cost_minor": 0, "manual_minutes": 0.0, "gross_margin_minor": 0},
        "authority": {
            "is_observed_evidence": True,
            "is_synthetic_score": False,
            "may_expand_execution_authority": False,
            "may_be_reused_as_strategy": False,
        },
    }


def build_context(campaign_dir: Path) -> dict[str, Any]:
    hypothesis = read_json(campaign_dir / "HIVENANCE_HYPOTHESIS.json")
    campaign_id = str(hypothesis.get("campaign_id") or "")
    return {
        "campaign_id": campaign_id,
        "hypothesis": hypothesis,
        "registry_observation": read_json(campaign_dir / "MARKET_OBSERVATION.json"),
        "live_signals": read_json(campaign_dir / "LIVE_MARKET_SIGNALS.json") if (campaign_dir / "LIVE_MARKET_SIGNALS.json").exists() else {},
        "measurement": read_json(campaign_dir / "measurement.json") if (campaign_dir / "measurement.json").exists() else {},
        "settlement": read_json(campaign_dir / "HIVENANCE_SETTLEMENT.json") if (campaign_dir / "HIVENANCE_SETTLEMENT.json").exists() else {},
        "mandos_outcomes": campaign_feedback(ROOT, campaign_id) if campaign_id else empty_mandos_feedback(),
    }


def apply_mandos_overlay(receipt: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Preserve the native Hivenance receipt and add a conservative Mandos outcome judgement."""
    feedback = context.get("mandos_outcomes") or empty_mandos_feedback()
    overlay = hivenance_outcome_overlay(feedback, receipt)
    receipt["mandos_outcome_council"] = overlay
    receipt["effective_decision"] = overlay["effective_decision"]
    receipt["effective_next_action"] = NEXT_ACTION[overlay["effective_decision"]]
    receipt.setdefault("authority", {})["mandos_may_upgrade_hivenance_decision"] = False
    receipt["authority"]["mandos_may_expand_execution_authority"] = False
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the non-crypto Hivenance market worker, oracle, strategist and council lane with Mandos outcome evidence.")
    parser.add_argument("--campaign-id")
    args = parser.parse_args()
    config = read_json(CONFIG)
    hivenance_root = Path(config["hivenance_root"]).resolve()
    agents = load_market_module(hivenance_root)
    register_root = hivenance_root / "data" / "hypothesis_registry" / "marketing" / "agent_receipts"
    register_root.mkdir(parents=True, exist_ok=True)
    results = []
    for campaign_dir in sorted(CAMPAIGN_ROOT.iterdir()):
        if not campaign_dir.is_dir() or not (campaign_dir / "HIVENANCE_HYPOTHESIS.json").exists():
            continue
        context = build_context(campaign_dir)
        campaign_id = str(context.get("campaign_id") or "")
        if args.campaign_id and campaign_id.upper() != args.campaign_id.upper():
            continue
        native_receipt = agents.assess_market_campaign(context)
        receipt = apply_mandos_overlay(native_receipt, context)
        output_path = campaign_dir / "HIVENANCE_MARKET_AGENTS.json"
        write_json(output_path, receipt)
        write_json(register_root / f"{campaign_id}.json", receipt)
        results.append(
            {
                "campaign_id": campaign_id,
                "decision": receipt["effective_decision"],
                "hivenance_decision": receipt["council"]["decision"],
                "mandos_outcome_judgement": receipt["mandos_outcome_council"]["judgement"],
                "regime": receipt["oracle"]["regime"],
                "selected_family": receipt["council"].get("selected_family"),
                "harmony_index": receipt["council"]["harmony_index"],
                "mandos_outcomes": len((context.get("mandos_outcomes") or {}).get("outcomes") or []),
                "mandos_strategy_reuse_authority": bool(((context.get("mandos_outcomes") or {}).get("authority") or {}).get("may_be_reused_as_strategy")),
                "mandos_may_upgrade_decision": False,
                "output": str(output_path),
            }
        )
    if args.campaign_id and not results:
        raise ValueError(f"Campaign not found: {args.campaign_id}")
    print(json.dumps({"schema": "dio.hivenance.market_agent_run.v3", "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
