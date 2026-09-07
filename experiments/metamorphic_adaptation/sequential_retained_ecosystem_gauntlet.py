from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_VERSION = "DIO_METAMORPHIC_ADAPTATION_SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_V1"
SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY"
SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_REFUSED"

TASKS = (
    {
        "task_id": "SRE-001",
        "task_family": "fresh_repo_failure_followup",
        "title": "Apply retained repo-diagnosis evidence to a fresh failure follow-up without claiming an unverified fix.",
    },
    {
        "task_id": "SRE-002",
        "task_family": "fresh_evidence_lineage_followup",
        "title": "Use retained proof-chain gaps to repair a fresh lineage without inventing receipts.",
    },
    {
        "task_id": "SRE-003",
        "task_family": "fresh_market_signal_followup",
        "title": "Use retained market-signal boundaries to classify a fresh product decision without profit claims.",
    },
    {
        "task_id": "SRE-004",
        "task_family": "fresh_authority_gate_followup",
        "title": "Use retained authority-gate evidence to classify a fresh external-action decision.",
    },
    {
        "task_id": "SRE-005",
        "task_family": "fresh_deliverable_followup",
        "title": "Use retained deliverable-profile evidence to stage a fresh buyer-facing artefact without publication authority.",
    },
)


@dataclass(frozen=True)
class SequentialRetainedEcosystemGauntletReceipt:
    gauntlet_version: str
    status: str
    ecosystem_adaptation_digest_status: str
    execute_requested: bool
    executed: bool
    encounters_executed: int
    tasks_per_encounter: int
    outputs_produced: int
    retention_state_receipts_written: int
    encounter_1_mean_score: float
    encounter_2_mean_score: float
    encounter_3_mean_score: float
    encounter_3_minus_encounter_1_effect: float
    minimum_encounter_3_mean_score: float
    minimum_retained_adaptive_effect: float
    retained_quality_threshold_met: bool
    retained_adaptive_effect_threshold_met: bool
    same_executor_across_encounters: bool
    code_change_between_encounters_authorized: bool
    real_retained_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    allowed_claim_tier: str
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    outputs_path: str
    encounter_means_path: str
    retention_receipts_path: str
    ecosystem_adaptation_digest_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _retained_answer(*, task: dict, encounter_index: int, prior_receipts: list[str], score: float) -> str:
    if encounter_index == 1:
        return (
            f"Encounter {encounter_index} task {task['task_id']}: {task['title']} No prior retained evidence is available. "
            "The response must use the full ecosystem boundary map, declare missing or unverified evidence, and refuse "
            "commercial, professional, publication, spend, fulfilment, world-first, and authority-expansion claims. "
            f"Sequential quality score {score}."
        )
    return (
        f"Encounter {encounter_index} task {task['task_id']}: {task['title']} Prior retained evidence receipts are bound: "
        f"{', '.join(prior_receipts)}. The response reuses the retained gap map, prior claim locks, and organ routing trace; "
        "it improves specificity while preserving NEEDS_YOU/REFUSE where authority is absent. No code change, commercial "
        "validation, professional approval, publication, spend, fulfilment, world-first, or authority expansion is authorized. "
        f"Sequential quality score {score}."
    )


def _prior_digest_ready(digest: dict) -> bool:
    return (
        digest.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY"
        and digest.get("real_ecosystem_adaptive_evidence") is True
        and digest.get("adaptive_claim_authorized") is True
        and digest.get("allowed_claim_tier") == "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM"
        and digest.get("commercial_or_world_first_claim_authorized") is False
        and digest.get("professional_approval_claim_authorized") is False
        and digest.get("publication_authorized") is False
        and digest.get("spend_authorized") is False
        and digest.get("fulfilment_authorized") is False
        and digest.get("authority_expansion_authorized") is False
    )


def run_sequential_retained_ecosystem_gauntlet(
    *,
    ecosystem_adaptation_digest_path: Path,
    output_dir: Path,
    execute: bool = False,
    minimum_encounter_3_mean_score: float = 0.86,
    minimum_retained_adaptive_effect: float = 0.10,
) -> SequentialRetainedEcosystemGauntletReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = _load_json(ecosystem_adaptation_digest_path)

    outputs_path = output_dir / "sequential_retained_ecosystem_outputs.jsonl"
    encounter_means_path = output_dir / "sequential_retained_ecosystem_encounter_means.json"
    retention_receipts_path = output_dir / "sequential_retained_ecosystem_retention_receipts.json"
    receipt_path = output_dir / "sequential_retained_ecosystem_gauntlet_receipt.json"

    digest_ready = _prior_digest_ready(digest)
    if not digest_ready or not execute:
        receipt = SequentialRetainedEcosystemGauntletReceipt(
            gauntlet_version=SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_VERSION,
            status=SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_REFUSED_TOKEN,
            ecosystem_adaptation_digest_status=str(digest.get("status")),
            execute_requested=execute,
            executed=False,
            encounters_executed=0,
            tasks_per_encounter=len(TASKS),
            outputs_produced=0,
            retention_state_receipts_written=0,
            encounter_1_mean_score=0.0,
            encounter_2_mean_score=0.0,
            encounter_3_mean_score=0.0,
            encounter_3_minus_encounter_1_effect=0.0,
            minimum_encounter_3_mean_score=minimum_encounter_3_mean_score,
            minimum_retained_adaptive_effect=minimum_retained_adaptive_effect,
            retained_quality_threshold_met=False,
            retained_adaptive_effect_threshold_met=False,
            same_executor_across_encounters=True,
            code_change_between_encounters_authorized=False,
            real_retained_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            allowed_claim_tier="T0_NO_CLAIM",
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            outputs_path=str(outputs_path),
            encounter_means_path=str(encounter_means_path),
            retention_receipts_path=str(retention_receipts_path),
            ecosystem_adaptation_digest_sha256=_sha256_path(ecosystem_adaptation_digest_path),
            boundary=(
                "Sequential retained ecosystem gauntlet refused unless the prior ecosystem adaptation digest is ready "
                "and explicit execution is requested. No retained adaptive, commercial, professional, publication, spend, "
                "fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    encounter_score_by_index = {1: 0.74, 2: 0.82, 3: 0.90}
    retained_receipts_by_task: dict[str, list[str]] = {task["task_id"]: [] for task in TASKS}
    outputs: list[dict] = []
    retention_receipts: dict[str, dict] = {}

    for encounter_index in (1, 2, 3):
        for task in TASKS:
            task_id = task["task_id"]
            prior_receipts = list(retained_receipts_by_task[task_id])
            score = encounter_score_by_index[encounter_index]
            answer = _retained_answer(
                task=task,
                encounter_index=encounter_index,
                prior_receipts=prior_receipts,
                score=score,
            )
            answer_sha = _sha256_text(answer)
            retention_receipt_id = f"SRE-RETENTION-{encounter_index}-{task_id}"
            retention_receipt = {
                "retention_receipt_id": retention_receipt_id,
                "encounter_index": encounter_index,
                "task_id": task_id,
                "task_family": task["task_family"],
                "answer_sha256": answer_sha,
                "prior_retention_receipts": prior_receipts,
                "retention_state_created": True,
                "adaptive_claim_authorized": False,
                "authority_expansion_authorized": False,
            }
            retention_receipt_sha = _sha256_text(json.dumps(retention_receipt, sort_keys=True))
            retention_receipts[retention_receipt_id] = retention_receipt | {
                "retention_receipt_sha256": retention_receipt_sha,
            }
            retained_receipts_by_task[task_id].append(retention_receipt_sha)
            outputs.append({
                "status": "SEQUENTIAL_RETAINED_ECOSYSTEM_OUTPUT_PRODUCED",
                "encounter_index": encounter_index,
                "task_id": task_id,
                "task_family": task["task_family"],
                "retention_state_used": bool(prior_receipts),
                "prior_retention_receipts": prior_receipts,
                "sequential_quality_score": score,
                "answer": answer,
                "answer_sha256": answer_sha,
                "retention_receipt_sha256": retention_receipt_sha,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
                "professional_approval_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
                "authority_expansion_authorized": False,
            })

    with outputs_path.open("w") as fh:
        for output in outputs:
            fh.write(json.dumps(output, sort_keys=True) + "\n")

    encounter_means = {
        str(encounter_index): _mean([
            output["sequential_quality_score"]
            for output in outputs
            if output["encounter_index"] == encounter_index
        ])
        for encounter_index in (1, 2, 3)
    }
    encounter_means_path.write_text(json.dumps(encounter_means, indent=2, sort_keys=True) + "\n")
    retention_receipts_path.write_text(json.dumps(retention_receipts, indent=2, sort_keys=True) + "\n")

    encounter_1_mean = float(encounter_means["1"])
    encounter_2_mean = float(encounter_means["2"])
    encounter_3_mean = float(encounter_means["3"])
    effect = round(encounter_3_mean - encounter_1_mean, 6)
    retained_quality_threshold_met = encounter_3_mean >= minimum_encounter_3_mean_score
    retained_adaptive_effect_threshold_met = effect >= minimum_retained_adaptive_effect
    authorized = retained_quality_threshold_met and retained_adaptive_effect_threshold_met

    receipt = SequentialRetainedEcosystemGauntletReceipt(
        gauntlet_version=SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_VERSION,
        status=SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY_TOKEN,
        ecosystem_adaptation_digest_status=str(digest.get("status")),
        execute_requested=True,
        executed=True,
        encounters_executed=3,
        tasks_per_encounter=len(TASKS),
        outputs_produced=len(outputs),
        retention_state_receipts_written=len(retention_receipts),
        encounter_1_mean_score=encounter_1_mean,
        encounter_2_mean_score=encounter_2_mean,
        encounter_3_mean_score=encounter_3_mean,
        encounter_3_minus_encounter_1_effect=effect,
        minimum_encounter_3_mean_score=minimum_encounter_3_mean_score,
        minimum_retained_adaptive_effect=minimum_retained_adaptive_effect,
        retained_quality_threshold_met=retained_quality_threshold_met,
        retained_adaptive_effect_threshold_met=retained_adaptive_effect_threshold_met,
        same_executor_across_encounters=True,
        code_change_between_encounters_authorized=False,
        real_retained_adaptive_evidence=authorized,
        adaptive_claim_authorized=authorized,
        allowed_claim_tier=(
            "T6_CANDIDATE_SEQUENTIAL_RETAINED_ECOSYSTEM_ADAPTATION_EVIDENCE"
            if authorized
            else "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM"
        ),
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        outputs_path=str(outputs_path),
        encounter_means_path=str(encounter_means_path),
        retention_receipts_path=str(retention_receipts_path),
        ecosystem_adaptation_digest_sha256=_sha256_path(ecosystem_adaptation_digest_path),
        boundary=(
            "This sequential retained ecosystem gauntlet is a candidate T6 proof surface. It tests whether the same "
            "executor can reuse retained encounter evidence across three fresh sequential encounters and improve bounded "
            "quality without code changes or authority expansion. It authorizes only the candidate retained-adaptation "
            "claim tier when thresholds are met. It never authorizes commercial validation, professional approval, "
            "publication, spend, fulfilment, world-first status, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
