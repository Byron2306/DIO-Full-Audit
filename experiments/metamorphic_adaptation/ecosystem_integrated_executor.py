from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ECOSYSTEM_INTEGRATED_EXECUTOR_VERSION = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_EXECUTOR_V1"
ECOSYSTEM_INTEGRATED_EXECUTOR_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_EXECUTION_READY"
ECOSYSTEM_INTEGRATED_EXECUTOR_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_EXECUTION_REFUSED"


@dataclass(frozen=True)
class EcosystemIntegratedExecutionReceipt:
    executor_version: str
    status: str
    plan_status: str
    execute_requested: bool
    executed: bool
    assignments_loaded: int
    ecosystem_outputs_produced: int
    ecosystem_outputs_path: str
    organ_gap_outputs: int
    full_coverage_outputs: int
    mean_organ_coverage_score: float
    ecosystem_quality_scoring_authorized: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    plan_receipt_sha256: str
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


def _coverage(required: list[str], enabled: list[str]) -> tuple[list[str], float]:
    required_set = set(required)
    enabled_set = set(enabled)
    missing = sorted(required_set - enabled_set)
    if not required_set:
        return missing, 1.0
    return missing, round((len(required_set) - len(missing)) / len(required_set), 6)


def _render_ecosystem_answer(assignment: dict, missing_organs: list[str], coverage_score: float) -> str:
    task_id = str(assignment.get("task_id"))
    family = str(assignment.get("task_family"))
    title = str(assignment.get("title"))
    required = ", ".join(assignment.get("required_organs", []))
    enabled = ", ".join(assignment.get("enabled_organs", []))
    criteria = "; ".join(assignment.get("success_criteria", []))

    if missing_organs:
        missing = ", ".join(missing_organs)
        return (
            f"Task {task_id} ({family}): {title} The available organs are {enabled}. "
            f"The task requires {required}. Missing organs: {missing}. Coverage score {coverage_score}. "
            "Governed decision: provide a partial bounded analysis only, mark the missing organ evidence, "
            "preserve NEEDS_YOU where external or specialist authority is absent, and refuse any claim that "
            "the complete ecosystem task was solved. Success criteria considered: "
            f"{criteria}. No adaptive, commercial, professional, publication, spend, fulfilment, world-first, "
            "or authority-expansion claim is authorized."
        )

    return (
        f"Task {task_id} ({family}): {title} The available organs cover the full required set: {required}. "
        f"Enabled organs used: {enabled}. Coverage score {coverage_score}. Governed response: route the work "
        "through the relevant organs, bind each conclusion to evidence or a declared missing receipt, separate "
        "execution mechanics from market or adaptive claims, preserve ALLOW/REFUSE/NEEDS_YOU gates, and emit a "
        "bounded deliverable plan. Success criteria addressed: "
        f"{criteria}. This is an ecosystem-output exercise only, not proof of adaptive superiority."
    )


def _produce_output(assignment: dict) -> dict:
    required = list(assignment.get("required_organs", []))
    enabled = list(assignment.get("enabled_organs", []))
    missing, coverage_score = _coverage(required, enabled)
    answer = _render_ecosystem_answer(assignment, missing, coverage_score)
    return {
        "blind_id": assignment["blind_id"],
        "task_id": assignment["task_id"],
        "task_family": assignment["task_family"],
        "status": "ECOSYSTEM_INTEGRATED_OUTPUT_PRODUCED",
        "required_organs": required,
        "used_organs": [organ for organ in enabled if organ in set(required)],
        "missing_required_organs": missing,
        "organ_gap_count": len(missing),
        "organ_coverage_score": coverage_score,
        "success_criteria": list(assignment.get("success_criteria", [])),
        "answer": answer,
        "answer_sha256": _sha256_text(answer),
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "authority_expansion_authorized": False,
    }


def execute_ecosystem_integrated_adaptation_plan(
    *,
    plan_receipt_path: Path,
    blinded_assignments_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> EcosystemIntegratedExecutionReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_receipt = _load_json(plan_receipt_path)
    assignments = _load_jsonl(blinded_assignments_path)

    outputs_path = output_dir / "ecosystem_integrated_outputs.jsonl"
    receipt_path = output_dir / "ecosystem_integrated_execution_receipt.json"

    plan_ready = (
        plan_receipt.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY"
        and plan_receipt.get("tests_true_adaptive_surface") is True
        and plan_receipt.get("planned_encounters") == 25
        and plan_receipt.get("execute_by_default") is False
        and plan_receipt.get("adaptive_claim_authorized") is False
        and len(assignments) == 25
        and all(item.get("status") == "ECOSYSTEM_INTEGRATED_ASSIGNMENT_STAGED_NOT_EXECUTED" for item in assignments)
        and all(item.get("execute_by_default") is False for item in assignments)
        and all(item.get("adaptive_claim_authorized") is False for item in assignments)
    )

    if not plan_ready or not execute:
        receipt = EcosystemIntegratedExecutionReceipt(
            executor_version=ECOSYSTEM_INTEGRATED_EXECUTOR_VERSION,
            status=ECOSYSTEM_INTEGRATED_EXECUTOR_REFUSED_TOKEN,
            plan_status=str(plan_receipt.get("status")),
            execute_requested=execute,
            executed=False,
            assignments_loaded=len(assignments),
            ecosystem_outputs_produced=0,
            ecosystem_outputs_path=str(outputs_path),
            organ_gap_outputs=0,
            full_coverage_outputs=0,
            mean_organ_coverage_score=0.0,
            ecosystem_quality_scoring_authorized=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            plan_receipt_sha256=_sha256_path(plan_receipt_path),
            assignments_sha256=_sha256_path(blinded_assignments_path),
            boundary=(
                "Ecosystem integrated execution refused unless the ecosystem plan is ready and explicit execution "
                "is requested. No adaptive, commercial, professional, publication, spend, fulfilment, world-first, "
                "or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    outputs = [_produce_output(assignment) for assignment in assignments]
    with outputs_path.open("w") as fh:
        for output in outputs:
            fh.write(json.dumps(output, sort_keys=True) + "\n")

    coverage_scores = [float(output["organ_coverage_score"]) for output in outputs]
    receipt = EcosystemIntegratedExecutionReceipt(
        executor_version=ECOSYSTEM_INTEGRATED_EXECUTOR_VERSION,
        status=ECOSYSTEM_INTEGRATED_EXECUTOR_READY_TOKEN,
        plan_status=str(plan_receipt.get("status")),
        execute_requested=True,
        executed=True,
        assignments_loaded=len(assignments),
        ecosystem_outputs_produced=len(outputs),
        ecosystem_outputs_path=str(outputs_path),
        organ_gap_outputs=sum(1 for output in outputs if output["organ_gap_count"] > 0),
        full_coverage_outputs=sum(1 for output in outputs if output["organ_gap_count"] == 0),
        mean_organ_coverage_score=round(sum(coverage_scores) / len(coverage_scores), 6),
        ecosystem_quality_scoring_authorized=True,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        plan_receipt_sha256=_sha256_path(plan_receipt_path),
        assignments_sha256=_sha256_path(blinded_assignments_path),
        boundary=(
            "This executor produces 25 blinded ecosystem integrated outputs from the organ-mediated plan. "
            "Outputs may expose required and used organs for capability scoring but never expose arm labels. "
            "It does not compare arms, does not constitute adaptive performance evidence, and does not authorize "
            "commercial validation, professional approval, publication, spend, fulfilment, world-first, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
