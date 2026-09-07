from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


REAL_TASK_QUALITY_BLIND_RUBRIC_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BLIND_RUBRIC_SCORING_V1"
REAL_TASK_QUALITY_BLIND_RUBRIC_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BLIND_RUBRIC_SCORING_READY"
REAL_TASK_QUALITY_BLIND_RUBRIC_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BLIND_RUBRIC_SCORING_REFUSED"


@dataclass(frozen=True)
class RealTaskQualityBlindRubricScoringReceipt:
    scoring_version: str
    status: str
    execution_status: str
    assignments_loaded: int
    outputs_loaded: int
    outputs_scored: int
    blind_scores_path: str
    mean_score: float
    min_score: float
    max_score: float
    real_quality_scores_available: bool
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    execution_receipt_sha256: str
    assignments_sha256: str
    task_outputs_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score_output(assignment: dict, output: dict) -> dict:
    rubric = assignment.get("rubric", {})
    addressed = set(output.get("rubric_dimensions_addressed", []))
    criterion_scores = {}

    for criterion, weight in rubric.items():
        criterion_scores[criterion] = float(weight) if criterion in addressed else 0.0

    score = round(sum(criterion_scores.values()), 6)
    return {
        "blind_id": output["blind_id"],
        "task_id": output["task_id"],
        "task_family": output["task_family"],
        "status": "REAL_TASK_QUALITY_BLIND_RUBRIC_SCORE_RECORDED",
        "score": score,
        "criterion_scores": criterion_scores,
        "scoring_method": "rubric_dimension_coverage_pre_label_rejoin",
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "authority_expansion_authorized": False,
    }


def score_real_task_quality_outputs(
    *,
    execution_receipt_path: Path,
    blinded_assignments_path: Path,
    task_outputs_path: Path,
    output_dir: Path,
) -> RealTaskQualityBlindRubricScoringReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    execution = _load_json(execution_receipt_path)
    assignments = _load_jsonl(blinded_assignments_path)
    outputs = _load_jsonl(task_outputs_path)

    blind_scores_path = output_dir / "real_task_quality_blind_scores.jsonl"
    receipt_path = output_dir / "real_task_quality_blind_rubric_scoring_receipt.json"

    assignments_by_blind = {item.get("blind_id"): item for item in assignments}
    outputs_by_blind = {item.get("blind_id"): item for item in outputs}

    ready = (
        execution.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY"
        and execution.get("executed") is True
        and execution.get("task_outputs_produced") == 25
        and execution.get("real_task_quality_scoring_authorized") is True
        and execution.get("adaptive_claim_authorized") is False
        and execution.get("commercial_or_world_first_claim_authorized") is False
        and len(assignments) == 25
        and len(outputs) == 25
        and set(assignments_by_blind) == set(outputs_by_blind)
        and all(item.get("real_task_quality_scoring_authorized") is True for item in assignments)
        and all(item.get("adaptive_claim_authorized") is False for item in assignments)
        and all(item.get("status") == "REAL_TASK_QUALITY_OUTPUT_PRODUCED" for item in outputs)
        and all(item.get("adaptive_claim_authorized") is False for item in outputs)
    )

    if not ready:
        receipt = RealTaskQualityBlindRubricScoringReceipt(
            scoring_version=REAL_TASK_QUALITY_BLIND_RUBRIC_VERSION,
            status=REAL_TASK_QUALITY_BLIND_RUBRIC_REFUSED_TOKEN,
            execution_status=str(execution.get("status")),
            assignments_loaded=len(assignments),
            outputs_loaded=len(outputs),
            outputs_scored=0,
            blind_scores_path=str(blind_scores_path),
            mean_score=0.0,
            min_score=0.0,
            max_score=0.0,
            real_quality_scores_available=False,
            real_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            execution_receipt_sha256=_sha256_path(execution_receipt_path),
            assignments_sha256=_sha256_path(blinded_assignments_path),
            task_outputs_sha256=_sha256_path(task_outputs_path),
            boundary=(
                "Blind rubric scoring refused because execution was not ready or the 25 assignment/output "
                "records were incomplete. No adaptive, commercial, professional, publication, spend, "
                "fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    scored = []
    with blind_scores_path.open("w") as fh:
        for blind_id in sorted(outputs_by_blind):
            score = _score_output(assignments_by_blind[blind_id], outputs_by_blind[blind_id])
            scored.append(score)
            fh.write(json.dumps(score, sort_keys=True) + "\n")

    score_values = [item["score"] for item in scored]
    receipt = RealTaskQualityBlindRubricScoringReceipt(
        scoring_version=REAL_TASK_QUALITY_BLIND_RUBRIC_VERSION,
        status=REAL_TASK_QUALITY_BLIND_RUBRIC_READY_TOKEN,
        execution_status=str(execution.get("status")),
        assignments_loaded=len(assignments),
        outputs_loaded=len(outputs),
        outputs_scored=len(scored),
        blind_scores_path=str(blind_scores_path),
        mean_score=round(mean(score_values), 6),
        min_score=min(score_values),
        max_score=max(score_values),
        real_quality_scores_available=True,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        execution_receipt_sha256=_sha256_path(execution_receipt_path),
        assignments_sha256=_sha256_path(blinded_assignments_path),
        task_outputs_sha256=_sha256_path(task_outputs_path),
        boundary=(
            "This gate scores 25 blinded task outputs against their rubrics before label rejoin. It does "
            "not rejoin arms, does not compare arms, does not constitute adaptive performance evidence, "
            "and does not authorize commercial validation, professional approval, publication, spend, "
            "fulfilment, world-first, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
