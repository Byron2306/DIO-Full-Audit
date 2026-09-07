import json
import subprocess
import sys

from experiments.metamorphic_adaptation.real_task_quality_arm_analysis import (
    REAL_TASK_QUALITY_ARM_ANALYSIS_READY_TOKEN,
    REAL_TASK_QUALITY_ARM_ANALYSIS_REFUSED_TOKEN,
    REAL_TASK_QUALITY_ARM_ANALYSIS_VERSION,
    analyze_real_task_quality_by_arm,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]
TASKS = ["RTQ-001", "RTQ-002", "RTQ-003", "RTQ-004", "RTQ-005"]


def _write_receipt(path, *, ready=True, count=25):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_REFUSED"
        ),
        "rubric_scores_written": count,
        "real_task_quality_evaluation_authorized": ready,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_scores_and_labels(scores_path, labels_path, *, count=25):
    labels = {}
    with scores_path.open("w") as fh:
        ordinal = 1
        for arm in ARMS:
            for encounter_index, task_id in enumerate(TASKS, start=1):
                if ordinal > count:
                    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))
                    return
                blind_id = f"FULL-TRANSFER-BLIND-{ordinal:04d}"
                fh.write(json.dumps({
                    "blind_id": blind_id,
                    "status": "REAL_TASK_QUALITY_RUBRIC_SCORE_RECORDED",
                    "task_id": task_id,
                    "total_score": 0.0,
                    "criteria_scores": {},
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")
                labels[blind_id] = {
                    "arm": arm,
                    "encounter_index": encounter_index,
                    "task_id": task_id,
                    "task_family": "test_family",
                }
                ordinal += 1
    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))


def test_real_task_quality_arm_analysis_rejoins_after_scoring(tmp_path):
    receipt_path = tmp_path / "real_task_quality_rubric_evaluation_receipt.json"
    scores_path = tmp_path / "real_task_quality_rubric_scores.jsonl"
    labels_path = tmp_path / "real_task_quality_label_join.json"
    output = tmp_path / "analysis"

    _write_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)

    receipt = analyze_real_task_quality_by_arm(
        rubric_evaluation_receipt_path=receipt_path,
        rubric_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output,
    )

    assert receipt.analysis_version == REAL_TASK_QUALITY_ARM_ANALYSIS_VERSION
    assert receipt.status == REAL_TASK_QUALITY_ARM_ANALYSIS_READY_TOKEN
    assert receipt.scores_loaded == 25
    assert receipt.labels_loaded == 25
    assert receipt.arms_analyzed == 5
    assert receipt.tasks_analyzed == 5
    assert receipt.baseline_arm == "A_STATELESS_RESET"
    assert receipt.full_arm == "E_FULL_SEMANTIC_MARKET_BEAST"
    assert receipt.full_minus_baseline_effect == 0.0
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False

    arm_means = json.loads((output / "real_task_quality_arm_means.json").read_text())
    task_means = json.loads((output / "real_task_quality_task_means.json").read_text())
    assert len(arm_means) == 5
    assert len(task_means) == 5
    assert arm_means["E_FULL_SEMANTIC_MARKET_BEAST"]["n"] == 5


def test_real_task_quality_arm_analysis_refuses_unready_evaluation(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output = tmp_path / "analysis"

    _write_receipt(receipt_path, ready=False)
    _write_scores_and_labels(scores_path, labels_path)

    receipt = analyze_real_task_quality_by_arm(
        rubric_evaluation_receipt_path=receipt_path,
        rubric_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output,
    )

    assert receipt.status == REAL_TASK_QUALITY_ARM_ANALYSIS_REFUSED_TOKEN
    assert receipt.real_task_quality_analysis_authorized is False
    assert receipt.arms_analyzed == 0


def test_real_task_quality_arm_analysis_refuses_incomplete_records(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output = tmp_path / "analysis"

    _write_receipt(receipt_path, count=24)
    _write_scores_and_labels(scores_path, labels_path, count=24)

    receipt = analyze_real_task_quality_by_arm(
        rubric_evaluation_receipt_path=receipt_path,
        rubric_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output,
    )

    assert receipt.status == REAL_TASK_QUALITY_ARM_ANALYSIS_REFUSED_TOKEN
    assert receipt.scores_loaded == 24
    assert receipt.labels_loaded == 24


def test_real_task_quality_arm_analysis_writes_factor_effects(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output = tmp_path / "analysis"

    _write_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)

    receipt = analyze_real_task_quality_by_arm(
        rubric_evaluation_receipt_path=receipt_path,
        rubric_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output,
    )

    effects = json.loads((output / "real_task_quality_factor_effects.json").read_text())
    assert effects["baseline_arm"] == receipt.baseline_arm
    assert effects["full_arm"] == receipt.full_arm
    assert effects["full_minus_baseline_effect"] == 0.0
    assert effects["real_adaptive_evidence"] is False


def test_real_task_quality_arm_analysis_boundary_blocks_overclaiming(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output = tmp_path / "analysis"

    _write_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)

    receipt = analyze_real_task_quality_by_arm(
        rubric_evaluation_receipt_path=receipt_path,
        rubric_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output,
    )

    boundary = receipt.boundary.lower()
    assert "rejoins labels only after blinded rubric scoring" in boundary
    assert "descriptive analysis only" in boundary
    assert "does not constitute adaptive performance evidence" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_real_task_quality_arm_analysis_cli_runner(tmp_path):
    receipt_path = tmp_path / "receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output = tmp_path / "analysis"

    _write_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_arm_analysis.py",
            "--rubric-evaluation-receipt",
            str(receipt_path),
            "--rubric-scores",
            str(scores_path),
            "--label-join",
            str(labels_path),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_TASK_QUALITY_ARM_ANALYSIS_READY_TOKEN in completed.stdout
    assert (output / "real_task_quality_arm_analysis_receipt.json").exists()
    assert (output / "real_task_quality_arm_means.json").exists()
    assert (output / "real_task_quality_task_means.json").exists()
    assert (output / "real_task_quality_factor_effects.json").exists()
