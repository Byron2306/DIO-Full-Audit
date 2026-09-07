import json
import subprocess
import sys

from experiments.metamorphic_adaptation.ecosystem_adaptation_evidence_digest import (
    ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN,
    ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN,
    ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_VERSION,
    write_ecosystem_adaptation_evidence_digest,
)


def _write(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _registry(path, *, ready=True):
    _write(path, {
        "status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY" if ready else "NOPE",
        "organs_registered": 11,
        "real_ecosystem_execution_authorized": ready,
        "adaptive_claim_authorized": False,
    })


def _plan(path, *, ready=True):
    _write(path, {
        "status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY" if ready else "NOPE",
        "tests_true_adaptive_surface": ready,
        "planned_encounters": 25,
        "adaptive_claim_authorized": False,
    })


def _execution(path, *, ready=True):
    _write(path, {
        "status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_EXECUTION_READY" if ready else "NOPE",
        "executed": ready,
        "ecosystem_outputs_produced": 25,
        "ecosystem_quality_scoring_authorized": ready,
        "organ_gap_outputs": 16,
        "full_coverage_outputs": 9,
        "adaptive_claim_authorized": False,
    })


def _rubric(path, *, ready=True):
    _write(path, {
        "status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATION_READY" if ready else "NOPE",
        "ecosystem_scores_written": 25,
        "ecosystem_arm_analysis_authorized": ready,
        "mean_ecosystem_quality_score": 0.8026,
        "mean_organ_coverage_score": 0.561333,
        "organ_gap_outputs": 16,
        "full_coverage_outputs": 9,
        "adaptive_claim_authorized": False,
    })


def _arm_analysis(path, *, ready=True):
    _write(path, {
        "status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY" if ready else "NOPE",
        "arms_analyzed": 5,
        "tasks_analyzed": 5,
        "baseline_arm": "A_DIO_CORE_ONLY",
        "baseline_arm_mean": 0.673,
        "full_arm": "E_FULL_ECOSYSTEM_ORCHESTRATION",
        "full_arm_mean": 1.0,
        "full_minus_baseline_effect": 0.327,
        "adaptive_claim_authorized": False,
    })


def _verdict(path, *, ready=True, positive=True):
    _write(path, {
        "status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY" if ready else "NOPE",
        "arm_analysis_status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY",
        "mean_ecosystem_quality_score": 0.8026,
        "mean_organ_coverage_score": 0.561333,
        "baseline_arm": "A_DIO_CORE_ONLY",
        "baseline_arm_mean": 0.673,
        "full_arm": "E_FULL_ECOSYSTEM_ORCHESTRATION",
        "full_arm_mean": 1.0,
        "full_minus_baseline_effect": 0.327,
        "minimum_mean_ecosystem_quality_score": 0.6,
        "minimum_full_minus_baseline_effect": 0.15,
        "ecosystem_quality_threshold_met": positive,
        "ecosystem_adaptive_effect_threshold_met": positive,
        "ecosystem_adaptive_evidence_verdict": (
            "ECOSYSTEM_ADAPTIVE_EVIDENCE_THRESHOLD_MET" if positive else "NO_ECOSYSTEM_ADAPTIVE_EVIDENCE_THRESHOLD_NOT_MET"
        ),
        "allowed_claim_tier": (
            "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM" if positive else "T4_ECOSYSTEM_QUALITY_PIPELINE_ONLY_NO_ADAPTIVE_CLAIM"
        ),
        "real_ecosystem_adaptive_evidence": positive,
        "adaptive_claim_authorized": positive,
    })


def _write_all(tmp_path, **kwargs):
    registry = tmp_path / "registry.json"
    plan = tmp_path / "plan.json"
    execution = tmp_path / "execution.json"
    rubric = tmp_path / "rubric.json"
    arm = tmp_path / "arm.json"
    verdict = tmp_path / "verdict.json"
    _registry(registry, ready=kwargs.get("registry_ready", True))
    _plan(plan, ready=kwargs.get("plan_ready", True))
    _execution(execution, ready=kwargs.get("execution_ready", True))
    _rubric(rubric, ready=kwargs.get("rubric_ready", True))
    _arm_analysis(arm, ready=kwargs.get("arm_ready", True))
    _verdict(verdict, ready=kwargs.get("verdict_ready", True), positive=kwargs.get("positive", True))
    return registry, plan, execution, rubric, arm, verdict


def test_ecosystem_adaptation_digest_binds_positive_verdict(tmp_path):
    paths = _write_all(tmp_path)
    output = tmp_path / "digest.json"

    digest = write_ecosystem_adaptation_evidence_digest(
        organ_registry_receipt_path=paths[0],
        ecosystem_plan_receipt_path=paths[1],
        ecosystem_execution_receipt_path=paths[2],
        ecosystem_rubric_evaluation_receipt_path=paths[3],
        ecosystem_arm_analysis_receipt_path=paths[4],
        ecosystem_adaptive_verdict_path=paths[5],
        output_path=output,
    )

    assert digest.digest_version == ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_VERSION
    assert digest.status == ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN
    assert digest.real_ecosystem_adaptive_evidence is True
    assert digest.adaptive_claim_authorized is True
    assert digest.allowed_claim_tier == "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM"
    assert digest.full_minus_baseline_effect == 0.327
    assert digest.commercial_or_world_first_claim_authorized is False
    assert digest.authority_expansion_authorized is False
    assert output.exists()


def test_ecosystem_adaptation_digest_refuses_unready_component(tmp_path):
    paths = _write_all(tmp_path, execution_ready=False)
    output = tmp_path / "digest.json"

    digest = write_ecosystem_adaptation_evidence_digest(
        organ_registry_receipt_path=paths[0],
        ecosystem_plan_receipt_path=paths[1],
        ecosystem_execution_receipt_path=paths[2],
        ecosystem_rubric_evaluation_receipt_path=paths[3],
        ecosystem_arm_analysis_receipt_path=paths[4],
        ecosystem_adaptive_verdict_path=paths[5],
        output_path=output,
    )

    assert digest.status == ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN
    assert digest.real_ecosystem_adaptive_evidence is False
    assert digest.adaptive_claim_authorized is False
    assert digest.allowed_claim_tier == "T0_NO_CLAIM"


def test_ecosystem_adaptation_digest_preserves_negative_verdict(tmp_path):
    paths = _write_all(tmp_path, positive=False)
    output = tmp_path / "digest.json"

    digest = write_ecosystem_adaptation_evidence_digest(
        organ_registry_receipt_path=paths[0],
        ecosystem_plan_receipt_path=paths[1],
        ecosystem_execution_receipt_path=paths[2],
        ecosystem_rubric_evaluation_receipt_path=paths[3],
        ecosystem_arm_analysis_receipt_path=paths[4],
        ecosystem_adaptive_verdict_path=paths[5],
        output_path=output,
    )

    assert digest.status == ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN
    assert digest.real_ecosystem_adaptive_evidence is False
    assert digest.adaptive_claim_authorized is False
    assert digest.allowed_claim_tier == "T4_ECOSYSTEM_QUALITY_PIPELINE_ONLY_NO_ADAPTIVE_CLAIM"


def test_ecosystem_adaptation_digest_records_hashes(tmp_path):
    paths = _write_all(tmp_path)
    output = tmp_path / "digest.json"
    digest = write_ecosystem_adaptation_evidence_digest(
        organ_registry_receipt_path=paths[0],
        ecosystem_plan_receipt_path=paths[1],
        ecosystem_execution_receipt_path=paths[2],
        ecosystem_rubric_evaluation_receipt_path=paths[3],
        ecosystem_arm_analysis_receipt_path=paths[4],
        ecosystem_adaptive_verdict_path=paths[5],
        output_path=output,
    )

    assert len(digest.organ_registry_sha256) == 64
    assert len(digest.ecosystem_plan_sha256) == 64
    assert len(digest.ecosystem_execution_sha256) == 64
    assert len(digest.ecosystem_rubric_evaluation_sha256) == 64
    assert len(digest.ecosystem_arm_analysis_sha256) == 64
    assert len(digest.ecosystem_adaptive_verdict_sha256) == 64


def test_ecosystem_adaptation_digest_boundary_blocks_overclaiming(tmp_path):
    paths = _write_all(tmp_path)
    output = tmp_path / "digest.json"
    digest = write_ecosystem_adaptation_evidence_digest(
        organ_registry_receipt_path=paths[0],
        ecosystem_plan_receipt_path=paths[1],
        ecosystem_execution_receipt_path=paths[2],
        ecosystem_rubric_evaluation_receipt_path=paths[3],
        ecosystem_arm_analysis_receipt_path=paths[4],
        ecosystem_adaptive_verdict_path=paths[5],
        output_path=output,
    )
    boundary = digest.boundary.lower()

    assert "bounded claim tier" in boundary
    assert "commercial validation" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary
    assert digest.publication_authorized is False
    assert digest.spend_authorized is False
    assert digest.fulfilment_authorized is False


def test_ecosystem_adaptation_digest_cli_runner(tmp_path):
    paths = _write_all(tmp_path)
    output = tmp_path / "digest.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_ecosystem_adaptation_evidence_digest.py",
            "--organ-registry-receipt", str(paths[0]),
            "--ecosystem-plan-receipt", str(paths[1]),
            "--ecosystem-execution-receipt", str(paths[2]),
            "--ecosystem-rubric-evaluation-receipt", str(paths[3]),
            "--ecosystem-arm-analysis-receipt", str(paths[4]),
            "--ecosystem-adaptive-verdict", str(paths[5]),
            "--output", str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN in completed.stdout
    assert output.exists()
