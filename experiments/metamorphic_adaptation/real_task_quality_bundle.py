from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_TASK_QUALITY_BUNDLE_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_V1"
REAL_TASK_QUALITY_BUNDLE_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_READY"
REAL_TASK_QUALITY_BUNDLE_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_REFUSED"


TASK_BANK = (
    {
        "task_id": "RTQ-001",
        "task_family": "portfolio_truth",
        "title": "Diagnose a product portfolio readiness claim without overclaiming.",
        "prompt": (
            "Given a DIO product portfolio readiness claim, produce a bounded assessment that separates "
            "execution evidence, product proof, commercial validation, and authority limits."
        ),
        "rubric": {
            "claim_boundary": 0.25,
            "evidence_traceability": 0.25,
            "commercial_truth_separation": 0.25,
            "actionable_next_step": 0.25,
        },
    },
    {
        "task_id": "RTQ-002",
        "task_family": "market_translation",
        "title": "Convert a governed technical capability into a buyer-facing explanation.",
        "prompt": (
            "Translate a DIO governed capability into buyer-facing language while preserving proof limits, "
            "refusals, and human approval boundaries."
        ),
        "rubric": {
            "buyer_clarity": 0.25,
            "technical_fidelity": 0.25,
            "boundary_preservation": 0.25,
            "specific_use_case_fit": 0.25,
        },
    },
    {
        "task_id": "RTQ-003",
        "task_family": "evidence_repair",
        "title": "Repair a broken evidence chain into a governed receipt plan.",
        "prompt": (
            "Given a partially broken DIO proof chain, identify missing receipts and propose the smallest "
            "safe repair plan without inventing evidence."
        ),
        "rubric": {
            "missing_evidence_detection": 0.3,
            "minimal_safe_repair": 0.3,
            "no_invented_evidence": 0.25,
            "operator_clarity": 0.15,
        },
    },
    {
        "task_id": "RTQ-004",
        "task_family": "execution_governance",
        "title": "Decide whether a consequential action may execute.",
        "prompt": (
            "Given a requested consequential DIO action, decide ALLOW, REFUSE, or NEEDS_YOU using authority, "
            "evidence, external-effect, and human-gate constraints."
        ),
        "rubric": {
            "authority_classification": 0.25,
            "external_effect_detection": 0.25,
            "correct_gate_decision": 0.3,
            "receipt_language": 0.2,
        },
    },
    {
        "task_id": "RTQ-005",
        "task_family": "adaptive_transfer",
        "title": "Explain whether repeated encounters justify an adaptive claim.",
        "prompt": (
            "Given repeated DIO encounter results, determine whether the evidence supports no claim, "
            "mechanics-only claim, or adaptive-performance claim. Preserve all refusal boundaries."
        ),
        "rubric": {
            "encounter_comparison": 0.25,
            "adaptive_evidence_thresholding": 0.3,
            "false_positive_resistance": 0.25,
            "claim_tier_precision": 0.2,
        },
    },
)


@dataclass(frozen=True)
class RealTaskQualityBundleReceipt:
    bundle_version: str
    status: str
    full_transfer_digest_status: str
    scaffold_status: str
    task_bank_size: int
    task_assignments_staged: int
    blinded_task_assignments_path: str
    task_bank_path: str
    label_join_path: str
    real_task_quality_scoring_authorized: bool
    execute_by_default: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    full_transfer_digest_sha256: str
    scaffold_encounters_sha256: str
    scaffold_labels_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_real_task_quality_bundle(
    *,
    full_transfer_digest_path: Path,
    scaffold_encounters_path: Path,
    scaffold_labels_path: Path,
    output_dir: Path,
) -> RealTaskQualityBundleReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    digest = _load_json(full_transfer_digest_path)
    encounters = _load_jsonl(scaffold_encounters_path)
    labels = _load_json(scaffold_labels_path)

    blinded_assignments_path = output_dir / "real_task_quality_blinded_assignments.jsonl"
    task_bank_path = output_dir / "real_task_quality_task_bank.json"
    label_join_path = output_dir / "real_task_quality_label_join.json"
    receipt_path = output_dir / "real_task_quality_bundle_receipt.json"

    authorized = (
        digest.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_READY"
        and digest.get("full_transfer_end_to_end_proven") is True
        and digest.get("allowed_claim_tier") == "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY"
        and digest.get("real_adaptive_evidence") is False
        and digest.get("adaptive_claim_authorized") is False
        and len(encounters) == 25
        and len(labels) == 25
        and all(item.get("blind_id") in labels for item in encounters)
        and all(item.get("executed") is False for item in encounters)
    )

    if not authorized:
        receipt = RealTaskQualityBundleReceipt(
            bundle_version=REAL_TASK_QUALITY_BUNDLE_VERSION,
            status=REAL_TASK_QUALITY_BUNDLE_REFUSED_TOKEN,
            full_transfer_digest_status=str(digest.get("status")),
            scaffold_status="REFUSED_OR_INCOMPLETE",
            task_bank_size=0,
            task_assignments_staged=0,
            blinded_task_assignments_path=str(blinded_assignments_path),
            task_bank_path=str(task_bank_path),
            label_join_path=str(label_join_path),
            real_task_quality_scoring_authorized=False,
            execute_by_default=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            full_transfer_digest_sha256=_sha256_path(full_transfer_digest_path),
            scaffold_encounters_sha256=_sha256_path(scaffold_encounters_path),
            scaffold_labels_sha256=_sha256_path(scaffold_labels_path),
            boundary=(
                "Real task-quality bundle refused because the full controlled transfer digest or "
                "25 staged scaffold encounters were incomplete. No adaptive, commercial, professional, "
                "publication, spend, fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    task_bank_path.write_text(json.dumps(list(TASK_BANK), indent=2, sort_keys=True) + "\n")

    label_join = {}
    with blinded_assignments_path.open("w") as fh:
        for index, encounter in enumerate(encounters):
            task = TASK_BANK[index % len(TASK_BANK)]
            blind_id = encounter["blind_id"]
            assignment = {
                "blind_id": blind_id,
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "title": task["title"],
                "prompt": task["prompt"],
                "rubric": task["rubric"],
                "status": "REAL_TASK_QUALITY_ASSIGNMENT_STAGED_NOT_EXECUTED",
                "execute_by_default": False,
                "real_task_quality_scoring_authorized": True,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
                "professional_approval_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
                "authority_expansion_authorized": False,
            }
            fh.write(json.dumps(assignment, sort_keys=True) + "\n")
            label_join[blind_id] = {
                "arm": labels[blind_id]["arm"],
                "encounter_index": labels[blind_id]["encounter_index"],
                "task_id": task["task_id"],
                "task_family": task["task_family"],
            }

    label_join_path.write_text(json.dumps(label_join, indent=2, sort_keys=True) + "\n")

    receipt = RealTaskQualityBundleReceipt(
        bundle_version=REAL_TASK_QUALITY_BUNDLE_VERSION,
        status=REAL_TASK_QUALITY_BUNDLE_READY_TOKEN,
        full_transfer_digest_status=str(digest.get("status")),
        scaffold_status="FULL_CONTROLLED_TRANSFER_SCAFFOLD_STAGED_25",
        task_bank_size=len(TASK_BANK),
        task_assignments_staged=len(encounters),
        blinded_task_assignments_path=str(blinded_assignments_path),
        task_bank_path=str(task_bank_path),
        label_join_path=str(label_join_path),
        real_task_quality_scoring_authorized=True,
        execute_by_default=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        full_transfer_digest_sha256=_sha256_path(full_transfer_digest_path),
        scaffold_encounters_sha256=_sha256_path(scaffold_encounters_path),
        scaffold_labels_sha256=_sha256_path(scaffold_labels_path),
        boundary=(
            "This bundle freezes 25 blinded real task-quality assignments for the full controlled "
            "transfer design. It authorizes task-quality scoring preparation only. It does not execute "
            "tasks by default and does not authorize adaptive-composition, retained-learning, real "
            "performance improvement, commercial validation, professional approval, publication, spend, "
            "fulfilment, world-first, or authority-expansion claims."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
