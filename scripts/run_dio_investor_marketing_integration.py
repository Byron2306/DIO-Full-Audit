#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts" / "run_dio_marketing_integration.py"
STRATEGY_CONFIG_PATH = ROOT / "config" / "dio_investor_strategy.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("dio_marketing_base", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_module()
BASE_CHOOSE_HYPOTHESIS = base.choose_hypothesis
BASE_BUILD_HYPOTHESIS_RECORD = base.build_hypothesis_record

load_json = base.load_json
product_layers = base.product_layers
target_index = base.target_index
build_observation = base.build_observation
outreach_allowed = base.outreach_allowed
market_outreach_allowed = base.market_outreach_allowed


def strategy_config() -> dict[str, Any]:
    return json.loads(STRATEGY_CONFIG_PATH.read_text(encoding="utf-8"))


def _normalised_score(value: Any) -> float:
    raw = max(0.0, min(5.0, base.float_value(value)))
    return round(raw * 20.0, 2)


def _weighted_score(target: dict[str, str], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    breakdown = {key: _normalised_score(target.get(key)) for key in weights}
    total = sum(breakdown[key] * float(weight) for key, weight in weights.items())
    return round(total, 2), breakdown


def _pitch_signal_text(target: dict[str, str]) -> str:
    values = [
        target.get("investment_thesis"),
        target.get("investor_type"),
        target.get("stage"),
        target.get("geography"),
        target.get("partner_interests"),
        target.get("portfolio_pattern"),
        target.get("recent_signal"),
    ]
    return " ".join(str(value or "").lower() for value in values)


def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
    hits = []
    for keyword in keywords:
        token = str(keyword).strip().lower()
        if token and re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", text):
            hits.append(keyword)
    return hits


def select_pitch_thesis(target: dict[str, str], config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or strategy_config()
    text = _pitch_signal_text(target)
    ranked = []
    for index, thesis in enumerate(cfg.get("pitch_theses", [])):
        hits = _keyword_hits(text, list(thesis.get("keywords") or []))
        ranked.append((len(hits), -index, thesis, hits))
    if ranked:
        score, _, thesis, hits = max(ranked, key=lambda item: (item[0], item[1]))
        if score > 0:
            return {
                "id": thesis["id"],
                "name": thesis["name"],
                "hook": thesis["hook"],
                "proof_focus": list(thesis.get("proof_focus") or []),
                "matched_signals": hits,
                "match_score": score,
            }
    fallback = cfg["fallback_pitch_thesis"]
    return {
        "id": fallback["id"],
        "name": fallback["name"],
        "hook": fallback["hook"],
        "proof_focus": list(fallback.get("proof_focus") or []),
        "matched_signals": [],
        "match_score": 0,
    }


def build_investor_strategy(
    target: dict[str, str],
    product: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    cfg = strategy_config()
    fit_score, fit_breakdown = _weighted_score(target, cfg["fit_weights"])
    timing_score, timing_breakdown = _weighted_score(target, cfg["timing_weights"])
    route_state = target.get("route_state") or "RESEARCH_ONLY"
    route_score = int(config.get("route_priority", {}).get(route_state, 0))
    thresholds = cfg["timing_thresholds"]

    if route_score <= 0:
        timing_decision = "WATCH" if fit_score >= thresholds["watch_fit"] and timing_score >= thresholds["watch_timing"] else "HOLD"
    elif fit_score >= thresholds["approach_now_fit"] and timing_score >= thresholds["approach_now_timing"]:
        timing_decision = "APPROACH_NOW"
    elif fit_score >= thresholds["watch_fit"] and timing_score >= thresholds["watch_timing"]:
        timing_decision = "WATCH"
    else:
        timing_decision = "HOLD"

    pitch = select_pitch_thesis(target, cfg)
    return {
        "schema": "dio.investor_strategy_decision.v1",
        "target_type": "investor",
        "route_state": route_state,
        "route_score": route_score,
        "fit_score": fit_score,
        "fit_breakdown": fit_breakdown,
        "timing_score": timing_score,
        "timing_breakdown": timing_breakdown,
        "timing_decision": timing_decision,
        "pitch_thesis": pitch,
        "explanation": {
            "route": f"Existing Market Command route {route_state} retains precedence with route score {route_score}.",
            "fit": f"Investor fit is {fit_score}/100 from thesis, proof, capital-use, stage, cheque and geography fit.",
            "timing": f"Timing is {timing_score}/100 from base timing, recent signal, fund deployment and route freshness.",
            "pitch": f"Pitch thesis {pitch['id']} won from {len(pitch['matched_signals'])} matched public/registry signals.",
        },
        "permission_note": "Fit and timing never grant outreach permission; registry permission, DIO Legalis and operator approval remain separate gates.",
    }


def choose_hypothesis(
    product_line_id: str,
    hypotheses: list[dict[str, str]],
    targets: dict[tuple[str, str], dict[str, str]],
    product_config: dict[str, Any],
    route_priority: dict[str, int],
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    if str(product_config.get("target_type") or "buyer").lower() != "investor":
        return BASE_CHOOSE_HYPOTHESIS(product_line_id, hypotheses, targets, product_config, route_priority)

    runtime_config = config or {"route_priority": route_priority}
    candidates = []
    preferred = set(product_config.get("preferred_route_states") or [])
    registry_product_line_id = product_config.get("registry_product_line_id") or product_line_id
    for hypothesis in hypotheses:
        if hypothesis.get("product_line_id") != registry_product_line_id:
            continue
        target = targets.get((hypothesis.get("prospect_id", ""), registry_product_line_id), {})
        route_state = target.get("route_state") or "RESEARCH_ONLY"
        strategy = build_investor_strategy(target, product_config, runtime_config)
        candidates.append(
            (
                1 if route_state in preferred else 0,
                int(route_priority.get(route_state, 0)),
                strategy["fit_score"],
                strategy["timing_score"],
                base.float_value(hypothesis.get("attack_score")),
                -base.int_value(hypothesis.get("rank"), 99999),
                hypothesis,
                target,
            )
        )
    if not candidates:
        raise ValueError(f"No campaign hypothesis found for {product_line_id}")
    *_, hypothesis, target = max(candidates, key=lambda item: item[:6])
    return hypothesis, target


def build_hypothesis_record(
    config: dict[str, Any],
    archive_hash: str,
    hypothesis: dict[str, str],
    target: dict[str, str],
    product: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    record = BASE_BUILD_HYPOTHESIS_RECORD(config, archive_hash, hypothesis, target, product, observation)
    if str(product.get("target_type") or target.get("target_type") or "buyer").lower() != "investor":
        return record

    strategy = build_investor_strategy(target, product, config)
    record["investor_strategy"] = strategy
    record["experiment"]["public_hook"] = strategy["pitch_thesis"]["hook"]
    record["experiment"]["proof_focus"] = strategy["pitch_thesis"]["proof_focus"]
    record["experiment"]["timing_decision"] = strategy["timing_decision"]
    record["gates"]["timing_is_permission"] = False
    return record


def main() -> int:
    base.choose_hypothesis = choose_hypothesis
    base.build_hypothesis_record = build_hypothesis_record
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
