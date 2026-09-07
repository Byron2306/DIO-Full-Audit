from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


FULL_TRANSFER_FACTORIAL_VERSION = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_FACTORIAL_ANALYSIS_V1"
FULL_TRANSFER_FACTORIAL_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_FACTORIAL_ANALYSIS_READY"
FULL_TRANSFER_FACTORIAL_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_FACTORIAL_ANALYSIS_REFUSED"


@dataclass(frozen=True)
class FullControlledTransferFactorialAnalysisReceipt:
    analysis_version: str
    status: str
    blind_evaluation_status: str
    scores_loaded: int
    labels_loaded: int
    arms_analyzed: int
    arm_means_path: str
    factor_effects_path: str
    best_arm: str
    best_arm_mean: float
    baseline_arm: str
    baseline_arm_mean: float
    full_minus_baseline_effect: float
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def analyze_full_controlled_transfer_scores(
    *,
    blind_evaluation_receipt_path: Path,
    blind_scores_path: Path,
    label_join_path: Path,
    output_dir: Path,
) -> FullControlledTransferFactorialAnalysisReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    blind_receipt = _load_json(blind_evaluation_receipt_path)
    scores = _load_jsonl(blind_scores_path)
    labels = _load_json(label_join_path)

    arm_means_path = output_dir / "full_controlled_transfer_arm_means.json"
    factor_effects_path = output_dir / "full_controlled_transfer_factor_effects.json"
    receipt_path = output_dir / "full_controlled_transfer_factorial_analysis_receipt.json"

    ready = (
        blind_receipt.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_READY"
        and blind_receipt.get("evaluated_blind_outputs") == 25
        and blind_receipt.get("real_adaptive_evidence") is False
        and blind_receipt.get("adaptive_claim_authorized") is False
        and len(scores) == 25
        and len(labels) == 25
    )

    if not ready:
        receipt = FullControlledTransferFactorialAnalysisReceipt(
            analysis_version=FULL_TRANSFER_FACTORIAL_VERSION,
            status=FULL_TRANSFER_FACTORIAL_REFUSED_TOKEN,
            blind_evaluation_status=str(blind_receipt.get("status")),
            scores_loaded=len(scores),
            labels_loaded=len(labels),
            arms_analyzed=0,
            arm_means_path=str(arm_means_path),
            factor_effects_path=str(factor_effects_path),
            best_arm="",
            best_arm_mean=0.0,
            baseline_arm="A_STATELESS_RESET",
            baseline_arm_mean=0.0,
            full_minus_baseline_effect=0.0,
            real_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            boundary=(
                "Full controlled transfer factorial analysis refused because blind evaluation "
                "was not ready or the 25 score/label records were incomplete. No adaptive, "
                "commercial, professional, publication, spend, fulfilment, world-first, or "
                "authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    by_arm: dict[str, list[float]] = {}
    for score_item in scores:
        blind_id = score_item["blind_id"]
        label = labels[blind_id]
        arm = label["arm"]
        by_arm.setdefault(arm, []).append(float(score_item["score"]))

    arm_means = {
        arm: {
            "n": len(values),
            "mean": mean(values),
            "scores": values,
        }
        for arm, values in sorted(by_arm.items())
    }

    baseline_arm = "A_STATELESS_RESET"
    full_arm = "E_FULL_SEMANTIC_MARKET_BEAST"
    baseline_mean = float(arm_means.get(baseline_arm, {}).get("mean", 0.0))
    full_mean = float(arm_means.get(full_arm, {}).get("mean", 0.0))
    effect = full_mean - baseline_mean

    best_arm, best_payload = max(
        arm_means.items(),
        key=lambda item: (item[1]["mean"], item[0]),
    )

    factor_effects = {
        "baseline_arm": baseline_arm,
        "full_arm": full_arm,
        "baseline_arm_mean": baseline_mean,
        "full_arm_mean": full_mean,
        "full_minus_baseline_effect": effect,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "claim_boundary": (
            "Smoke-score factorial analysis cannot prove adaptation. A future claim would require "
            "real task-quality scoring, repeated encounters, predeclared thresholds, and guardrail review."
        ),
    }

    arm_means_path.write_text(json.dumps(arm_means, indent=2, sort_keys=True) + "\n")
    factor_effects_path.write_text(json.dumps(factor_effects, indent=2, sort_keys=True) + "\n")

    receipt = FullControlledTransferFactorialAnalysisReceipt(
        analysis_version=FULL_TRANSFER_FACTORIAL_VERSION,
        status=FULL_TRANSFER_FACTORIAL_READY_TOKEN,
        blind_evaluation_status=str(blind_receipt.get("status")),
        scores_loaded=len(scores),
        labels_loaded=len(labels),
        arms_analyzed=len(arm_means),
        arm_means_path=str(arm_means_path),
        factor_effects_path=str(factor_effects_path),
        best_arm=best_arm,
        best_arm_mean=float(best_payload["mean"]),
        baseline_arm=baseline_arm,
        baseline_arm_mean=baseline_mean,
        full_minus_baseline_effect=effect,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This full controlled transfer factorial analysis groups 25 blind smoke scores by arm. "
            "It analyzes compatibility-score structure only. It does not constitute adaptive "
            "performance evidence, does not claim improvement, and does not authorize commercial "
            "validation, professional approval, publication, spend, fulfilment, world-first, or "
            "authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
