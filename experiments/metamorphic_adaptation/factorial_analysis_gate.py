from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


FACTORIAL_ANALYSIS_VERSION = "DIO_METAMORPHIC_ADAPTATION_FACTORIAL_ANALYSIS_V1"
FACTORIAL_ANALYSIS_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FACTORIAL_ANALYSIS_FIXTURE_READY"
FACTORIAL_ANALYSIS_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FACTORIAL_ANALYSIS_REFUSED"


@dataclass(frozen=True)
class FactorialAnalysisReceipt:
    analysis_version: str
    status: str
    fixture_mode: bool
    blind_scores_loaded: int
    arms_analyzed: int
    arm_means_path: str
    factor_effects_path: str
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def run_factorial_fixture_analysis(
    *,
    blind_scores_path: Path,
    label_join_path: Path,
    output_dir: Path,
) -> FactorialAnalysisReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    blind_scores = _load_jsonl(blind_scores_path)
    label_join = _load_json(label_join_path)

    arm_means_path = output_dir / "arm_means.json"
    factor_effects_path = output_dir / "factor_effects.json"

    if not blind_scores:
        receipt = FactorialAnalysisReceipt(
            analysis_version=FACTORIAL_ANALYSIS_VERSION,
            status=FACTORIAL_ANALYSIS_REFUSED_TOKEN,
            fixture_mode=True,
            blind_scores_loaded=0,
            arms_analyzed=0,
            arm_means_path=str(arm_means_path),
            factor_effects_path=str(factor_effects_path),
            real_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            boundary=(
                "Factorial analysis refused because no blind scores were provided. "
                "No adaptive, commercial, professional, publication, spend, fulfilment, "
                "world-first, or authority-expansion claim is authorized."
            ),
        )
        (output_dir / "factorial_analysis_receipt.json").write_text(
            json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n"
        )
        return receipt

    grouped: dict[str, list[float]] = {}
    for score in blind_scores:
        blind_id = score["blind_id"]
        arm = label_join[blind_id]["arm"]
        grouped.setdefault(arm, []).append(float(score["score"]))

    arm_means = {
        arm: {
            "mean_score": _mean(values),
            "n": len(values),
        }
        for arm, values in sorted(grouped.items())
    }

    def arm_mean(arm: str) -> float:
        return arm_means.get(arm, {}).get("mean_score", 0.0)

    factor_effects = {
        "semantic_retained_fixture_effect": round(
            arm_mean("C_SEMANTIC_RETAINED") - arm_mean("B_COMPOSITION_ONLY_NO_RETAINED_LEARNING"),
            6,
        ),
        "market_retained_fixture_effect": round(
            arm_mean("D_MARKET_RETAINED") - arm_mean("B_COMPOSITION_ONLY_NO_RETAINED_LEARNING"),
            6,
        ),
        "full_stack_fixture_effect": round(
            arm_mean("E_FULL_SEMANTIC_MARKET_BEAST") - arm_mean("A_STATELESS_RESET"),
            6,
        ),
        "fixture_mode": True,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    }

    arm_means_path.write_text(json.dumps(arm_means, indent=2, sort_keys=True) + "\n")
    factor_effects_path.write_text(json.dumps(factor_effects, indent=2, sort_keys=True) + "\n")

    receipt = FactorialAnalysisReceipt(
        analysis_version=FACTORIAL_ANALYSIS_VERSION,
        status=FACTORIAL_ANALYSIS_READY_TOKEN,
        fixture_mode=True,
        blind_scores_loaded=len(blind_scores),
        arms_analyzed=len(arm_means),
        arm_means_path=str(arm_means_path),
        factor_effects_path=str(factor_effects_path),
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        boundary=(
            "This factorial analysis summarizes fixture-mode blind scores after label rejoin. "
            "It proves analysis mechanics only, does not constitute real adaptive performance "
            "evidence, does not claim improvement, and does not authorize commercial, professional, "
            "publication, spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )

    (output_dir / "factorial_analysis_receipt.json").write_text(
        json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n"
    )
    return receipt
