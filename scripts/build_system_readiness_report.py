#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "system_readiness_scorecard.json"
OUTPUT_JSON = ROOT / "state" / "audits" / "SYSTEM_READINESS_2026-08-09.json"


def main() -> int:
    scorecard = json.loads(SOURCE.read_text(encoding="utf-8"))
    weights = scorecard["weights"]
    dimensions = list(weights)
    weight_values = [float(weights[name]) for name in dimensions]
    results = []
    for system in scorecard["systems"]:
        dimensions_scored = dict(zip(dimensions, system["scores"], strict=True))
        weighted = round(sum(score * weight for score, weight in zip(system["scores"], weight_values, strict=True)), 1)
        controlled = round(
            sum(score * weight for name, score, weight in zip(dimensions, system["scores"], weight_values, strict=True) if name != "external_validation")
            / (1 - weights["external_validation"]),
            1,
        )
        results.append({**system, "dimensions": dimensions_scored, "score": weighted, "controlled_pilot_score": controlled})
    payload = {
        "schema": "dio.system_readiness_result.v1",
        "assessed_at": scorecard["assessed_at"],
        "scoring": scorecard["weights"],
        "overall_score": round(sum(row["score"] for row in results) / len(results), 1),
        "controlled_pilot_score": round(sum(row["controlled_pilot_score"] for row in results) / len(results), 1),
        "external_validation_score": round(sum(row["dimensions"]["external_validation"] for row in results) / len(results), 1),
        "systems": results,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
