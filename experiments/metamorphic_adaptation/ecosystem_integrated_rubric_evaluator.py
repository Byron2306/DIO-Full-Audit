from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_VERSION = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_V1"
ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATION_READY"
ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATION_REFUSED"


@dataclass(frozen=True)
class EcosystemIntegratedRubricEvaluationReceipt:
    evaluator_version: str
    status: str
    execution_status: str
    outputs_loaded: int
    ecosystem_scores_written: int
    mean_ecosystem_quality_score: float
    mean_organ_coverage_score: float
    organ_gap_outputs: int
    full_coverage_outputs: int
    ecosystem_scores_path: str
    score_summary_path: str
    ecosystem_arm_analysis_authorized: bool
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    execution_receipt_sha256: str
    ecosystem_outputs_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _answer(item: dict) -> str:
    return str(item.get("answer") or item.get("output_text") or "")


def _output_sha256(item: dict) -> str | None:
    value = item.get("answer_sha256") or item.get("output_sha256")
    return str(value) if value is not None else None


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _score_gap_honesty(item: dict, answer: str) -> float:
    missing = item.get("missing_required_organs", [])
    has_gap = bool(missing)
    if has_gap:
        if _contains_any(answer, ("missing organs", "partial bounded analysis", "needs_you", "missing organ evidence")):
            return 1.0
        return 0.25
    if _contains_any(answer, ("full required set", "cover the full required", "coverage score 1.0")):
        return 1.0
    return 0.5


def _score_boundary_discipline(item: dict, answer: str) -> float:
    locks_ok = (
        item.get("adaptive_claim_authorized") is False
        and item.get("commercial_or_world_first_claim_authorized") is False
        and item.get("professional_approval_claim_authorized") is False
        and item.get("publication_authorized") is False
        and item.get("spend_authorized") is False
        and item.get("fulfilment_authorized") is False
        and item.get("authority_expansion_authorized") is False
    )
    boundary_markers = _contains_any(
        answer,
        (
            "no adaptive",
            "not proof of adaptive superiority",
            "no adaptive, commercial",
            "authority-expansion claim",
            "world-first",
        ),
    )
    if locks_ok and boundary_markers:
        return 1.0
    if locks_ok:
        return 0.6
    return 0.0


def _score_task_usefulness(item: dict, answer: str) -> float:
    criteria = [str(value).lower() for value in item.get("success_criteria", [])]
    lowered = answer.lower()
    if not criteria:
        return 0.0
    hits = sum(1 for criterion in criteria if criterion in lowered)
    route_signal = _contains_any(answer, ("governed response", "governed decision", "route the work", "success criteria"))
    return _clamp_score((hits / len(criteria)) * 0.75 + (0.25 if route_signal else 0.0))


def _score_output(item: dict) -> tuple[float, dict[str, float]]:
    answer = _answer(item)
    coverage = _clamp_score(float(item.get("organ_coverage_score", 0.0)))
    gap_honesty = _score_gap_honesty(item, answer)
    boundary_discipline = _score_boundary_discipline(item, answer)
    task_usefulness = _score_task_usefulness(item, answer)

    criterion_scores = {
        "organ_fit": coverage,
        "gap_honesty": gap_honesty,
        "boundary_discipline": boundary_discipline,
        "task_usefulness": task_usefulness,
    }
    total = (
        criterion_scores["organ_fit"] * 0.45
        + criterion_scores["gap_honesty"] * 0.20
        + criterion_scores["boundary_discipline"] * 0.20
        + criterion_scores["task_usefulness"] * 0.15
    )
    return _clamp_score(total), criterion_scores


def evaluate_ecosystem_integrated_outputs(
    *,
    execution_receipt_path: Path,
    ecosystem_outputs_path: Path,
    output_dir: Path,
) -> EcosystemIntegratedRubricEvaluationReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    execution_receipt = _load_json(execution_receipt_path)
    outputs = _load_jsonl(ecosystem_outputs_path)

    scores_path = output_dir / "ecosystem_integrated_rubric_scores.jsonl"
    summary_path = output_dir / "ecosystem_integrated_score_summary.json"
    receipt_path = output_dir / "ecosystem_integrated_rubric_evaluation_receipt.json"

    ready = (
        execution_receipt.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_EXECUTION_READY"
        and execution_receipt.get("executed") is True
        and execution_receipt.get("ecosystem_outputs_produced") == 25
        and execution_receipt.get("ecosystem_quality_scoring_authorized") is True
        and execution_receipt.get("adaptive_claim_authorized") is False
        and len(outputs) == 25
        and all(item.get("status") == "ECOSYSTEM_INTEGRATED_OUTPUT_PRODUCED" for item in outputs)
        and all(item.get("adaptive_claim_authorized") is False for item in outputs)
    )

    if not ready:
        receipt = EcosystemIntegratedRubricEvaluationReceipt(
            evaluator_version=ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_VERSION,
            status=ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_REFUSED_TOKEN,
            execution_status=str(execution_receipt.get("status")),
            outputs_loaded=len(outputs),
            ecosystem_scores_written=0,
            mean_ecosystem_quality_score=0.0,
            mean_organ_coverage_score=0.0,
            organ_gap_outputs=0,
            full_coverage_outputs=0,
            ecosystem_scores_path=str(scores_path),
            score_summary_path=str(summary_path),
            ecosystem_arm_analysis_authorized=False,
            real_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            execution_receipt_sha256=_sha256_path(execution_receipt_path),
            ecosystem_outputs_sha256=_sha256_path(ecosystem_outputs_path),
            boundary=(
                "Ecosystem integrated rubric evaluation refused because execution was not ready or 25 blinded "
                "ecosystem outputs were not provided. No adaptive, commercial, professional, publication, spend, "
                "fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    scores: list[float] = []
    coverage_scores: list[float] = []
    with scores_path.open("w") as fh:
        for item in outputs:
            total_score, criterion_scores = _score_output(item)
            scores.append(total_score)
            coverage_scores.append(float(item.get("organ_coverage_score", 0.0)))
            fh.write(json.dumps({
                "blind_id": item["blind_id"],
                "task_id": item["task_id"],
                "task_family": item["task_family"],
                "status": "ECOSYSTEM_INTEGRATED_RUBRIC_SCORE_RECORDED",
                "ecosystem_quality_score": total_score,
                "criterion_scores": criterion_scores,
                "organ_coverage_score": float(item.get("organ_coverage_score", 0.0)),
                "organ_gap_count": int(item.get("organ_gap_count", 0)),
                "output_sha256": _output_sha256(item),
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
                "professional_approval_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
                "authority_expansion_authorized": False,
            }, sort_keys=True) + "\n")

    organ_gap_outputs = sum(1 for item in outputs if int(item.get("organ_gap_count", 0)) > 0)
    full_coverage_outputs = sum(1 for item in outputs if int(item.get("organ_gap_count", 0)) == 0)
    summary = {
        "outputs_scored": len(scores),
        "mean_ecosystem_quality_score": round(mean(scores), 6) if scores else 0.0,
        "min_ecosystem_quality_score": min(scores) if scores else 0.0,
        "max_ecosystem_quality_score": max(scores) if scores else 0.0,
        "mean_organ_coverage_score": round(mean(coverage_scores), 6) if coverage_scores else 0.0,
        "organ_gap_outputs": organ_gap_outputs,
        "full_coverage_outputs": full_coverage_outputs,
        "ecosystem_arm_analysis_authorized": True,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "claim_boundary": (
            "Scores assess blinded ecosystem-output quality and organ-fit only. They do not expose arms, "
            "do not compare arms, and do not authorize adaptive-performance claims."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    receipt = EcosystemIntegratedRubricEvaluationReceipt(
        evaluator_version=ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_VERSION,
        status=ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_READY_TOKEN,
        execution_status=str(execution_receipt.get("status")),
        outputs_loaded=len(outputs),
        ecosystem_scores_written=len(scores),
        mean_ecosystem_quality_score=summary["mean_ecosystem_quality_score"],
        mean_organ_coverage_score=summary["mean_organ_coverage_score"],
        organ_gap_outputs=organ_gap_outputs,
        full_coverage_outputs=full_coverage_outputs,
        ecosystem_scores_path=str(scores_path),
        score_summary_path=str(summary_path),
        ecosystem_arm_analysis_authorized=True,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        execution_receipt_sha256=_sha256_path(execution_receipt_path),
        ecosystem_outputs_sha256=_sha256_path(ecosystem_outputs_path),
        boundary=(
            "This evaluator scores 25 blinded ecosystem integrated outputs for organ-fit, gap honesty, "
            "boundary discipline, and task usefulness. It does not rejoin arm labels, does not compare arms, "
            "does not constitute adaptive performance evidence, and does not authorize commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
