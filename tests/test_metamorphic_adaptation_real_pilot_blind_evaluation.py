import json
import subprocess
import sys

from experiments.metamorphic_adaptation.real_pilot_blind_evaluation import (
    REAL_PILOT_BLIND_EVALUATION_READY_TOKEN,
    REAL_PILOT_BLIND_EVALUATION_REFUSED_TOKEN,
    REAL_PILOT_BLIND_EVALUATION_VERSION,
    evaluate_real_pilot_blind_outputs,
)


def _write_compatibility(path, *, ready=True):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_REFUSED"
        ),
        "real_pilot_native_compatibility_proven": ready,
        "ready_for_real_blind_evaluation": ready,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_execution_receipts(path, count=5):
    with path.open("w") as fh:
        for index in range(1, count + 1):
            fh.write(json.dumps({
                "blind_id": f"REAL-PILOT-BLIND-{index:04d}",
                "arm": "A_STATELESS_RESET",
                "encounter_index": 1,
                "status": "REAL_PILOT_NATIVE_PASSED",
                "executed": True,
                "real_native_mode": True,
                "exit_code": 0,
                "stdout_sha256": "a" * 64,
                "stderr_sha256": "b" * 64,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }, sort_keys=True) + "\n")


def _write_blind_labels(path, count=5):
    labels = {
        f"REAL-PILOT-BLIND-{index:04d}": {
            "arm": "A_STATELESS_RESET",
            "encounter_index": 1,
        }
        for index in range(1, count + 1)
    }
    path.write_text(json.dumps(labels, indent=2, sort_keys=True))


def test_real_pilot_blind_evaluation_scores_real_native_outputs(tmp_path):
    compatibility = tmp_path / "real_pilot_compatibility_verdict.json"
    receipts = tmp_path / "real_pilot_execution_receipts.jsonl"
    labels = tmp_path / "real_pilot_blind_labels.json"
    output = tmp_path / "blind"

    _write_compatibility(compatibility)
    _write_execution_receipts(receipts)
    _write_blind_labels(labels)

    receipt = evaluate_real_pilot_blind_outputs(
        compatibility_verdict_path=compatibility,
        execution_receipts_path=receipts,
        blind_labels_path=labels,
        output_dir=output,
    )

    assert receipt.evaluation_version == REAL_PILOT_BLIND_EVALUATION_VERSION
    assert receipt.status == REAL_PILOT_BLIND_EVALUATION_READY_TOKEN
    assert receipt.real_pilot_native_compatibility_proven is True
    assert receipt.evaluated_blind_outputs == 5
    assert receipt.real_native_mode is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False

    scores = (output / "real_pilot_blind_scores.jsonl").read_text().splitlines()
    assert len(scores) == 5

    first = json.loads(scores[0])
    assert first["blind_id"] == "REAL-PILOT-BLIND-0001"
    assert "arm" not in first
    assert first["score"] == 1.0
    assert first["status"] == "REAL_PILOT_BLIND_SCORE_RECORDED"


def test_real_pilot_blind_evaluation_refuses_without_compatibility(tmp_path):
    compatibility = tmp_path / "real_pilot_compatibility_verdict.json"
    receipts = tmp_path / "real_pilot_execution_receipts.jsonl"
    labels = tmp_path / "real_pilot_blind_labels.json"
    output = tmp_path / "blind"

    _write_compatibility(compatibility, ready=False)
    _write_execution_receipts(receipts)
    _write_blind_labels(labels)

    receipt = evaluate_real_pilot_blind_outputs(
        compatibility_verdict_path=compatibility,
        execution_receipts_path=receipts,
        blind_labels_path=labels,
        output_dir=output,
    )

    assert receipt.status == REAL_PILOT_BLIND_EVALUATION_REFUSED_TOKEN
    assert receipt.real_pilot_native_compatibility_proven is False
    assert receipt.evaluated_blind_outputs == 0
    assert receipt.adaptive_claim_authorized is False


def test_real_pilot_blind_evaluation_refuses_empty_receipts(tmp_path):
    compatibility = tmp_path / "real_pilot_compatibility_verdict.json"
    receipts = tmp_path / "real_pilot_execution_receipts.jsonl"
    labels = tmp_path / "real_pilot_blind_labels.json"
    output = tmp_path / "blind"

    _write_compatibility(compatibility)
    receipts.write_text("")
    labels.write_text("{}")

    receipt = evaluate_real_pilot_blind_outputs(
        compatibility_verdict_path=compatibility,
        execution_receipts_path=receipts,
        blind_labels_path=labels,
        output_dir=output,
    )

    assert receipt.status == REAL_PILOT_BLIND_EVALUATION_REFUSED_TOKEN
    assert receipt.evaluated_blind_outputs == 0
    assert receipt.real_adaptive_evidence is False


def test_real_pilot_blind_evaluation_writes_label_join_and_receipt(tmp_path):
    compatibility = tmp_path / "real_pilot_compatibility_verdict.json"
    receipts = tmp_path / "real_pilot_execution_receipts.jsonl"
    labels = tmp_path / "real_pilot_blind_labels.json"
    output = tmp_path / "blind"

    _write_compatibility(compatibility)
    _write_execution_receipts(receipts, count=2)
    _write_blind_labels(labels, count=2)

    receipt = evaluate_real_pilot_blind_outputs(
        compatibility_verdict_path=compatibility,
        execution_receipts_path=receipts,
        blind_labels_path=labels,
        output_dir=output,
    )

    data = json.loads((output / "real_pilot_blind_evaluation_receipt.json").read_text())
    joined = json.loads((output / "real_pilot_blind_label_join.json").read_text())

    assert data["status"] == receipt.status
    assert data["evaluated_blind_outputs"] == 2
    assert joined["REAL-PILOT-BLIND-0001"]["arm"] == "A_STATELESS_RESET"


def test_real_pilot_blind_evaluation_boundary_blocks_overclaiming(tmp_path):
    compatibility = tmp_path / "real_pilot_compatibility_verdict.json"
    receipts = tmp_path / "real_pilot_execution_receipts.jsonl"
    labels = tmp_path / "real_pilot_blind_labels.json"
    output = tmp_path / "blind"

    _write_compatibility(compatibility)
    _write_execution_receipts(receipts, count=1)
    _write_blind_labels(labels, count=1)

    receipt = evaluate_real_pilot_blind_outputs(
        compatibility_verdict_path=compatibility,
        execution_receipts_path=receipts,
        blind_labels_path=labels,
        output_dir=output,
    )

    boundary = receipt.boundary.lower()

    assert "scores native smoke outputs by blind identifier" in boundary
    assert "compatibility signals only" in boundary
    assert "does not constitute adaptive performance evidence" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_real_pilot_blind_evaluation_cli_runner(tmp_path):
    compatibility = tmp_path / "real_pilot_compatibility_verdict.json"
    receipts = tmp_path / "real_pilot_execution_receipts.jsonl"
    labels = tmp_path / "real_pilot_blind_labels.json"
    output = tmp_path / "blind"

    _write_compatibility(compatibility)
    _write_execution_receipts(receipts, count=2)
    _write_blind_labels(labels, count=2)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_pilot_blind_evaluation.py",
            "--compatibility-verdict",
            str(compatibility),
            "--execution-receipts",
            str(receipts),
            "--blind-labels",
            str(labels),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_PILOT_BLIND_EVALUATION_READY_TOKEN in completed.stdout
    assert (output / "real_pilot_blind_evaluation_receipt.json").exists()
    assert (output / "real_pilot_blind_scores.jsonl").exists()
    assert (output / "real_pilot_blind_label_join.json").exists()
