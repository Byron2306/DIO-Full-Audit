import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.metamorphic_adaptation_evidence_digest import (
    METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN,
    METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN,
    METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_VERSION,
    build_metamorphic_adaptation_evidence_digest,
    write_metamorphic_adaptation_evidence_digest,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _chain(tmp_path, *, full_ready=True, quality_ready=True, verdict_ready=True, adaptive=False):
    full_transfer = tmp_path / "full_controlled_transfer_digest.json"
    quality = tmp_path / "real_task_quality_digest.json"
    verdict = tmp_path / "adaptive_evidence_verdict.json"

    _write(full_transfer, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_READY"
            if full_ready
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_REFUSED"
        ),
        "full_transfer_end_to_end_proven": full_ready,
        "adaptive_claim_authorized": False,
    })
    _write(quality, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_READY"
            if quality_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_REFUSED"
        ),
        "real_task_quality_end_to_end_proven": quality_ready,
        "quality_pipeline_exercised": quality_ready,
        "mean_quality_score": 1.0,
        "baseline_arm": "A_STATELESS_RESET",
        "baseline_arm_mean": 1.0,
        "full_arm": "E_FULL_SEMANTIC_MARKET_BEAST",
        "full_arm_mean": 1.0 if not adaptive else 1.25,
        "full_minus_baseline_effect": 0.0 if not adaptive else 0.25,
        "adaptive_claim_authorized": False,
    })
    _write(verdict, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_EVIDENCE_VERDICT_READY"
            if verdict_ready
            else "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_EVIDENCE_VERDICT_REFUSED"
        ),
        "real_task_quality_digest_status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_READY"
            if quality_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_REFUSED"
        ),
        "quality_pipeline_exercised": quality_ready,
        "mean_quality_score": 1.0,
        "baseline_arm": "A_STATELESS_RESET",
        "baseline_arm_mean": 1.0,
        "full_arm": "E_FULL_SEMANTIC_MARKET_BEAST",
        "full_arm_mean": 1.0 if not adaptive else 1.25,
        "full_minus_baseline_effect": 0.0 if not adaptive else 0.25,
        "minimum_mean_quality_score": 0.6,
        "minimum_full_minus_baseline_effect": 0.15,
        "quality_threshold_met": True,
        "adaptive_effect_threshold_met": adaptive,
        "adaptive_evidence_verdict": (
            "ADAPTIVE_EVIDENCE_THRESHOLD_MET"
            if adaptive
            else "NO_ADAPTIVE_EVIDENCE_THRESHOLD_NOT_MET"
        ),
        "allowed_claim_tier": (
            "T5_BOUNDED_ADAPTIVE_EVIDENCE_CLAIM"
            if adaptive
            else "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
        ),
        "real_adaptive_evidence": adaptive,
        "adaptive_claim_authorized": adaptive,
        "commercial_or_world_first_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "authority_expansion_authorized": False,
    })
    return full_transfer, quality, verdict


def test_evidence_digest_binds_non_adaptive_verdict(tmp_path):
    full_transfer, quality, verdict = _chain(tmp_path)

    digest = build_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=full_transfer,
        real_task_quality_digest_path=quality,
        adaptive_evidence_verdict_path=verdict,
    )

    assert digest.digest_version == METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_VERSION
    assert digest.status == METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN
    assert digest.full_transfer_end_to_end_proven is True
    assert digest.real_task_quality_end_to_end_proven is True
    assert digest.quality_pipeline_exercised is True
    assert digest.quality_threshold_met is True
    assert digest.adaptive_effect_threshold_met is False
    assert digest.adaptive_evidence_verdict == "NO_ADAPTIVE_EVIDENCE_THRESHOLD_NOT_MET"
    assert digest.allowed_claim_tier == "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
    assert digest.real_adaptive_evidence is False
    assert digest.adaptive_claim_authorized is False
    assert digest.commercial_or_world_first_claim_authorized is False
    assert digest.authority_expansion_authorized is False


def test_evidence_digest_can_bind_bounded_adaptive_verdict_without_external_authority(tmp_path):
    full_transfer, quality, verdict = _chain(tmp_path, adaptive=True)

    digest = build_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=full_transfer,
        real_task_quality_digest_path=quality,
        adaptive_evidence_verdict_path=verdict,
    )

    assert digest.status == METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN
    assert digest.allowed_claim_tier == "T5_BOUNDED_ADAPTIVE_EVIDENCE_CLAIM"
    assert digest.real_adaptive_evidence is True
    assert digest.adaptive_claim_authorized is True
    assert digest.commercial_or_world_first_claim_authorized is False
    assert digest.professional_approval_claim_authorized is False
    assert digest.publication_authorized is False
    assert digest.spend_authorized is False
    assert digest.fulfilment_authorized is False
    assert digest.authority_expansion_authorized is False


def test_evidence_digest_refuses_without_full_transfer_digest(tmp_path):
    full_transfer, quality, verdict = _chain(tmp_path, full_ready=False)

    digest = build_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=full_transfer,
        real_task_quality_digest_path=quality,
        adaptive_evidence_verdict_path=verdict,
    )

    assert digest.status == METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN
    assert digest.allowed_claim_tier == "T0_NO_CLAIM"
    assert digest.real_adaptive_evidence is False
    assert digest.adaptive_claim_authorized is False


def test_evidence_digest_refuses_without_quality_digest(tmp_path):
    full_transfer, quality, verdict = _chain(tmp_path, quality_ready=False)

    digest = build_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=full_transfer,
        real_task_quality_digest_path=quality,
        adaptive_evidence_verdict_path=verdict,
    )

    assert digest.status == METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN
    assert digest.allowed_claim_tier == "T0_NO_CLAIM"
    assert digest.real_task_quality_end_to_end_proven is False


def test_evidence_digest_refuses_without_adaptive_verdict(tmp_path):
    full_transfer, quality, verdict = _chain(tmp_path, verdict_ready=False)

    digest = build_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=full_transfer,
        real_task_quality_digest_path=quality,
        adaptive_evidence_verdict_path=verdict,
    )

    assert digest.status == METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN
    assert digest.allowed_claim_tier == "T0_NO_CLAIM"
    assert digest.adaptive_evidence_verdict == "NO_ADAPTIVE_EVIDENCE_THRESHOLD_NOT_MET"


def test_evidence_digest_writes_json_and_hashes_sources(tmp_path):
    full_transfer, quality, verdict = _chain(tmp_path)
    output = tmp_path / "metamorphic_adaptation_evidence_digest.json"

    digest = write_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=full_transfer,
        real_task_quality_digest_path=quality,
        adaptive_evidence_verdict_path=verdict,
        output_path=output,
    )

    data = json.loads(output.read_text())
    assert data == json.loads(json.dumps(asdict(digest)))
    assert len(data["full_transfer_digest_sha256"]) == 64
    assert len(data["real_task_quality_digest_sha256"]) == 64
    assert len(data["adaptive_evidence_verdict_sha256"]) == 64


def test_evidence_digest_boundary_blocks_external_overclaiming(tmp_path):
    full_transfer, quality, verdict = _chain(tmp_path)

    digest = build_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=full_transfer,
        real_task_quality_digest_path=quality,
        adaptive_evidence_verdict_path=verdict,
    )

    boundary = digest.boundary.lower()
    assert "full controlled-transfer smoke digest" in boundary
    assert "real task-quality digest" in boundary
    assert "adaptive evidence verdict" in boundary
    assert "never authorizes commercial validation" in boundary
    assert "world-first status" in boundary
    assert "authority expansion" in boundary


def test_evidence_digest_cli_runner(tmp_path):
    full_transfer, quality, verdict = _chain(tmp_path)
    output = tmp_path / "metamorphic_adaptation_evidence_digest.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_evidence_digest.py",
            "--full-transfer-digest",
            str(full_transfer),
            "--real-task-quality-digest",
            str(quality),
            "--adaptive-evidence-verdict",
            str(verdict),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN in completed.stdout
    assert output.exists()
