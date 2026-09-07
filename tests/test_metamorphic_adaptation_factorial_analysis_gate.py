import json
import subprocess
import sys

from experiments.metamorphic_adaptation.factorial_analysis_gate import (
    FACTORIAL_ANALYSIS_READY_TOKEN,
    FACTORIAL_ANALYSIS_REFUSED_TOKEN,
    FACTORIAL_ANALYSIS_VERSION,
    run_factorial_fixture_analysis,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_blind_eval_bundle(scores_path, labels_path, encounter_count=5):
    labels = {}
    ordinal = 1

    with scores_path.open("w") as fh:
        for arm in ARMS:
            for encounter_index in range(1, encounter_count + 1):
                blind_id = f"BLIND-{ordinal:04d}"
                score = {
                    "A_STATELESS_RESET": 0.10,
                    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING": 0.20,
                    "C_SEMANTIC_RETAINED": 0.30,
                    "D_MARKET_RETAINED": 0.30,
                    "E_FULL_SEMANTIC_MARKET_BEAST": 0.40,
                }[arm] + encounter_index * 0.01

                fh.write(json.dumps({
                    "blind_id": blind_id,
                    "status": "BLIND_SCORE_RECORDED",
                    "fixture_mode": True,
                    "output_sha256": "a" * 64,
                    "score": round(score, 4),
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")

                labels[blind_id] = {
                    "arm": arm,
                    "encounter_index": encounter_index,
                }
                ordinal += 1

    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))


def test_factorial_analysis_summarizes_blind_scores_after_label_rejoin(tmp_path):
    scores = tmp_path / "blind_scores.jsonl"
    labels = tmp_path / "blind_label_join.json"
    output = tmp_path / "factorial"

    _write_blind_eval_bundle(scores, labels)

    receipt = run_factorial_fixture_analysis(
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.analysis_version == FACTORIAL_ANALYSIS_VERSION
    assert receipt.status == FACTORIAL_ANALYSIS_READY_TOKEN
    assert receipt.fixture_mode is True
    assert receipt.blind_scores_loaded == 25
    assert receipt.arms_analyzed == 5
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False

    arm_means = json.loads((output / "arm_means.json").read_text())

    assert arm_means["A_STATELESS_RESET"]["mean_score"] == 0.13
    assert arm_means["E_FULL_SEMANTIC_MARKET_BEAST"]["mean_score"] == 0.43


def test_factorial_analysis_emits_fixture_effects_without_claim(tmp_path):
    scores = tmp_path / "blind_scores.jsonl"
    labels = tmp_path / "blind_label_join.json"
    output = tmp_path / "factorial"

    _write_blind_eval_bundle(scores, labels)

    run_factorial_fixture_analysis(
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    effects = json.loads((output / "factor_effects.json").read_text())

    assert effects["semantic_retained_fixture_effect"] == 0.1
    assert effects["market_retained_fixture_effect"] == 0.1
    assert effects["full_stack_fixture_effect"] == 0.3
    assert effects["fixture_mode"] is True
    assert effects["real_adaptive_evidence"] is False
    assert effects["adaptive_claim_authorized"] is False


def test_factorial_analysis_refuses_empty_scores(tmp_path):
    scores = tmp_path / "blind_scores.jsonl"
    labels = tmp_path / "blind_label_join.json"
    output = tmp_path / "factorial"

    scores.write_text("")
    labels.write_text("{}")

    receipt = run_factorial_fixture_analysis(
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    assert receipt.status == FACTORIAL_ANALYSIS_REFUSED_TOKEN
    assert receipt.blind_scores_loaded == 0
    assert receipt.arms_analyzed == 0
    assert receipt.adaptive_claim_authorized is False


def test_factorial_analysis_writes_top_level_receipt(tmp_path):
    scores = tmp_path / "blind_scores.jsonl"
    labels = tmp_path / "blind_label_join.json"
    output = tmp_path / "factorial"

    _write_blind_eval_bundle(scores, labels, encounter_count=2)

    receipt = run_factorial_fixture_analysis(
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    data = json.loads((output / "factorial_analysis_receipt.json").read_text())

    assert data["status"] == receipt.status
    assert data["blind_scores_loaded"] == 10
    assert data["arms_analyzed"] == 5
    assert data["real_adaptive_evidence"] is False


def test_factorial_analysis_boundary_blocks_overclaiming(tmp_path):
    scores = tmp_path / "blind_scores.jsonl"
    labels = tmp_path / "blind_label_join.json"
    output = tmp_path / "factorial"

    _write_blind_eval_bundle(scores, labels, encounter_count=1)

    receipt = run_factorial_fixture_analysis(
        blind_scores_path=scores,
        label_join_path=labels,
        output_dir=output,
    )

    boundary = receipt.boundary.lower()

    assert "fixture-mode blind scores" in boundary
    assert "proves analysis mechanics only" in boundary
    assert "does not constitute real adaptive performance evidence" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_factorial_analysis_cli_runner(tmp_path):
    scores = tmp_path / "blind_scores.jsonl"
    labels = tmp_path / "blind_label_join.json"
    output = tmp_path / "factorial"

    _write_blind_eval_bundle(scores, labels, encounter_count=2)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_factorial_analysis.py",
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
    assert FACTORIAL_ANALYSIS_READY_TOKEN in completed.stdout
    assert (output / "factorial_analysis_receipt.json").exists()
    assert (output / "arm_means.json").exists()
    assert (output / "factor_effects.json").exists()
