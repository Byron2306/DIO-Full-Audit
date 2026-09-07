import json
import subprocess
import sys

from experiments.metamorphic_adaptation.blind_evaluation_gate import (
    BLIND_EVALUATION_READY_TOKEN,
    BLIND_EVALUATION_REFUSED_TOKEN,
    BLIND_EVALUATION_VERSION,
    evaluate_blind_fixture_outputs,
)


def _write_executed(path, count=5):
    with path.open("w") as fh:
        for index in range(1, count + 1):
            fh.write(json.dumps({
                "blind_id": f"BLIND-{index:04d}",
                "arm": "A_STATELESS_RESET",
                "encounter_index": index,
                "status": "EXECUTED_FIXTURE",
                "fixture_mode": True,
                "output_sha256": "a" * 64,
                "score_proxy": round(0.1 + index * 0.01, 4),
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }, sort_keys=True) + "\n")


def _write_labels(path, count=5):
    labels = {
        f"BLIND-{index:04d}": {
            "arm": "A_STATELESS_RESET",
            "encounter_index": index,
        }
        for index in range(1, count + 1)
    }
    path.write_text(json.dumps(labels, indent=2, sort_keys=True))


def test_blind_evaluation_scores_outputs_by_blind_id(tmp_path):
    executed = tmp_path / "executed_encounter_receipts.jsonl"
    labels = tmp_path / "blind_labels.json"
    output = tmp_path / "blind_eval"

    _write_executed(executed, count=5)
    _write_labels(labels, count=5)

    receipt = evaluate_blind_fixture_outputs(
        executed_receipts_path=executed,
        blind_labels_path=labels,
        output_dir=output,
    )

    assert receipt.evaluation_version == BLIND_EVALUATION_VERSION
    assert receipt.status == BLIND_EVALUATION_READY_TOKEN
    assert receipt.fixture_mode is True
    assert receipt.evaluated_blind_outputs == 5
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False

    scores = (output / "blind_scores.jsonl").read_text().splitlines()
    assert len(scores) == 5

    first = json.loads(scores[0])
    assert first["blind_id"] == "BLIND-0001"
    assert "arm" not in first
    assert first["status"] == "BLIND_SCORE_RECORDED"
    assert first["score"] == 0.11


def test_blind_evaluation_rejoins_labels_after_scoring(tmp_path):
    executed = tmp_path / "executed_encounter_receipts.jsonl"
    labels = tmp_path / "blind_labels.json"
    output = tmp_path / "blind_eval"

    _write_executed(executed, count=3)
    _write_labels(labels, count=3)

    evaluate_blind_fixture_outputs(
        executed_receipts_path=executed,
        blind_labels_path=labels,
        output_dir=output,
    )

    joined = json.loads((output / "blind_label_join.json").read_text())

    assert joined["BLIND-0001"]["arm"] == "A_STATELESS_RESET"
    assert joined["BLIND-0001"]["encounter_index"] == 1


def test_blind_evaluation_refuses_empty_outputs(tmp_path):
    executed = tmp_path / "executed_encounter_receipts.jsonl"
    labels = tmp_path / "blind_labels.json"
    output = tmp_path / "blind_eval"

    executed.write_text("")
    labels.write_text("{}")

    receipt = evaluate_blind_fixture_outputs(
        executed_receipts_path=executed,
        blind_labels_path=labels,
        output_dir=output,
    )

    assert receipt.status == BLIND_EVALUATION_REFUSED_TOKEN
    assert receipt.evaluated_blind_outputs == 0
    assert receipt.adaptive_claim_authorized is False


def test_blind_evaluation_writes_top_level_receipt(tmp_path):
    executed = tmp_path / "executed_encounter_receipts.jsonl"
    labels = tmp_path / "blind_labels.json"
    output = tmp_path / "blind_eval"

    _write_executed(executed, count=2)
    _write_labels(labels, count=2)

    receipt = evaluate_blind_fixture_outputs(
        executed_receipts_path=executed,
        blind_labels_path=labels,
        output_dir=output,
    )

    data = json.loads((output / "blind_evaluation_receipt.json").read_text())

    assert data["status"] == receipt.status
    assert data["evaluated_blind_outputs"] == 2
    assert data["adaptive_claim_authorized"] is False


def test_blind_evaluation_boundary_blocks_overclaiming(tmp_path):
    executed = tmp_path / "executed_encounter_receipts.jsonl"
    labels = tmp_path / "blind_labels.json"
    output = tmp_path / "blind_eval"

    _write_executed(executed, count=1)
    _write_labels(labels, count=1)

    receipt = evaluate_blind_fixture_outputs(
        executed_receipts_path=executed,
        blind_labels_path=labels,
        output_dir=output,
    )

    boundary = receipt.boundary.lower()

    assert "blind identifier before label rejoin" in boundary
    assert "proves evaluation mechanics only" in boundary
    assert "does not constitute real adaptive performance evidence" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_blind_evaluation_cli_runner(tmp_path):
    executed = tmp_path / "executed_encounter_receipts.jsonl"
    labels = tmp_path / "blind_labels.json"
    output = tmp_path / "blind_eval"

    _write_executed(executed, count=2)
    _write_labels(labels, count=2)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_blind_evaluation.py",
            "--executed-receipts",
            str(executed),
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
    assert BLIND_EVALUATION_READY_TOKEN in completed.stdout
    assert (output / "blind_evaluation_receipt.json").exists()
    assert (output / "blind_scores.jsonl").exists()
    assert (output / "blind_label_join.json").exists()
