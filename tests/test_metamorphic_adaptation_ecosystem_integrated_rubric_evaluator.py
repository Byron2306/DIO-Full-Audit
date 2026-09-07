import json
import subprocess
import sys

from experiments.metamorphic_adaptation.ecosystem_integrated_rubric_evaluator import (
    ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_READY_TOKEN,
    ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_REFUSED_TOKEN,
    ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_VERSION,
    evaluate_ecosystem_integrated_outputs,
)


def _write_execution_receipt(path, *, ready=True, produced=25):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_EXECUTION_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_EXECUTION_REFUSED"
        ),
        "executed": ready,
        "ecosystem_outputs_produced": produced,
        "ecosystem_quality_scoring_authorized": ready,
        "adaptive_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_outputs(path, *, count=25, full=False):
    required = ["DIO_CORE", "BEAST", "LINGUA"]
    with path.open("w") as fh:
        for index in range(1, count + 1):
            if full or index % 2 == 0:
                used = required
                missing = []
                coverage = 1.0
                answer = (
                    "The available organs cover the full required set with coverage score 1.0. "
                    "Governed response: route the work, bind evidence, preserve ALLOW/REFUSE/NEEDS_YOU, "
                    "and address success criteria: root cause identified; files scoped; tests named; "
                    "no unverified fix claim. This is not proof of adaptive superiority."
                )
            else:
                used = ["DIO_CORE"]
                missing = ["BEAST", "LINGUA"]
                coverage = 0.333333
                answer = (
                    "Missing organs: BEAST, LINGUA. Governed decision: provide a partial bounded analysis only, "
                    "mark the missing organ evidence, preserve NEEDS_YOU, and refuse any claim that the complete "
                    "ecosystem task was solved. Success criteria considered: root cause identified; files scoped; "
                    "tests named; no unverified fix claim. No adaptive, commercial, professional, publication, spend, "
                    "fulfilment, world-first, or authority-expansion claim is authorized."
                )
            fh.write(json.dumps({
                "blind_id": f"ECO-BLIND-{index:04d}",
                "task_id": "ECO-001",
                "task_family": "repo_failure_governance",
                "status": "ECOSYSTEM_INTEGRATED_OUTPUT_PRODUCED",
                "required_organs": required,
                "used_organs": used,
                "missing_required_organs": missing,
                "organ_gap_count": len(missing),
                "organ_coverage_score": coverage,
                "success_criteria": [
                    "root cause identified",
                    "files scoped",
                    "tests named",
                    "no unverified fix claim",
                ],
                "answer": answer,
                "answer_sha256": "a" * 64,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
                "professional_approval_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
                "authority_expansion_authorized": False,
            }, sort_keys=True) + "\n")


def test_evaluator_scores_25_blinded_ecosystem_outputs(tmp_path):
    execution = tmp_path / "execution.json"
    outputs = tmp_path / "outputs.jsonl"
    output_dir = tmp_path / "scores"

    _write_execution_receipt(execution)
    _write_outputs(outputs)

    receipt = evaluate_ecosystem_integrated_outputs(
        execution_receipt_path=execution,
        ecosystem_outputs_path=outputs,
        output_dir=output_dir,
    )

    assert receipt.evaluator_version == ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_VERSION
    assert receipt.status == ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_READY_TOKEN
    assert receipt.outputs_loaded == 25
    assert receipt.ecosystem_scores_written == 25
    assert 0 < receipt.mean_ecosystem_quality_score <= 1
    assert receipt.organ_gap_outputs == 13
    assert receipt.full_coverage_outputs == 12
    assert receipt.ecosystem_arm_analysis_authorized is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False

    first = json.loads((output_dir / "ecosystem_integrated_rubric_scores.jsonl").read_text().splitlines()[0])
    assert first["blind_id"] == "ECO-BLIND-0001"
    assert "arm_id" not in first
    assert first["ecosystem_quality_score"] > 0
    assert first["criterion_scores"]["organ_fit"] == 0.333333


def test_evaluator_rewards_full_organ_coverage_more_than_partial_gap(tmp_path):
    execution = tmp_path / "execution.json"
    partial = tmp_path / "partial.jsonl"
    full = tmp_path / "full.jsonl"

    _write_execution_receipt(execution)
    _write_outputs(partial)
    _write_outputs(full, full=True)

    partial_receipt = evaluate_ecosystem_integrated_outputs(
        execution_receipt_path=execution,
        ecosystem_outputs_path=partial,
        output_dir=tmp_path / "partial_scores",
    )
    full_receipt = evaluate_ecosystem_integrated_outputs(
        execution_receipt_path=execution,
        ecosystem_outputs_path=full,
        output_dir=tmp_path / "full_scores",
    )

    assert full_receipt.mean_ecosystem_quality_score > partial_receipt.mean_ecosystem_quality_score
    assert full_receipt.mean_organ_coverage_score == 1.0
    assert full_receipt.organ_gap_outputs == 0


def test_evaluator_refuses_unready_execution(tmp_path):
    execution = tmp_path / "execution.json"
    outputs = tmp_path / "outputs.jsonl"

    _write_execution_receipt(execution, ready=False, produced=0)
    _write_outputs(outputs)

    receipt = evaluate_ecosystem_integrated_outputs(
        execution_receipt_path=execution,
        ecosystem_outputs_path=outputs,
        output_dir=tmp_path / "scores",
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_REFUSED_TOKEN
    assert receipt.ecosystem_scores_written == 0
    assert receipt.ecosystem_arm_analysis_authorized is False
    assert receipt.adaptive_claim_authorized is False


def test_evaluator_refuses_wrong_output_count(tmp_path):
    execution = tmp_path / "execution.json"
    outputs = tmp_path / "outputs.jsonl"

    _write_execution_receipt(execution, produced=24)
    _write_outputs(outputs, count=24)

    receipt = evaluate_ecosystem_integrated_outputs(
        execution_receipt_path=execution,
        ecosystem_outputs_path=outputs,
        output_dir=tmp_path / "scores",
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_REFUSED_TOKEN
    assert receipt.outputs_loaded == 24
    assert receipt.real_adaptive_evidence is False


def test_evaluator_writes_summary_and_hashes_sources(tmp_path):
    execution = tmp_path / "execution.json"
    outputs = tmp_path / "outputs.jsonl"
    output_dir = tmp_path / "scores"

    _write_execution_receipt(execution)
    _write_outputs(outputs)

    receipt = evaluate_ecosystem_integrated_outputs(
        execution_receipt_path=execution,
        ecosystem_outputs_path=outputs,
        output_dir=output_dir,
    )

    saved = json.loads((output_dir / "ecosystem_integrated_rubric_evaluation_receipt.json").read_text())
    summary = json.loads((output_dir / "ecosystem_integrated_score_summary.json").read_text())

    assert saved["status"] == receipt.status
    assert summary["outputs_scored"] == 25
    assert summary["ecosystem_arm_analysis_authorized"] is True
    assert summary["real_adaptive_evidence"] is False
    assert len(saved["execution_receipt_sha256"]) == 64
    assert len(saved["ecosystem_outputs_sha256"]) == 64


def test_evaluator_boundary_blocks_overclaiming(tmp_path):
    execution = tmp_path / "execution.json"
    outputs = tmp_path / "outputs.jsonl"

    _write_execution_receipt(execution)
    _write_outputs(outputs)

    receipt = evaluate_ecosystem_integrated_outputs(
        execution_receipt_path=execution,
        ecosystem_outputs_path=outputs,
        output_dir=tmp_path / "scores",
    )

    boundary = receipt.boundary.lower()
    assert "organ-fit" in boundary
    assert "does not rejoin arm labels" in boundary
    assert "does not compare arms" in boundary
    assert "does not constitute adaptive" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_evaluator_cli_runner(tmp_path):
    execution = tmp_path / "execution.json"
    outputs = tmp_path / "outputs.jsonl"
    output_dir = tmp_path / "scores"

    _write_execution_receipt(execution)
    _write_outputs(outputs)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_ecosystem_integrated_rubric_evaluator.py",
            "--execution-receipt",
            str(execution),
            "--ecosystem-outputs",
            str(outputs),
            "--output",
            str(output_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_READY_TOKEN in completed.stdout
    assert (output_dir / "ecosystem_integrated_rubric_evaluation_receipt.json").exists()
    assert (output_dir / "ecosystem_integrated_rubric_scores.jsonl").exists()
    assert (output_dir / "ecosystem_integrated_score_summary.json").exists()
