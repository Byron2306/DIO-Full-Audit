import json
import subprocess
import sys

from experiments.metamorphic_adaptation.ecosystem_integrated_arm_analysis import (
    BASELINE_ARM,
    ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY_TOKEN,
    ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_REFUSED_TOKEN,
    ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_VERSION,
    FULL_ARM,
    analyze_ecosystem_integrated_arms,
)


def _write_rubric_receipt(path, *, ready=True, written=25):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATION_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATION_REFUSED"
        ),
        "ecosystem_arm_analysis_authorized": ready,
        "adaptive_claim_authorized": False,
        "ecosystem_scores_written": written,
    }, indent=2, sort_keys=True))


def _arms():
    return (
        "A_DIO_CORE_ONLY",
        "B_DIO_CORE_LINGUA",
        "C_DIO_BEAST_CONTEXT",
        "D_DIO_DOMAIN_ORGANS",
        "E_FULL_ECOSYSTEM_ORCHESTRATION",
    )


def _write_scores_and_labels(scores_path, labels_path, *, count=25, full_score=0.92, baseline_score=0.60):
    labels = {}
    with scores_path.open("w") as fh:
        ordinal = 1
        for arm in _arms():
            for task_index in range(1, 6):
                blind_id = f"ECO-BLIND-{ordinal:04d}"
                score = full_score if arm == FULL_ARM else baseline_score if arm == BASELINE_ARM else 0.72
                gap_count = 0 if arm == FULL_ARM else 1
                fh.write(json.dumps({
                    "blind_id": blind_id,
                    "task_id": f"ECO-{task_index:03d}",
                    "task_family": "family",
                    "status": "ECOSYSTEM_INTEGRATED_RUBRIC_SCORE_RECORDED",
                    "ecosystem_quality_score": score,
                    "organ_coverage_score": 1.0 if arm == FULL_ARM else 0.5,
                    "organ_gap_count": gap_count,
                    "criterion_scores": {"organ_fit": score},
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")
                labels[blind_id] = {
                    "arm_id": arm,
                    "task_id": f"ECO-{task_index:03d}",
                    "task_family": "family",
                    "enabled_organs": [],
                    "required_organs": [],
                    "missing_organs": [] if arm == FULL_ARM else ["BEAST"],
                }
                ordinal += 1
                if ordinal > count:
                    break
            if ordinal > count:
                break
    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))


def test_ecosystem_arm_analysis_rejoins_labels_after_scoring(tmp_path):
    receipt_path = tmp_path / "rubric_receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output_dir = tmp_path / "analysis"

    _write_rubric_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)

    receipt = analyze_ecosystem_integrated_arms(
        rubric_evaluation_receipt_path=receipt_path,
        ecosystem_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output_dir,
    )

    assert receipt.analysis_version == ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_VERSION
    assert receipt.status == ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY_TOKEN
    assert receipt.scores_loaded == 25
    assert receipt.labels_loaded == 25
    assert receipt.arms_analyzed == 5
    assert receipt.tasks_analyzed == 5
    assert receipt.baseline_arm == BASELINE_ARM
    assert receipt.full_arm == FULL_ARM
    assert receipt.full_minus_baseline_effect == 0.32
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False


def test_ecosystem_arm_analysis_writes_outputs(tmp_path):
    receipt_path = tmp_path / "rubric_receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output_dir = tmp_path / "analysis"

    _write_rubric_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)

    receipt = analyze_ecosystem_integrated_arms(
        rubric_evaluation_receipt_path=receipt_path,
        ecosystem_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output_dir,
    )

    arm_means = json.loads((output_dir / "ecosystem_integrated_arm_means.json").read_text())
    effects = json.loads((output_dir / "ecosystem_integrated_factor_effects.json").read_text())
    saved = json.loads((output_dir / "ecosystem_integrated_arm_analysis_receipt.json").read_text())

    assert arm_means[FULL_ARM]["mean_ecosystem_quality_score"] == 0.92
    assert effects["full_minus_baseline_effect"] == 0.32
    assert saved["status"] == receipt.status
    assert len(saved["ecosystem_scores_sha256"]) == 64
    assert len(saved["label_join_sha256"]) == 64


def test_ecosystem_arm_analysis_refuses_unready_receipt(tmp_path):
    receipt_path = tmp_path / "rubric_receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output_dir = tmp_path / "analysis"

    _write_rubric_receipt(receipt_path, ready=False, written=0)
    _write_scores_and_labels(scores_path, labels_path)

    receipt = analyze_ecosystem_integrated_arms(
        rubric_evaluation_receipt_path=receipt_path,
        ecosystem_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output_dir,
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_REFUSED_TOKEN
    assert receipt.ecosystem_arm_analysis_authorized is False
    assert receipt.arms_analyzed == 0
    assert receipt.adaptive_claim_authorized is False


def test_ecosystem_arm_analysis_refuses_missing_label(tmp_path):
    receipt_path = tmp_path / "rubric_receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output_dir = tmp_path / "analysis"

    _write_rubric_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)
    labels = json.loads(labels_path.read_text())
    labels.pop("ECO-BLIND-0001")
    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))

    receipt = analyze_ecosystem_integrated_arms(
        rubric_evaluation_receipt_path=receipt_path,
        ecosystem_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output_dir,
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_REFUSED_TOKEN
    assert receipt.labels_loaded == 24
    assert receipt.adaptive_claim_authorized is False


def test_ecosystem_arm_analysis_boundary_blocks_overclaiming(tmp_path):
    receipt_path = tmp_path / "rubric_receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output_dir = tmp_path / "analysis"

    _write_rubric_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)

    receipt = analyze_ecosystem_integrated_arms(
        rubric_evaluation_receipt_path=receipt_path,
        ecosystem_scores_path=scores_path,
        label_join_path=labels_path,
        output_dir=output_dir,
    )

    boundary = receipt.boundary.lower()
    assert "rejoins ecosystem arm labels only after blinded rubric scoring" in boundary
    assert "descriptive analysis only" in boundary
    assert "does not constitute adaptive" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_ecosystem_arm_analysis_cli_runner(tmp_path):
    receipt_path = tmp_path / "rubric_receipt.json"
    scores_path = tmp_path / "scores.jsonl"
    labels_path = tmp_path / "labels.json"
    output_dir = tmp_path / "analysis"

    _write_rubric_receipt(receipt_path)
    _write_scores_and_labels(scores_path, labels_path)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_ecosystem_integrated_arm_analysis.py",
            "--rubric-evaluation-receipt",
            str(receipt_path),
            "--ecosystem-scores",
            str(scores_path),
            "--label-join",
            str(labels_path),
            "--output",
            str(output_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY_TOKEN in completed.stdout
    assert (output_dir / "ecosystem_integrated_arm_analysis_receipt.json").exists()
    assert (output_dir / "ecosystem_integrated_arm_means.json").exists()
    assert (output_dir / "ecosystem_integrated_task_means.json").exists()
    assert (output_dir / "ecosystem_integrated_factor_effects.json").exists()
