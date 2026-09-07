from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


FULL_TRANSFER_BLIND_EVALUATION_VERSION = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_V1"
FULL_TRANSFER_BLIND_EVALUATION_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_READY"
FULL_TRANSFER_BLIND_EVALUATION_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_REFUSED"


@dataclass(frozen=True)
class FullControlledTransferBlindEvaluationReceipt:
    evaluation_version: str
    status: str
    compatibility_status: str
    full_run_native_compatibility_proven: bool
    evaluated_blind_outputs: int
    blind_scores_path: str
    label_join_path: str
    real_native_mode: bool
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


def _native_score_proxy(item: dict) -> float:
    # Native smoke score only. This is not adaptive performance scoring.
    return 1.0 if (
        item.get("status") == "FULL_CONTROLLED_TRANSFER_NATIVE_PASSED"
        and item.get("exit_code") == 0
    ) else 0.0


def evaluate_full_transfer_blind_outputs(
    *,
    compatibility_verdict_path: Path,
    execution_receipts_path: Path,
    blind_labels_path: Path,
    output_dir: Path,
) -> FullControlledTransferBlindEvaluationReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    compatibility = _load_json(compatibility_verdict_path)
    execution_receipts = _load_jsonl(execution_receipts_path)
    blind_labels = _load_json(blind_labels_path)

    blind_scores_path = output_dir / "full_controlled_transfer_blind_scores.jsonl"
    label_join_path = output_dir / "full_controlled_transfer_blind_label_join.json"
    receipt_path = output_dir / "full_controlled_transfer_blind_evaluation_receipt.json"

    compatible = (
        compatibility.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_COMPATIBILITY_VERDICT_READY"
        and compatibility.get("full_run_native_compatibility_proven") is True
        and compatibility.get("ready_for_full_blind_evaluation") is True
        and compatibility.get("adaptive_claim_authorized") is False
        and len(execution_receipts) == 25
    )

    if not compatible:
        receipt = FullControlledTransferBlindEvaluationReceipt(
            evaluation_version=FULL_TRANSFER_BLIND_EVALUATION_VERSION,
            status=FULL_TRANSFER_BLIND_EVALUATION_REFUSED_TOKEN,
            compatibility_status=str(compatibility.get("status")),
            full_run_native_compatibility_proven=False,
            evaluated_blind_outputs=0,
            blind_scores_path=str(blind_scores_path),
            label_join_path=str(label_join_path),
            real_native_mode=True,
            real_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            boundary=(
                "Full controlled transfer blind evaluation refused because full-run native "
                "compatibility was not proven or 25 execution receipts were not provided. "
                "No adaptive, commercial, professional, publication, spend, fulfilment, "
                "world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    with blind_scores_path.open("w") as fh:
        for item in execution_receipts:
            blind_id = item["blind_id"]
            fh.write(json.dumps({
                "blind_id": blind_id,
                "status": "FULL_CONTROLLED_TRANSFER_BLIND_SCORE_RECORDED",
                "real_native_mode": True,
                "score": _native_score_proxy(item),
                "stdout_sha256": item["stdout_sha256"],
                "stderr_sha256": item["stderr_sha256"],
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
                "professional_approval_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
                "authority_expansion_authorized": False,
            }, sort_keys=True) + "\n")

    label_join_path.write_text(json.dumps(blind_labels, indent=2, sort_keys=True) + "\n")

    receipt = FullControlledTransferBlindEvaluationReceipt(
        evaluation_version=FULL_TRANSFER_BLIND_EVALUATION_VERSION,
        status=FULL_TRANSFER_BLIND_EVALUATION_READY_TOKEN,
        compatibility_status=str(compatibility.get("status")),
        full_run_native_compatibility_proven=True,
        evaluated_blind_outputs=len(execution_receipts),
        blind_scores_path=str(blind_scores_path),
        label_join_path=str(label_join_path),
        real_native_mode=True,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This full controlled transfer blind evaluation scores 25 native smoke outputs "
            "by blind identifier before label rejoin. It evaluates compatibility signals only, "
            "does not constitute adaptive performance evidence, does not claim improvement, "
            "and does not authorize commercial validation, professional approval, publication, "
            "spend, fulfilment, world-first, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
