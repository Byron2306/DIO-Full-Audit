import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.adaptive_evidence_verdict import (
    ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN,
    ADAPTIVE_EVIDENCE_VERDICT_REFUSED_TOKEN,
    ADAPTIVE_EVIDENCE_VERDICT_VERSION,
    evaluate_adaptive_evidence_verdict,
    write_adaptive_evidence_verdict,
)


def _write_digest(path, *, ready=True, mean=1.0, effect=0.0):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_REFUSED"
        ),
        "real_task_quality_end_to_end_proven": ready,
        "quality_pipeline_exercised": ready,
        "mean_quality_score": mean,
        "baseline_arm": "A_STATELESS_RESET",
        "baseline_arm_mean": 1.0,
        "full_arm": "E_FULL_SEMANTIC_MARKET_BEAST",
        "full_arm_mean": 1.0 + effect,
        "full_minus_baseline_effect": effect,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def test_adaptive_evidence_verdict_denies_equal_arm_quality(tmp_path):
    digest = tmp_path / "real_task_quality_digest.json"
    _write_digest(digest, mean=1.0, effect=0.0)

    receipt = evaluate_adaptive_evidence_verdict(real_task_quality_digest_path=digest)

    assert receipt.verdict_version == ADAPTIVE_EVIDENCE_VERDICT_VERSION
    assert receipt.status == ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN
    assert receipt.mean_quality_score == 1.0
    assert receipt.full_minus_baseline_effect == 0.0
    assert receipt.quality_threshold_met is True
    assert receipt.adaptive_effect_threshold_met is False
    assert receipt.adaptive_evidence_verdict == "NO_ADAPTIVE_EVIDENCE_THRESHOLD_NOT_MET"
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.allowed_claim_tier == "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
    assert receipt.commercial_or_world_first_claim_authorized is False


def test_adaptive_evidence_verdict_denies_low_quality_even_with_effect(tmp_path):
    digest = tmp_path / "real_task_quality_digest.json"
    _write_digest(digest, mean=0.4, effect=0.25)

    receipt = evaluate_adaptive_evidence_verdict(real_task_quality_digest_path=digest)

    assert receipt.quality_threshold_met is False
    assert receipt.adaptive_effect_threshold_met is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False


def test_adaptive_evidence_verdict_allows_only_bounded_adaptive_claim_when_thresholds_met(tmp_path):
    digest = tmp_path / "real_task_quality_digest.json"
    _write_digest(digest, mean=0.8, effect=0.2)

    receipt = evaluate_adaptive_evidence_verdict(real_task_quality_digest_path=digest)

    assert receipt.status == ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN
    assert receipt.adaptive_evidence_verdict == "ADAPTIVE_EVIDENCE_THRESHOLD_MET"
    assert receipt.real_adaptive_evidence is True
    assert receipt.adaptive_claim_authorized is True
    assert receipt.allowed_claim_tier == "T5_CROSS_ENCOUNTER_ADAPTIVE_COMPOSITION_OBSERVED"
    assert receipt.commercial_or_world_first_claim_authorized is False
    assert receipt.professional_approval_claim_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_adaptive_evidence_verdict_refuses_unready_digest(tmp_path):
    digest = tmp_path / "real_task_quality_digest.json"
    _write_digest(digest, ready=False, mean=1.0, effect=1.0)

    receipt = evaluate_adaptive_evidence_verdict(real_task_quality_digest_path=digest)

    assert receipt.status == ADAPTIVE_EVIDENCE_VERDICT_REFUSED_TOKEN
    assert receipt.adaptive_evidence_verdict == "NO_ADAPTIVE_EVIDENCE_DIGEST_NOT_READY"
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.allowed_claim_tier == "T0_NO_CLAIM"


def test_adaptive_evidence_verdict_writes_json_and_hash(tmp_path):
    digest = tmp_path / "real_task_quality_digest.json"
    output = tmp_path / "adaptive_evidence_verdict.json"
    _write_digest(digest, mean=1.0, effect=0.0)

    receipt = write_adaptive_evidence_verdict(
        real_task_quality_digest_path=digest,
        output_path=output,
    )

    data = json.loads(output.read_text())
    assert data == json.loads(json.dumps(asdict(receipt)))
    assert len(data["real_task_quality_digest_sha256"]) == 64


def test_adaptive_evidence_verdict_boundary_blocks_overclaiming(tmp_path):
    digest = tmp_path / "real_task_quality_digest.json"
    _write_digest(digest, mean=0.8, effect=0.2)

    receipt = evaluate_adaptive_evidence_verdict(real_task_quality_digest_path=digest)
    boundary = receipt.boundary.lower()

    assert "predeclared quality" in boundary
    assert "full-minus-baseline effect" in boundary
    assert "bounded adaptive-evidence claim" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_adaptive_evidence_verdict_cli_runner(tmp_path):
    digest = tmp_path / "real_task_quality_digest.json"
    output = tmp_path / "adaptive_evidence_verdict.json"
    _write_digest(digest, mean=1.0, effect=0.0)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_adaptive_evidence_verdict.py",
            "--real-task-quality-digest",
            str(digest),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN in completed.stdout
    assert output.exists()
