import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_task_quality_factorial_analysis import (
    REAL_TASK_QUALITY_FACTORIAL_READY_TOKEN,
    REAL_TASK_QUALITY_FACTORIAL_REFUSED_TOKEN,
    REAL_TASK_QUALITY_FACTORIAL_VERSION,
    analyze_real_task_quality_scores,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_scoring_receipt(path, *, ready=True, outputs=25, mean_score=1.0):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BLIND_RUBRIC_SCORING_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BLIND_RUBRIC_SCORING_REFUSED"
        ),
        "real_quality_scores_available": ready,
        "outputs_scored": outputs if ready else 0,
        "mean_score": mean_score,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_scores_and_labels(scores_path, labels_path, *, score_by_arm=None, count=25):
    score_by_arm = score_by_arm or {arm: 1.0 for arm in ARMS}
    labels = {}
    with scores_path.open("w") as fh:
        ordinal = 1
        for arm in ARMS:
            for encounter_index in range(1, 6):
                if ordinal > count:
                    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))
                    return
                blind_id = f"FULL-TRANSFER-BLIND-{ordinal:04d}"
                score = float(score_by_arm.get(arm, 1.0))
                fh.write(json.dumps({
                    "blind_id": blind_id,
                    "task_id": f"RTQ-{((ordinal - 1) % 5) + 1:03d}",
                    "task_family": "portfolio_truth",
                    "status": "REAL_TASK_QUALITY_BLIND_SCORE_RECORDED",
                    "score": score,
                    "rubric_scores": {
                        "claim_boundary": score,
                        "evidence_traceability": score,
                    },
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")
                labels[blind_id] = {
                    "arm": arm,
                    "encounter_index": encounter_index,
                    "task_id": f"RTQ-{((ordinal - 1) % 5) + 1:03d}",
                    "task_family": "portfolio_truth",
                }
                ordinal += 1
    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))


def test_real_task_quality_factorial_analysis_rejoins_labels_and_groups_arms(tmp_path):
    scoring = tmp_path / "real_task_quality_blind_rubric_scoring_receipt.json"
    scores = tmp_path / "real_task_quality_blind_scores.jsonl"
    labels = tmp_path / "real_task_quality_label_join.json"
    output = tmp_path / "analysis"

    _write_scoring_receipt(scoring)
    _write_scores_and_labels(scores, labels)

    receipt = analyze_real_task_quality_scores(
        scoring_receipt_path=scoring,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.analysis_version == REAL_TASK_QUALITY_FACTORIAL_VERSION
    assert receipt.status == REAL_TASK_QUALITY_FACTORIAL_READY_TOKEN
    assert receipt.real_quality_scores_analyzed is True
    assert receipt.scores_loaded == 25
    assert receipt.labels_loaded == 25
    assert receipt.arms_analyzed == 5
    assert receipt.baseline_arm == "A_STATELESS_RESET"
    assert receipt.baseline_mean_score == 1.0
    assert receipt.full_arm == "E_FULL_SEMANTIC_MARKET_BEAST"
    assert receipt.full_mean_score == 1.0
    assert receipt.full_minus_baseline_effect == 0.0
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False

    arm_means = json.loads((output / "real_task_quality_arm_means.json").read_text())
    assert arm_means["A_STATELESS_RESET"]["n"] == 5
    assert arm_means["E_FULL_SEMANTIC_MARKET_BEAST"]["mean_score"] == 1.0


def test_real_task_quality_factorial_analysis_detects_positive_effect_without_authorizing_claim(tmp_path):
    scoring = tmp_path / "real_task_quality_blind_rubric_scoring_receipt.json"
    scores = tmp_path / "real_task_quality_blind_scores.jsonl"
    labels = tmp_path / "real_task_quality_label_join.json"
    output = tmp_path / "analysis"

    _write_scoring_receipt(scoring)
    _write_scores_and_labels(scores, labels, score_by_arm={
        "A_STATELESS_RESET": 0.60,
        "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING": 0.65,
        "C_SEMANTIC_RETAINED": 0.70,
        "D_MARKET_RETAINED": 0.72,
        "E_FULL_SEMANTIC_MARKET_BEAST": 0.90,
    })

    receipt = analyze_real_task_quality_scores(
        scoring_receipt_path=scoring,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.status == REAL_TASK_QUALITY_FACTORIAL_READY_TOKEN
    assert round(receipt.full_minus_baseline_effect, 2) == 0.30
    assert receipt.positive_full_stack_quality_effect_observed is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False
    assert "claim-gate review" in receipt.boundary


def test_real_task_quality_factorial_analysis_refuses_unready_scoring(tmp_path):
    scoring = tmp_path / "real_task_quality_blind_rubric_scoring_receipt.json"
    scores = tmp_path / "real_task_quality_blind_scores.jsonl"
    labels = tmp_path / "real_task_quality_label_join.json"
    output = tmp_path / "analysis"

    _write_scoring_receipt(scoring, ready=False)
    _write_scores_and_labels(scores, labels)

    receipt = analyze_real_task_quality_scores(
        scoring_receipt_path=scoring,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.status == REAL_TASK_QUALITY_FACTORIAL_REFUSED_TOKEN
    assert receipt.real_quality_scores_analyzed is False
    assert receipt.arms_analyzed == 0


def test_real_task_quality_factorial_analysis_refuses_incomplete_scores(tmp_path):
    scoring = tmp_path / "real_task_quality_blind_rubric_scoring_receipt.json"
    scores = tmp_path / "real_task_quality_blind_scores.jsonl"
    labels = tmp_path / "real_task_quality_label_join.json"
    output = tmp_path / "analysis"

    _write_scoring_receipt(scoring, outputs=24)
    _write_scores_and_labels(scores, labels, count=24)

    receipt = analyze_real_task_quality_scores(
        scoring_receipt_path=scoring,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.status == REAL_TASK_QUALITY_FACTORIAL_REFUSED_TOKEN
    assert receipt.scores_loaded == 24
    assert receipt.labels_loaded == 24


def test_real_task_quality_factorial_analysis_writes_receipt_and_effects(tmp_path):
    scoring = tmp_path / "real_task_quality_blind_rubric_scoring_receipt.json"
    scores = tmp_path / "real_task_quality_blind_scores.jsonl"
    labels = tmp_path / "real_task_quality_label_join.json"
    output = tmp_path / "analysis"

    _write_scoring_receipt(scoring)
    _write_scores_and_labels(scores, labels)

    receipt = analyze_real_task_quality_scores(
        scoring_receipt_path=scoring,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    data = json.loads((output / "real_task_quality_factorial_analysis_receipt.json").read_text())
    effects = json.loads((output / "real_task_quality_factor_effects.json").read_text())

    assert data == json.loads(json.dumps(asdict(receipt)))
    assert effects["full_minus_baseline_effect"] == receipt.full_minus_baseline_effect
    assert len(data["scoring_receipt_sha256"]) == 64
    assert len(data["blind_scores_sha256"]) == 64
    assert len(data["label_join_sha256"]) == 64


def test_real_task_quality_factorial_analysis_boundary_blocks_overclaiming(tmp_path):
    scoring = tmp_path / "real_task_quality_blind_rubric_scoring_receipt.json"
    scores = tmp_path / "real_task_quality_blind_scores.jsonl"
    labels = tmp_path / "real_task_quality_label_join.json"
    output = tmp_path / "analysis"

    _write_scoring_receipt(scoring)
    _write_scores_and_labels(scores, labels)

    receipt = analyze_real_task_quality_scores(
        scoring_receipt_path=scoring,
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    boundary = receipt.boundary.lower()
    assert "rejoins labels after blind scoring" in boundary
    assert "does not by itself authorize" in boundary
    assert "adaptive-performance claim" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_real_task_quality_factorial_analysis_cli_runner(tmp_path):
    scoring = tmp_path / "real_task_quality_blind_rubric_scoring_receipt.json"
    scores = tmp_path / "real_task_quality_blind_scores.jsonl"
    labels = tmp_path / "real_task_quality_label_join.json"
    output = tmp_path / "analysis"

    _write_scoring_receipt(scoring)
    _write_scores_and_labels(scores, labels)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_factorial_analysis.py",
            "--scoring-receipt",
            str(scoring),
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
    assert REAL_TASK_QUALITY_FACTORIAL_READY_TOKEN in completed.stdout
    assert (output / "real_task_quality_factorial_analysis_receipt.json").exists()
