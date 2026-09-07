from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


REAL_TASK_QUALITY_RUBRIC_EVALUATOR_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATOR_V1"
REAL_TASK_QUALITY_RUBRIC_EVALUATOR_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_READY"
REAL_TASK_QUALITY_RUBRIC_EVALUATOR_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_REFUSED"


FROZEN_RUBRICS_BY_TASK_ID = {
    "RTQ-001": {
        "claim_boundary": 0.25,
        "evidence_traceability": 0.25,
        "commercial_truth_separation": 0.25,
        "actionable_next_step": 0.25,
    },
    "RTQ-002": {
        "buyer_clarity": 0.25,
        "technical_fidelity": 0.25,
        "boundary_preservation": 0.25,
        "specific_use_case_fit": 0.25,
    },
    "RTQ-003": {
        "missing_evidence_detection": 0.3,
        "minimal_safe_repair": 0.3,
        "no_invented_evidence": 0.25,
        "operator_clarity": 0.15,
    },
    "RTQ-004": {
        "authority_classification": 0.25,
        "external_effect_detection": 0.25,
        "correct_gate_decision": 0.3,
        "receipt_language": 0.2,
    },
    "RTQ-005": {
        "encounter_comparison": 0.25,
        "adaptive_evidence_thresholding": 0.3,
        "false_positive_resistance": 0.25,
        "claim_tier_precision": 0.2,
    },
}


@dataclass(frozen=True)
class RealTaskQualityRubricEvaluationReceipt:
    evaluator_version: str
    status: str
    execution_status: str
    outputs_loaded: int
    rubric_scores_written: int
    mean_quality_score: float
    rubric_scores_path: str
    score_summary_path: str
    real_task_quality_evaluation_authorized: bool
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    execution_receipt_sha256: str
    task_outputs_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _output_text(item: dict) -> str:
    """Return the blinded output text, tolerating both executor-era field names."""
    return str(item.get("output_text") or item.get("answer") or "")


def _output_sha256(item: dict) -> str | None:
    value = item.get("output_sha256") or item.get("answer_sha256")
    return str(value) if value is not None else None


def _rubric_for_output(item: dict) -> dict[str, float]:
    """Return an attached rubric, or recover the frozen rubric by task_id.

    Early executor outputs intentionally carried only blind task metadata and answer
    text, so the evaluator must be able to recover the frozen scoring rubric from
    the task identifier without rejoining arm labels.
    """
    attached = item.get("rubric")
    if isinstance(attached, dict) and attached:
        return {str(key): float(value) for key, value in attached.items()}

    task_id = str(item.get("task_id", ""))
    recovered = FROZEN_RUBRICS_BY_TASK_ID.get(task_id, {})
    return {str(key): float(value) for key, value in recovered.items()}


def _criterion_score(*, output_text: str, criterion: str) -> float:
    text = output_text.lower()
    tokens = criterion.lower().replace("_", " ").split()
    direct_hits = sum(1 for token in tokens if token in text)
    boundary_hits = sum(
        1
        for marker in (
            "claim",
            "evidence",
            "boundary",
            "refuse",
            "allow",
            "needs_you",
            "receipt",
            "commercial",
            "authority",
            "next step",
            "next action",
            "human-gate",
            "external validation",
        )
        if marker in text
    )
    length_signal = 1 if len(output_text.strip()) >= 120 else 0
    raw = direct_hits + min(boundary_hits, 4) + length_signal
    return min(1.0, raw / 5.0)


def _score_output(item: dict) -> tuple[float, dict[str, float]]:
    text = _output_text(item)
    rubric = _rubric_for_output(item)
    if not rubric:
        return 0.0, {}

    criterion_scores: dict[str, float] = {}
    weighted_total = 0.0
    weight_total = 0.0
    for criterion, weight in rubric.items():
        numeric_weight = float(weight)
        score = _criterion_score(output_text=text, criterion=str(criterion))
        criterion_scores[str(criterion)] = score
        weighted_total += score * numeric_weight
        weight_total += numeric_weight

    if weight_total <= 0:
        return 0.0, criterion_scores
    return round(weighted_total / weight_total, 6), criterion_scores


def evaluate_real_task_quality_rubrics(
    *,
    execution_receipt_path: Path,
    task_outputs_path: Path,
    output_dir: Path,
) -> RealTaskQualityRubricEvaluationReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    execution_receipt = _load_json(execution_receipt_path)
    task_outputs = _load_jsonl(task_outputs_path)

    rubric_scores_path = output_dir / "real_task_quality_rubric_scores.jsonl"
    score_summary_path = output_dir / "real_task_quality_score_summary.json"
    receipt_path = output_dir / "real_task_quality_rubric_evaluation_receipt.json"

    ready = (
        execution_receipt.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY"
        and execution_receipt.get("executed") is True
        and execution_receipt.get("task_outputs_produced") == 25
        and execution_receipt.get("real_task_quality_scoring_authorized") is True
        and execution_receipt.get("adaptive_claim_authorized") is False
        and len(task_outputs) == 25
        and all(item.get("adaptive_claim_authorized") is False for item in task_outputs)
    )

    if not ready:
        receipt = RealTaskQualityRubricEvaluationReceipt(
            evaluator_version=REAL_TASK_QUALITY_RUBRIC_EVALUATOR_VERSION,
            status=REAL_TASK_QUALITY_RUBRIC_EVALUATOR_REFUSED_TOKEN,
            execution_status=str(execution_receipt.get("status")),
            outputs_loaded=len(task_outputs),
            rubric_scores_written=0,
            mean_quality_score=0.0,
            rubric_scores_path=str(rubric_scores_path),
            score_summary_path=str(score_summary_path),
            real_task_quality_evaluation_authorized=False,
            real_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            execution_receipt_sha256=_sha256_path(execution_receipt_path),
            task_outputs_sha256=_sha256_path(task_outputs_path),
            boundary=(
                "Real task-quality rubric evaluation refused because execution was not ready or "
                "25 blinded task outputs were not provided. No adaptive, commercial, professional, "
                "publication, spend, fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    scores: list[float] = []
    with rubric_scores_path.open("w") as fh:
        for item in task_outputs:
            total_score, criterion_scores = _score_output(item)
            scores.append(total_score)
            fh.write(json.dumps({
                "blind_id": item["blind_id"],
                "task_id": item["task_id"],
                "task_family": item["task_family"],
                "status": "REAL_TASK_QUALITY_RUBRIC_SCORE_RECORDED",
                "quality_score": total_score,
                "criterion_scores": criterion_scores,
                "output_sha256": _output_sha256(item),
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
                "professional_approval_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
                "authority_expansion_authorized": False,
            }, sort_keys=True) + "\n")

    summary = {
        "outputs_scored": len(scores),
        "mean_quality_score": round(mean(scores), 6) if scores else 0.0,
        "min_quality_score": min(scores) if scores else 0.0,
        "max_quality_score": max(scores) if scores else 0.0,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "claim_boundary": (
            "Rubric scores assess blinded task-output quality only. They do not compare arms, "
            "do not prove adaptation, and do not authorize performance-improvement claims."
        ),
    }
    score_summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    receipt = RealTaskQualityRubricEvaluationReceipt(
        evaluator_version=REAL_TASK_QUALITY_RUBRIC_EVALUATOR_VERSION,
        status=REAL_TASK_QUALITY_RUBRIC_EVALUATOR_READY_TOKEN,
        execution_status=str(execution_receipt.get("status")),
        outputs_loaded=len(task_outputs),
        rubric_scores_written=len(scores),
        mean_quality_score=summary["mean_quality_score"],
        rubric_scores_path=str(rubric_scores_path),
        score_summary_path=str(score_summary_path),
        real_task_quality_evaluation_authorized=True,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        execution_receipt_sha256=_sha256_path(execution_receipt_path),
        task_outputs_sha256=_sha256_path(task_outputs_path),
        boundary=(
            "This evaluator scores 25 blinded real task-quality outputs against the frozen rubrics. "
            "It accepts either output_text or answer fields from compatible executors and can recover "
            "frozen rubrics by task_id without rejoining arm labels. It does not compare arms, does not "
            "constitute adaptive performance evidence, and does not authorize commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
