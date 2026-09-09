#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_capital.atlas_fit import adjacent_search_suggestions, build_capital_support_fit
from market_capital.discovery import dedupe_observation_candidates, ingest_public_observation
from market_capital.hypotheses import generate_hypotheses
from market_capital.outreach import build_outreach_bundle
from market_capital.ranking import rank_capital_opportunities


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _default_type_fit(opportunity_type: str, fit_score: float) -> dict[str, float]:
    score = max(0.0, min(float(fit_score or 0), 100.0))
    defaults = {
        "INVESTOR": {"thesis": score, "stage": 60, "geography": 60, "capital_use": score, "proof": score},
        "GRANT": {"eligibility": score, "thematic": score, "geography": 60, "deadline": 50, "evidence": score},
        "DONOR": {"mission": score, "public_benefit": score, "impact": score, "stewardship": 60, "beneficiary": 60},
        "SPONSOR": {"strategic_alignment": score, "audience_overlap": 55, "ecosystem_value": score, "brand_safety": 70, "activation": 55},
        "PATRONAGE": {"public_value": score, "community_fit": 55, "repeatability": 55, "supporter_benefits": 50, "platform_fit": 50},
        "ACCELERATOR": {"eligibility": score, "stage": 60, "geography": 60, "sector": score, "network_value": 55, "programme_burden": 50},
        "PRIZE": {"eligibility": score, "innovation_fit": score, "impact": score, "deadline": 50, "evidence": score},
    }
    return defaults[opportunity_type]


def run_cycle(root: Path, observations: list[dict[str, Any]], search_budget: int = 20) -> dict[str, Any]:
    root = Path(root)
    state_root = root / "state"
    capital_root = state_root / "market_capital"
    budget = max(0, int(search_budget))
    observations = dedupe_observation_candidates(list(observations or []))

    processed: list[dict[str, Any]] = []
    ranking_inputs: list[dict[str, Any]] = []
    drafts: list[dict[str, Any]] = []
    expansion: list[dict[str, Any]] = []

    for observation in observations:
        ingested = ingest_public_observation(state_root, observation)
        opportunity = dict(ingested["opportunity"])
        fit = build_capital_support_fit(root, opportunity)
        _write_json(capital_root / "fits" / f"{opportunity['opportunity_id']}.json", fit)

        hypotheses = generate_hypotheses(opportunity, fit)
        _write_json(capital_root / "hypotheses" / f"{opportunity['opportunity_id']}.json", {
            "schema": "dio.market_capital.hypothesis_set.v1",
            "opportunity_id": opportunity["opportunity_id"],
            "items": hypotheses,
            "authority_created": False,
        })

        remaining = max(0, budget - len(expansion))
        if remaining:
            expansion.extend(adjacent_search_suggestions(fit, remaining))

        route_quality = opportunity.get("route_quality")
        if route_quality is None:
            route_quality = 70 if opportunity.get("contact_route") else 40
        evidence_freshness = opportunity.get("evidence_freshness", 90)
        timing_score = opportunity.get("timing_score", 60)
        ranking_inputs.append({
            **opportunity,
            "atlas_fit_score": fit.get("fit_score", 0),
            "type_fit": dict(opportunity.get("type_fit") or _default_type_fit(opportunity["opportunity_type"], fit.get("fit_score", 0))),
            "timing_score": timing_score,
            "route_quality": route_quality,
            "evidence_freshness": evidence_freshness,
            "leading_hypothesis": hypotheses[0] if hypotheses else None,
            "proof_bundle_ready": bool(fit.get("proof_bundle")),
        })

        if hypotheses:
            draft = build_outreach_bundle(opportunity, fit, hypotheses[0])
            drafts.append(draft)
            _write_json(capital_root / "drafts" / f"{opportunity['opportunity_id']}.json", draft)

        processed.append({
            "opportunity_id": opportunity["opportunity_id"],
            "opportunity_type": opportunity["opportunity_type"],
            "fit": fit,
            "hypothesis_count": len(hypotheses),
            "draft_created": bool(hypotheses),
        })

    ranked = rank_capital_opportunities(ranking_inputs)
    priority = {
        "schema": "dio.goldeneye.capital_support_priority.v1",
        "state": "PRESENT" if ranked else "EMPTY",
        "generated_at": _now(),
        "opportunity_count": len(ranked),
        "items": ranked,
        "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
        "willingness_to_fund": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }
    _write_json(capital_root / "rankings" / "CAPITAL_SUPPORT_PRIORITY.json", priority)

    receipt = {
        "schema": "dio.market_capital.discovery_cycle_receipt.v1",
        "generated_at": _now(),
        "processed": len(processed),
        "ranked": len(ranked),
        "drafts_created": len(drafts),
        "search_budget": budget,
        "search_budget_used": min(len(expansion), budget),
        "search_expansion_suggestions": expansion[:budget],
        "external_searches_executed": 0,
        "external_contacts_sent": 0,
        "submission_actions_executed": 0,
        "financial_actions_executed": 0,
        "truth_class": "PUBLIC_SOURCE_OBSERVATION",
        "authority_created": False,
        "external_effects": False,
    }
    _write_json(capital_root / "receipts" / "LATEST_DISCOVERY_CYCLE.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded DIO Capital & Support discovery projection cycle")
    parser.add_argument("--observations", type=Path, required=True, help="JSON file containing a list of public-source observation envelopes")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--search-budget", type=int, default=20)
    args = parser.parse_args()
    payload = json.loads(args.observations.read_text(encoding="utf-8"))
    observations = payload if isinstance(payload, list) else list(payload.get("observations") or [])
    print(json.dumps(run_cycle(args.root, observations, args.search_budget), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
