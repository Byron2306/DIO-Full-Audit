from __future__ import annotations

import json
from pathlib import Path

from experiments.metamorphic_adaptation.t24_canonical_continuity_digest_gate import (
    T24_CANONICAL_CONTINUITY_DIGEST_READY_TOKEN,
    build_t24_canonical_continuity_digest,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _seed_receipt_pack(root: Path) -> None:
    tiers = {
        "t1.json": {"allowed_claim_tier": "T1_FIXTURE_MECHANICS_PROVEN_NO_ADAPTIVE_CLAIM", "status": "DIO_METAMORPHIC_ADAPTATION_FIXTURE_EXPERIMENT_DIGEST_READY"},
        "t2.json": {"allowed_claim_tier": "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY", "status": "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_DIGEST_READY"},
        "t3.json": {"allowed_claim_tier": "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY", "status": "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_READY"},
        "t4.json": {"allowed_claim_tier": "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM", "status": "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_READY"},
        "t5.json": {"allowed_claim_tier": "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM", "status": "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY"},
        "t6.json": {"allowed_claim_tier": "T6_CANDIDATE_RETAINED_ECOSYSTEM_ADAPTATION_EVIDENCE", "status": "DIO_METAMORPHIC_ADAPTATION_SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY"},
        "t7.json": {"marketing_claim_tier": "T7_MARKETING_SAFE_MARKET_COMMAND_SENSORIUM_PIVOTING_ADAPTATION", "status": "DIO_METAMORPHIC_ADAPTATION_MARKET_COMMAND_MARKETING_PROOF_PACK_READY"},
        "t8.json": {"marketing_claim_tier": "T8_MARKETING_SAFE_ADAPTIVE_LINGUISTIC_MARKET_RECOMPOSITION", "status": "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_LINGUISTIC_MARKETING_PROOF_PACK_READY"},
        "t9.json": {"allowed_claim_tier": "T9_CANDIDATE_AUDIENCE_MORPHOLOGY_SEMANTIC_RECOMPOSITION_EVIDENCE", "status": "DIO_METAMORPHIC_ADAPTATION_AUDIENCE_MORPHOLOGY_RECOMPOSITION_GAUNTLET_READY"},
        "t10.json": {"marketing_claim_tier": "T10_MARKETING_SAFE_ATLAS_GUIDED_DOMAIN_PRODUCT_COMPOSITION", "status": "DIO_METAMORPHIC_ADAPTATION_ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY"},
        "t11.json": {"marketing_claim_tier": "T11_MARKETING_SAFE_GOVERNED_PRODUCT_INCARNATION_DEVELOPMENT", "status": "DIO_METAMORPHIC_ADAPTATION_PRODUCT_INCARNATION_MARKETING_PROOF_PACK_READY"},
        "t12.json": {"marketing_claim_tier": "T12_MARKETING_SAFE_GOVERNED_PRODUCT_PORTFOLIO_PRIORITIZATION", "status": "DIO_METAMORPHIC_ADAPTATION_PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY"},
        "t13.json": {"marketing_claim_tier": "T13_MARKETING_SAFE_SELECTED_PRODUCT_SPRINT_PLANNING", "status": "DIO_METAMORPHIC_ADAPTATION_SELECTED_PRODUCT_SPRINT_MARKETING_PROOF_PACK_READY"},
        "t14.json": {"allowed_claim_tier": "T14_CANDIDATE_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_EVIDENCE", "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_READY"},
        "t15.json": {"marketing_claim_tier": "T15_MARKETING_SAFE_CAPABILITY_EXECUTION_READINESS_MAPPING", "status": "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MARKETING_PROOF_PACK_READY"},
        "t16.json": {"marketing_claim_tier": "T16_MARKETING_SAFE_CONTROLLED_LOCAL_STARTER_CODE_GENERATION", "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_STARTER_CODE_MARKETING_PROOF_PACK_READY"},
        "t17.json": {"marketing_claim_tier": "T17_MARKETING_SAFE_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION", "status": "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_MARKETING_PROOF_PACK_READY"},
        "t18.json": {"marketing_claim_tier": "T18_MARKETING_SAFE_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN", "status": "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_MARKETING_PROOF_PACK_READY"},
    }
    for name, payload in tiers.items():
        _write(root / name, payload)


def test_t24_builds_complete_source_bound_continuity_digest(tmp_path: Path) -> None:
    pack = tmp_path / "receipt_pack"
    _seed_receipt_pack(pack)
    extra = tmp_path / "local_receipts"
    for tier in range(19, 24):
        _write(extra / f"t{tier}.json", {"allowed_claim_tier": f"T{tier}_LOCAL_TEST_TIER", "status": f"DIO_METAMORPHIC_ADAPTATION_T{tier}_READY"})
    output = tmp_path / "out" / "t24.json"

    receipt = build_t24_canonical_continuity_digest(
        receipt_pack_dir=pack,
        extra_receipt_dirs=[extra],
        output_path=output,
    )

    assert receipt.status == T24_CANONICAL_CONTINUITY_DIGEST_READY_TOKEN
    assert receipt.allowed_claim_tier == "T24_INTERNAL_CANONICAL_T1_T23_CONTINUITY_DIGEST"
    assert receipt.stages_expected == 23
    assert receipt.stages_source_bound == 23
    assert receipt.gaps_pending == []
    assert receipt.tiers_present["T7"] is True
    assert receipt.tiers_present["T9"] is True
    assert receipt.tiers_present["T14"] is True
    assert receipt.tiers_present["T23"] is True
    assert receipt.external_deployment_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert output.exists()


def test_t24_marks_missing_tiers_as_gap_pending(tmp_path: Path) -> None:
    pack = tmp_path / "partial_pack"
    _write(pack / "t1.json", {"allowed_claim_tier": "T1_FIXTURE_MECHANICS_PROVEN_NO_ADAPTIVE_CLAIM"})
    output = tmp_path / "out" / "t24.json"

    receipt = build_t24_canonical_continuity_digest(
        receipt_pack_dir=pack,
        extra_receipt_dirs=[],
        output_path=output,
    )

    assert receipt.status != T24_CANONICAL_CONTINUITY_DIGEST_READY_TOKEN
    assert "T2" in receipt.gaps_pending
    assert "T23" in receipt.gaps_pending
    assert receipt.authority_expansion_authorized is False
