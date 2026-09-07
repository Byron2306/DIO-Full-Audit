from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.marketing_proof_boundary_pack import (
    MARKETING_PROOF_BOUNDARY_PACK_READY_TOKEN,
    MARKETING_PROOF_BOUNDARY_PACK_REFUSED_TOKEN,
    build_marketing_proof_boundary_pack,
)


def _write_ecosystem_digest(path: Path, *, ready: bool = True) -> None:
    path.write_text(json.dumps({
        "status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY" if ready else "NOPE",
        "real_ecosystem_adaptive_evidence": ready,
        "adaptive_claim_authorized": ready,
        "allowed_claim_tier": "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM",
        "baseline_arm_mean": 0.673,
        "full_arm_mean": 1.0,
        "full_minus_baseline_effect": 0.327,
        "commercial_or_world_first_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "authority_expansion_authorized": False,
    }))


def _write_t6_receipt(path: Path, *, ready: bool = True) -> None:
    path.write_text(json.dumps({
        "status": "DIO_METAMORPHIC_ADAPTATION_SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY" if ready else "NOPE",
        "real_retained_adaptive_evidence": ready,
        "adaptive_claim_authorized": ready,
        "allowed_claim_tier": "T6_CANDIDATE_SEQUENTIAL_RETAINED_ECOSYSTEM_ADAPTATION_EVIDENCE",
        "encounters_executed": 3,
        "outputs_produced": 15,
        "same_executor_across_encounters": True,
        "code_change_between_encounters_authorized": False,
        "encounter_1_mean_score": 0.74,
        "encounter_2_mean_score": 0.82,
        "encounter_3_mean_score": 0.90,
        "encounter_3_minus_encounter_1_effect": 0.16,
        "commercial_or_world_first_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "authority_expansion_authorized": False,
    }))


def test_builds_marketing_safe_pack_from_t5_and_t6(tmp_path):
    ecosystem_digest = tmp_path / "ecosystem_digest.json"
    t6_receipt = tmp_path / "t6.json"
    output_dir = tmp_path / "marketing"
    _write_ecosystem_digest(ecosystem_digest)
    _write_t6_receipt(t6_receipt)

    receipt = build_marketing_proof_boundary_pack(
        ecosystem_adaptation_digest_path=ecosystem_digest,
        sequential_retained_gauntlet_path=t6_receipt,
        output_dir=output_dir,
    )

    assert receipt.status == MARKETING_PROOF_BOUNDARY_PACK_READY_TOKEN
    assert receipt.bounded_marketing_language_authorized is True
    assert receipt.marketing_claim_tier == "T6_MARKETING_SAFE_CANDIDATE_RETAINED_ECOSYSTEM_ADAPTATION"
    assert receipt.allowed_public_claims_count >= 5
    assert receipt.forbidden_public_claims_count >= 8
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.world_first_claim_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert Path(receipt.marketing_claims_path).exists()
    assert Path(receipt.marketing_copy_path).exists()

    claims = json.loads(Path(receipt.marketing_claims_path).read_text())
    assert any("bounded ecosystem adaptive evidence" in claim for claim in claims["allowed_public_claims"])
    assert any("T6 candidate" in claim for claim in claims["allowed_public_claims"])
    assert "DIO is AGI" in claims["forbidden_public_claims"]
    assert claims["proof_numbers"]["t5_full_minus_baseline_effect"] == 0.327
    assert claims["proof_numbers"]["t6_encounter_3_minus_encounter_1_effect"] == 0.16

    copy = Path(receipt.marketing_copy_path).read_text()
    assert "Marketing-safe claim" in copy
    assert "Not AGI" in copy
    assert "Not commercial validation" in copy


def test_refuses_when_t6_not_ready(tmp_path):
    ecosystem_digest = tmp_path / "ecosystem_digest.json"
    t6_receipt = tmp_path / "t6.json"
    output_dir = tmp_path / "marketing"
    _write_ecosystem_digest(ecosystem_digest)
    _write_t6_receipt(t6_receipt, ready=False)

    receipt = build_marketing_proof_boundary_pack(
        ecosystem_adaptation_digest_path=ecosystem_digest,
        sequential_retained_gauntlet_path=t6_receipt,
        output_dir=output_dir,
    )

    assert receipt.status == MARKETING_PROOF_BOUNDARY_PACK_REFUSED_TOKEN
    assert receipt.bounded_marketing_language_authorized is False
    assert receipt.allowed_public_claims_count == 0
    assert receipt.adaptive_claim_authorized is False


def test_refuses_when_ecosystem_digest_not_ready(tmp_path):
    ecosystem_digest = tmp_path / "ecosystem_digest.json"
    t6_receipt = tmp_path / "t6.json"
    output_dir = tmp_path / "marketing"
    _write_ecosystem_digest(ecosystem_digest, ready=False)
    _write_t6_receipt(t6_receipt)

    receipt = build_marketing_proof_boundary_pack(
        ecosystem_adaptation_digest_path=ecosystem_digest,
        sequential_retained_gauntlet_path=t6_receipt,
        output_dir=output_dir,
    )

    assert receipt.status == MARKETING_PROOF_BOUNDARY_PACK_REFUSED_TOKEN
    assert receipt.marketing_claim_tier == "T0_NO_MARKETING_PROOF_CLAIM"
    assert receipt.commercial_validation_claim_authorized is False


def test_cli_runner_writes_pack(tmp_path):
    ecosystem_digest = tmp_path / "ecosystem_digest.json"
    t6_receipt = tmp_path / "t6.json"
    output_dir = tmp_path / "marketing"
    _write_ecosystem_digest(ecosystem_digest)
    _write_t6_receipt(t6_receipt)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_marketing_proof_boundary_pack.py",
            "--ecosystem-adaptation-digest",
            str(ecosystem_digest),
            "--sequential-retained-gauntlet",
            str(t6_receipt),
            "--output",
            str(output_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert MARKETING_PROOF_BOUNDARY_PACK_READY_TOKEN in completed.stdout
    assert (output_dir / "marketing_proof_boundary_pack_receipt.json").exists()
    assert (output_dir / "marketing_safe_copy.md").exists()
