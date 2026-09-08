#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTEGRATION_CONFIG = ROOT / "config" / "dio_marketing_integration.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.isoformat()


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def number(section: dict[str, Any], key: str) -> int:
    return int(section.get(key) or 0)


def measurement_hash(measurement: dict[str, Any]) -> str:
    canonical = json.dumps(measurement, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def economics(measurement: dict[str, Any]) -> dict[str, int]:
    commerce = measurement.get("commerce", {})
    costs = measurement.get("economics", {})
    revenue = number(commerce, "revenue_minor")
    refunds = number(commerce, "refunds_minor")
    total_cost = sum(
        number(costs, key)
        for key in ["ad_spend_minor", "payment_fees_minor", "external_cost_minor", "manual_labour_minor"]
    )
    return {
        "revenue_minor": revenue,
        "refunds_minor": refunds,
        "total_cost_minor": total_cost,
        "gross_contribution_minor": revenue - refunds - total_cost,
    }


def hypothesis_market_type(hypothesis: dict[str, Any]) -> str:
    return str(hypothesis.get("audience", {}).get("market_type") or "buyer").strip().lower()


def decide_investor_campaign(measurement: dict[str, Any]) -> tuple[str, list[str]]:
    funnel = measurement.get("capital_funnel", {})
    acquisition = measurement.get("acquisition", {})
    term_sheets = number(funnel, "term_sheets")
    ic_reviews = number(funnel, "ic_reviews")
    partner_meetings = number(funnel, "partner_meetings")
    diligence_entries = number(funnel, "diligence_entries")
    meetings = number(funnel, "meetings")
    replies = number(funnel, "replies")
    engagements = max(number(acquisition, "profile_engagements"), number(acquisition, "clicks"))

    if term_sheets >= 1:
        return (
            "promote",
            [
                "The capital campaign produced a term-sheet signal; promote the campaign hypothesis while keeping investment-secured truth explicitly unearned."
            ],
        )
    if ic_reviews >= 1 or partner_meetings >= 1 or diligence_entries >= 1:
        return (
            "continue",
            ["Qualified investor engagement reached diligence, partner-meeting or investment-committee depth; continue the campaign and gather more evidence."],
        )
    if meetings >= 3:
        return "revise", ["Investor meetings did not progress into diligence; revise thesis framing, proof selection or capital-use narrative."]
    if engagements >= 10 and replies == 0:
        return "revise", ["Investor-profile engagement did not produce replies; revise target fit, hook or route."]
    return "revise", ["The completed capital window lacks enough investor signal to continue unchanged."]


def decide(hypothesis: dict[str, Any], measurement: dict[str, Any], as_of: datetime) -> tuple[str, list[str], bool]:
    governance = measurement.get("governance", {})
    leads = measurement.get("leads", {})
    acquisition = measurement.get("acquisition", {})
    commerce = measurement.get("commerce", {})
    fulfilment = measurement.get("fulfilment", {})
    window = measurement.get("measurement_window", {})
    started = parse_time(window.get("started_at"))
    ended = parse_time(window.get("ended_at"))
    window_days = int(hypothesis.get("experiment", {}).get("window_days") or 14)
    calculated = economics(measurement)

    if number(governance, "unresolved_incidents") or number(governance, "permission_failures"):
        return "kill", ["Governance incident or permission failure is unresolved."], True
    if number(governance, "outreach_attempts") and hypothesis.get("gates", {}).get("electronic_sales_outreach") != "allowed":
        return "kill", ["Outreach occurred while the registered outreach gate was blocked."], True
    if started is None:
        return "pending", ["The measurement window has not started."], False

    window_complete = ended is not None or as_of >= started + timedelta(days=window_days)
    if not window_complete:
        return "pending", [f"The {window_days}-day measurement window is still collecting evidence."], False

    if hypothesis_market_type(hypothesis) == "investor":
        decision, reasons = decide_investor_campaign(measurement)
        return decision, reasons, True

    paid_orders = number(commerce, "paid_orders")
    orders = max(number(commerce, "orders"), paid_orders)
    qualified = number(leads, "qualified_leads")
    clicks = number(acquisition, "clicks")
    revisions = number(fulfilment, "revisions")
    contribution = calculated["gross_contribution_minor"]

    if paid_orders >= 3 and contribution > 0 and revisions <= max(orders, 1):
        return "promote", ["At least three paid orders produced positive gross contribution with controlled revision burden."], True
    if paid_orders >= 1 and contribution > 0:
        return "continue", ["Paid demand and positive gross contribution exist, but the sample is too small for promotion."], True
    if paid_orders and contribution <= 0:
        return "revise", ["The campaign converted, but its measured gross contribution is not positive."], True
    if qualified >= 3 and paid_orders == 0:
        return "revise", ["Qualified interest did not convert to a paid order; revise offer, proof or close path."], True
    if clicks >= 10 and qualified == 0:
        return "revise", ["Traffic did not become qualified demand; revise audience, hook or landing-page promise."], True
    return "revise", ["The completed window lacks enough commercial signal to continue unchanged."], True


def settle(campaign_dir: Path, as_of: datetime) -> dict[str, Any]:
    hypothesis = read_json(campaign_dir / "HIVENANCE_HYPOTHESIS.json")
    measurement = read_json(campaign_dir / "measurement.json")
    if measurement.get("campaign_id") != hypothesis.get("campaign_id"):
        raise ValueError("Measurement campaign_id does not match the registered hypothesis.")

    decision, reasons, window_complete = decide(hypothesis, measurement, as_of)
    digest = measurement_hash(measurement)
    decision_id = f"SET-{hashlib.sha256((hypothesis['campaign_id'] + digest).encode()).hexdigest()[:12].upper()}"
    entry = {
        "decision_id": decision_id,
        "decided_at": iso(as_of),
        "campaign_id": hypothesis["campaign_id"],
        "hypothesis_id": hypothesis["hypothesis_id"],
        "market_type": hypothesis_market_type(hypothesis),
        "measurement_sha256": digest,
        "window_complete": window_complete,
        "decision": decision,
        "reasons": reasons,
        "economics": economics(measurement),
        "gate_effects": {
            "content_hypothesis": decision,
            "publication_permission": "unchanged",
            "electronic_outreach_permission": "unchanged",
        },
    }
    settlement_path = campaign_dir / "HIVENANCE_SETTLEMENT.json"
    settlement = (
        read_json(settlement_path)
        if settlement_path.exists()
        else {"schema": "dio.hivenance.marketing_settlement.v1", "campaign_id": hypothesis["campaign_id"], "history": []}
    )
    if not any(item.get("decision_id") == decision_id for item in settlement["history"]):
        settlement["history"].append(entry)
    settlement["latest"] = entry
    write_json(settlement_path, settlement)
    return entry


def sync_hivenance_settlement(campaign_dir: Path, entry: dict[str, Any], config_path: Path) -> Path:
    config = read_json(config_path)
    destination_dir = Path(config["hivenance_root"]).resolve() / "data" / "hypothesis_registry" / "marketing" / "settlements"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{entry['campaign_id']}.json"
    source = read_json(campaign_dir / "HIVENANCE_SETTLEMENT.json")
    write_json(destination, source)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Settle one measured DIO marketing hypothesis.")
    parser.add_argument("campaign_dir", type=Path)
    parser.add_argument("--as-of", help="ISO timestamp used for reproducible settlement tests")
    parser.add_argument("--config", type=Path, default=DEFAULT_INTEGRATION_CONFIG)
    args = parser.parse_args()
    as_of = parse_time(args.as_of) if args.as_of else utc_now()
    campaign_dir = args.campaign_dir.resolve()
    result = settle(campaign_dir, as_of or utc_now())
    result["hivenance_settlement_path"] = str(sync_hivenance_settlement(campaign_dir, result, args.config.resolve()))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
