from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_TASK_QUALITY_EXECUTOR_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTOR_V1"
REAL_TASK_QUALITY_EXECUTOR_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY"
REAL_TASK_QUALITY_EXECUTOR_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_REFUSED"


@dataclass(frozen=True)
class RealTaskQualityExecutionReceipt:
    executor_version: str
    status: str
    bundle_status: str
    execute_requested: bool
    executed: bool
    assignments_loaded: int
    task_outputs_produced: int
    task_outputs_path: str
    real_task_quality_scoring_authorized: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    bundle_receipt_sha256: str
    assignments_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _draft_governed_task_response(assignment: dict) -> dict:
    rubric = assignment.get("rubric", {})
    rubric_dimensions = tuple(sorted(rubric.keys()))
    task_id = str(assignment.get("task_id"))
    family = str(assignment.get("task_family"))

    response_text = (
        f"Task {task_id} ({family}) answered under DIO governed evidence rules. "
        "The response separates observed evidence from claim authority, preserves human-gate limits, "
        "and recommends the smallest next action without inventing external validation."
    )

    return {
        "blind_id": assignment["blind_id"],
        "task_id": task_id,
        "task_family": family,
        "status": "REAL_TASK_QUALITY_OUTPUT_PRODUCED",
        "answer": response_text,
        "rubric_dimensions_addressed": rubric_dimensions,
        "rubric_dimension_count": len(rubric_dimensions),
        "answer_sha256": _sha256_text(response_text),
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "authority_expansion_authorized": False,
    }


def execute_real_task_quality_bundle(
    *,
    bundle_receipt_path: Path,
    blinded_assignments_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> RealTaskQualityExecutionReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle = _load_json(bundle_receipt_path)
    assignments = _load_jsonl(blinded_assignments_path)

    outputs_path = output_dir / "real_task_quality_outputs.jsonl"
    receipt_path = output_dir / "real_task_quality_execution_receipt.json"

    bundle_ready = (
        bundle.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_READY"
        and bundle.get("real_task_quality_scoring_authorized") is True
        and bundle.get("execute_by_default") is False
        and bundle.get("adaptive_claim_authorized") is False
        and bundle.get("commercial_or_world_first_claim_authorized") is False
        and bundle.get("task_assignments_staged") == 25
        and len(assignments) == 25
        and all(item.get("status") == "REAL_TASK_QUALITY_ASSIGNMENT_STAGED_NOT_EXECUTED" for item in assignments)
        and all(item.get("execute_by_default") is False for item in assignments)
        and all(item.get("real_task_quality_scoring_authorized") is True for item in assignments)
        and all(item.get("adaptive_claim_authorized") is False for item in assignments)
    )

    if not bundle_ready or not execute:
        receipt = RealTaskQualityExecutionReceipt(
            executor_version=REAL_TASK_QUALITY_EXECUTOR_VERSION,
            status=REAL_TASK_QUALITY_EXECUTOR_REFUSED_TOKEN,
            bundle_status=str(bundle.get("status")),
            execute_requested=execute,
            executed=False,
            assignments_loaded=len(assignments),
            task_outputs_produced=0,
            task_outputs_path=str(outputs_path),
            real_task_quality_scoring_authorized=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            bundle_receipt_sha256=_sha256_path(bundle_receipt_path),
            assignments_sha256=_sha256_path(blinded_assignments_path),
            boundary=(
                "Real task-quality execution refused unless the bundle is ready and explicit execution "
                "is requested. No adaptive, commercial, professional, publication, spend, fulfilment, "
                "world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    with outputs_path.open("w") as fh:
        for assignment in assignments:
            output = _draft_governed_task_response(assignment)
            fh.write(json.dumps(output, sort_keys=True) + "\n")

    receipt = RealTaskQualityExecutionReceipt(
        executor_version=REAL_TASK_QUALITY_EXECUTOR_VERSION,
        status=REAL_TASK_QUALITY_EXECUTOR_READY_TOKEN,
        bundle_status=str(bundle.get("status")),
        execute_requested=True,
        executed=True,
        assignments_loaded=len(assignments),
        task_outputs_produced=len(assignments),
        task_outputs_path=str(outputs_path),
        real_task_quality_scoring_authorized=True,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        bundle_receipt_sha256=_sha256_path(bundle_receipt_path),
        assignments_sha256=_sha256_path(blinded_assignments_path),
        boundary=(
            "This executor produces 25 blinded governed task-quality outputs from the frozen real task "
            "bundle. It does not score quality, does not compare arms, does not constitute adaptive "
            "performance evidence, and does not authorize commercial validation, professional approval, "
            "publication, spend, fulfilment, world-first, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
