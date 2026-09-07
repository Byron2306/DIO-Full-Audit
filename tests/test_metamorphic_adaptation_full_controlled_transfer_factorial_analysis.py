import json
import subprocess
import sys

from experiments.metamorphic_adaptation.full_controlled_transfer_factorial_analysis import (
    FULL_TRANSFER_FACTORIAL_READY_TOKEN,
    FULL_TRANSFER_FACTORIAL_REFUSED_TOKEN,
    FULL_TRANSFER_FACTORIAL_VERSION,
    analyze_full_controlled_transfer_scores,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_blind_receipt(path, *, ready=True, count=25):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_REFUSED"
        ),
        "evaluated_blind_outputs": count,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_scores_and_labels(scores_path, labels_path, *, count=25):
    labels = {}
    with scores_path.open("w") as fh:
        ordinal = 1
        for arm in ARMS:
            for encounter_index in range(1, 6):
                if ordinal > count:
                    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))
                    return
                blind_id = f"FULL-TRANSFER-BLIND-{ordinal:04d}"
                fh.write(json.dumps({
                    "blind_id": blind_id,
                    "status": "FULL_CONTROLLED_TRANSFER_BLIND_SCORE_RECORDED",
                    "real_native_mode": True,
                    "score": 1.0,
                    "stdout_sha256": "a" * 64,
                    "stderr_sha256": "b" * 64,
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")
                labels[blind_id] = {
                    "arm": arm,
                    "encounter_index": encounter_index,
                }
                ordinal += 1
    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))


def test_full_transfer_factorial_analysis_groups_scores_by_arm(tmp_path):
    blind_receipt = tmp_path / "full_controlled_transfer_blind_evaluation_receipt.json"
    scores = tmp_path / "full_controlled_transfer_blind_scores.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_label_join.json"
    output = tmp_path / "analysis"

    _write_blind_receipt(blind_receipt)
    _write_scores_and_labels(scores, labels)

    receipt = analyze_full_controlled_transfer_scores(
        blind_evaluation_receipt_path=blind_receipt,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.analysis_version == FULL_TRANSFER_FACTORIAL_VERSION
    assert receipt.status == FULL_TRANSFER_FACTORIAL_READY_TOKEN
    assert receipt.scores_loaded == 25
    assert receipt.labels_loaded == 25
    assert receipt.arms_analyzed == 5
    assert receipt.baseline_arm == "A_STATELESS_RESET"
    assert receipt.baseline_arm_mean == 1.0
    assert receipt.full_minus_baseline_effect == 0.0
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False

    arm_means = json.loads((output / "full_controlled_transfer_arm_means.json").read_text())
    assert len(arm_means) == 5
    assert arm_means["E_FULL_SEMANTIC_MARKET_BEAST"]["n"] == 5


def test_full_transfer_factorial_analysis_refuses_unready_blind_evaluation(tmp_path):
    blind_receipt = tmp_path / "full_controlled_transfer_blind_evaluation_receipt.json"
    scores = tmp_path / "full_controlled_transfer_blind_scores.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_label_join.json"
    output = tmp_path / "analysis"

    _write_blind_receipt(blind_receipt, ready=False)
    _write_scores_and_labels(scores, labels)

    receipt = analyze_full_controlled_transfer_scores(
        blind_evaluation_receipt_path=blind_receipt,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.status == FULL_TRANSFER_FACTORIAL_REFUSED_TOKEN
    assert receipt.arms_analyzed == 0
    assert receipt.real_adaptive_evidence is False


def test_full_transfer_factorial_analysis_refuses_incomplete_scores(tmp_path):
    blind_receipt = tmp_path / "full_controlled_transfer_blind_evaluation_receipt.json"
    scores = tmp_path / "full_controlled_transfer_blind_scores.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_label_join.json"
    output = tmp_path / "analysis"

    _write_blind_receipt(blind_receipt, count=24)
    _write_scores_and_labels(scores, labels, count=24)

    receipt = analyze_full_controlled_transfer_scores(
        blind_evaluation_receipt_path=blind_receipt,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.status == FULL_TRANSFER_FACTORIAL_REFUSED_TOKEN
    assert receipt.scores_loaded == 24
    assert receipt.labels_loaded == 24


def test_full_transfer_factorial_analysis_writes_factor_effects(tmp_path):
    blind_receipt = tmp_path / "full_controlled_transfer_blind_evaluation_receipt.json"
    scores = tmp_path / "full_controlled_transfer_blind_scores.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_label_join.json"
    output = tmp_path / "analysis"

    _write_blind_receipt(blind_receipt)
    _write_scores_and_labels(scores, labels)

    receipt = analyze_full_controlled_transfer_scores(
        blind_evaluation_receipt_path=blind_receipt,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    effects = json.loads((output / "full_controlled_transfer_factor_effects.json").read_text())

    assert effects["baseline_arm"] == "A_STATELESS_RESET"
    assert effects["full_arm"] == "E_FULL_SEMANTIC_MARKET_BEAST"
    assert effects["full_minus_baseline_effect"] == receipt.full_minus_baseline_effect
    assert effects["real_adaptive_evidence"] is False


def test_full_transfer_factorial_analysis_boundary_blocks_overclaiming(tmp_path):
    blind_receipt = tmp_path / "full_controlled_transfer_blind_evaluation_receipt.json"
    scores = tmp_path / "full_controlled_transfer_blind_scores.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_label_join.json"
    output = tmp_path / "analysis"

    _write_blind_receipt(blind_receipt)
    _write_scores_and_labels(scores, labels)

    receipt = analyze_full_controlled_transfer_scores(
        blind_evaluation_receipt_path=blind_receipt,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    boundary = receipt.boundary.lower()

    assert "groups 25 blind smoke scores by arm" in boundary
    assert "compatibility-score structure only" in boundary
    assert "does not constitute adaptive performance evidence" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_full_transfer_factorial_analysis_cli_runner(tmp_path):
    blind_receipt = tmp_path / "full_controlled_transfer_blind_evaluation_receipt.json"
    scores = tmp_path / "full_controlled_transfer_blind_scores.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_label_join.json"
    output = tmp_path / "analysis"

    _write_blind_receipt(blind_receipt)
    _write_scores_and_labels(scores, labels)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_full_controlled_transfer_factorial_analysis.py",
            "--blind-evaluation-receipt",
            str(blind_receipt),
            "--blind-scores",
            str(scores),
            "--label-join",
            str(labels),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert FULL_TRANSFER_FACTORIAL_READY_TOKEN in completed.stdout
    assert (output / "full_controlled_transfer_factorial_analysis_receipt.json").exists()
    assert (output / "full_controlled_transfer_arm_means.json").exists()
    assert (output / "full_controlled_transfer_factor_effects.json").exists()
