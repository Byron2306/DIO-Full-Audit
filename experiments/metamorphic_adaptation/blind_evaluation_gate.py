from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


BLIND_EVALUATION_VERSION = "DIO_METAMORPHIC_ADAPTATION_BLIND_EVALUATION_V1"
BLIND_EVALUATION_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_BLIND_EVALUATION_FIXTURE_READY"
BLIND_EVALUATION_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_BLIND_EVALUATION_REFUSED"


@dataclass(frozen=True)
class BlindEvaluationReceipt:
    evaluation_version: str
    status: str
    fixture_mode: bool
    evaluated_blind_outputs: int
    blind_scores_path: str
    label_join_path: str
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


def evaluate_blind_fixture_outputs(
    *,
    executed_receipts_path: Path,
    blind_labels_path: Path,
    output_dir: Path,
) -> BlindEvaluationReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    executed = _load_jsonl(executed_receipts_path)
    labels = _load_json(blind_labels_path)

    blind_scores_path = output_dir / "blind_scores.jsonl"
    label_join_path = output_dir / "blind_label_join.json"

    if not executed:
        receipt = BlindEvaluationReceipt(
            evaluation_version=BLIND_EVALUATION_VERSION,
            status=BLIND_EVALUATION_REFUSED_TOKEN,
            fixture_mode=True,
            evaluated_blind_outputs=0,
            blind_scores_path=str(blind_scores_path),
            label_join_path=str(label_join_path),
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            boundary=(
                "Blind evaluation refused because no executed blind outputs were provided. "
                "No adaptive, commercial, professional, publication, spend, fulfilment, "
                "world-first, or authority-expansion claim is authorized."
            ),
        )
        (output_dir / "blind_evaluation_receipt.json").write_text(
            json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n"
        )
        return receipt

    with blind_scores_path.open("w") as fh:
        for item in executed:
            blind_id = item["blind_id"]

            # The evaluator consumes blind id and output hash/score proxy only.
            # Arm labels remain outside scoring and are rejoined only afterward.
            fh.write(json.dumps({
                "blind_id": blind_id,
                "status": "BLIND_SCORE_RECORDED",
                "fixture_mode": True,
                "output_sha256": item["output_sha256"],
                "score": item["score_proxy"],
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }, sort_keys=True) + "\n")

    label_join_path.write_text(json.dumps(labels, indent=2, sort_keys=True) + "\n")

    receipt = BlindEvaluationReceipt(
        evaluation_version=BLIND_EVALUATION_VERSION,
        status=BLIND_EVALUATION_READY_TOKEN,
        fixture_mode=True,
        evaluated_blind_outputs=len(executed),
        blind_scores_path=str(blind_scores_path),
        label_join_path=str(label_join_path),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        boundary=(
            "This blind evaluation gate scores fixture outputs by blind identifier before "
            "label rejoin. It proves evaluation mechanics only, does not constitute real "
            "adaptive performance evidence, does not claim improvement, and does not "
            "authorize commercial, professional, publication, spend, fulfilment, world-first, "
            "or authority-expansion claims."
        ),
    )

    (output_dir / "blind_evaluation_receipt.json").write_text(
        json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n"
    )
    return receipt
