import json
import subprocess
import sys

from experiments.metamorphic_adaptation.ecosystem_adaptive_evidence_verdict import (
    ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN,
    ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_REFUSED_TOKEN,
    ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_VERSION,
    evaluate_ecosystem_adaptive_evidence,
)


def _write_arm_analysis(path, *, ready=True, mean_quality=0.8026, effect=0.327):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_REFUSED"
        ),
        "ecosystem_arm_analysis_authorized": ready,
        "adaptive_claim_authorized": False,
        "arms_analyzed": 5 if ready else 0,
        "tasks_analyzed": 5 if ready else 0,
        "mean_ecosystem_quality_score": mean_quality,
        "mean_organ_coverage_score": 0.561333,
        "baseline_arm": "A_DIO_CORE_ONLY",
        "baseline_arm_mean": 0.673,
        "full_arm": "E_FULL_ECOSYSTEM_ORCHESTRATION",
        "full_arm_mean": 1.0,
        "full_minus_baseline_effect": effect,
    }, indent=2, sort_keys=True))


def test_ecosystem_adaptive_evidence_verdict_authorizes_bounded_t5_when_thresholds_met(tmp_path):
    arm_analysis = tmp_path / "arm_analysis.json"
    _write_arm_analysis(arm_analysis)

    verdict = evaluate_ecosystem_adaptive_evidence(arm_analysis_path=arm_analysis)

    assert verdict.verdict_version == ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_VERSION
    assert verdict.status == ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN
    assert verdict.ecosystem_quality_threshold_met is True
    assert verdict.ecosystem_adaptive_effect_threshold_met is True
    assert verdict.ecosystem_adaptive_evidence_verdict == "ECOSYSTEM_ADAPTIVE_EVIDENCE_THRESHOLD_MET"
    assert verdict.allowed_claim_tier == "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM"
    assert verdict.real_ecosystem_adaptive_evidence is True
    assert verdict.adaptive_claim_authorized is True
    assert verdict.commercial_or_world_first_claim_authorized is False
    assert verdict.authority_expansion_authorized is False


def test_ecosystem_adaptive_evidence_verdict_refuses_when_effect_threshold_not_met(tmp_path):
    arm_analysis = tmp_path / "arm_analysis.json"
    _write_arm_analysis(arm_analysis, effect=0.0)

    verdict = evaluate_ecosystem_adaptive_evidence(arm_analysis_path=arm_analysis)

    assert verdict.status == ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN
    assert verdict.ecosystem_quality_threshold_met is True
    assert verdict.ecosystem_adaptive_effect_threshold_met is False
    assert verdict.real_ecosystem_adaptive_evidence is False
    assert verdict.adaptive_claim_authorized is False
    assert verdict.allowed_claim_tier == "T4_ECOSYSTEM_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"


def test_ecosystem_adaptive_evidence_verdict_refuses_when_quality_threshold_not_met(tmp_path):
    arm_analysis = tmp_path / "arm_analysis.json"
    _write_arm_analysis(arm_analysis, mean_quality=0.4, effect=0.327)

    verdict = evaluate_ecosystem_adaptive_evidence(arm_analysis_path=arm_analysis)

    assert verdict.status == ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN
    assert verdict.ecosystem_quality_threshold_met is False
    assert verdict.ecosystem_adaptive_effect_threshold_met is True
    assert verdict.real_ecosystem_adaptive_evidence is False
    assert verdict.adaptive_claim_authorized is False


def test_ecosystem_adaptive_evidence_verdict_refuses_unready_source(tmp_path):
    arm_analysis = tmp_path / "arm_analysis.json"
    _write_arm_analysis(arm_analysis, ready=False)

    verdict = evaluate_ecosystem_adaptive_evidence(arm_analysis_path=arm_analysis)

    assert verdict.status == ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_REFUSED_TOKEN
    assert verdict.allowed_claim_tier == "T0_NO_CLAIM"
    assert verdict.real_ecosystem_adaptive_evidence is False
    assert verdict.adaptive_claim_authorized is False


def test_ecosystem_adaptive_evidence_boundary_never_authorizes_overclaiming(tmp_path):
    arm_analysis = tmp_path / "arm_analysis.json"
    _write_arm_analysis(arm_analysis)

    verdict = evaluate_ecosystem_adaptive_evidence(arm_analysis_path=arm_analysis)
    boundary = verdict.boundary.lower()

    assert "bounded ecosystem adaptive-evidence claim" in boundary
    assert "never authorizes commercial validation" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary
    assert verdict.commercial_or_world_first_claim_authorized is False
    assert verdict.professional_approval_claim_authorized is False
    assert verdict.publication_authorized is False
    assert verdict.spend_authorized is False
    assert verdict.fulfilment_authorized is False
    assert verdict.authority_expansion_authorized is False


def test_ecosystem_adaptive_evidence_verdict_cli_runner(tmp_path):
    arm_analysis = tmp_path / "arm_analysis.json"
    output = tmp_path / "verdict.json"
    _write_arm_analysis(arm_analysis)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_ecosystem_adaptive_evidence_verdict.py",
            "--arm-analysis",
            str(arm_analysis),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN in completed.stdout
    saved = json.loads(output.read_text())
    assert saved["real_ecosystem_adaptive_evidence"] is True
    assert saved["adaptive_claim_authorized"] is True
