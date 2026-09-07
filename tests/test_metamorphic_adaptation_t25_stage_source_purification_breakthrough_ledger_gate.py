from __future__ import annotations

import json
from pathlib import Path

from experiments.metamorphic_adaptation.t25_stage_source_purification_breakthrough_ledger_gate import (
    T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_READY_TOKEN,
    build_t25_stage_source_purification_breakthrough_ledger,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _valid_t24_receipt() -> dict:
    tiers = {f"T{i}": True for i in range(1, 24)}
    return {
        "gate_version": "DIO_METAMORPHIC_ADAPTATION_T24_CANONICAL_CONTINUITY_DIGEST_GATE_V1",
        "status": "DIO_METAMORPHIC_ADAPTATION_T24_CANONICAL_CONTINUITY_DIGEST_READY",
        "source_bound": True,
        "continuity_digest_authorized": True,
        "stages_expected": 23,
        "stages_source_bound": 23,
        "gaps_pending": [],
        "tiers_present": tiers,
        "tier_sources": {
            "T1": [
                "evidence/metamorphic_adaptation/full_receipt_pack_20260907T104807Z/dio-metamorphic-adaptation-fixture-experiment-digest-1/fixture_experiment_digest.json",
                "evidence/metamorphic_adaptation/full_receipt_pack_20260907T104807Z/dio-metamorphic-adaptation-transfer-claim-gate-fixture-1/transfer_claim_gate.json",
            ],
            "T7": [
                "evidence/metamorphic_adaptation/full_receipt_pack_20260907T104807Z/RECEIPT_PACK_MANIFEST.json",
                "evidence/metamorphic_adaptation/full_receipt_pack_20260907T104807Z/dio-metamorphic-adaptation-market-command-sensorium-pivot-marketing-proof-pack-1/market_command_marketing_proof_pack_receipt.json",
                "evidence/metamorphic_adaptation/full_receipt_pack_20260907T104807Z/dio-metamorphic-adaptation-adaptive-linguistic-pivot-gauntlet-1/adaptive_linguistic_pivot_gauntlet_receipt.json",
            ],
            "T16": [
                "/data/data/com.termux/files/home/dio-runs/t22-html-proof-surface/dio_trust_dossier_studio/index.html",
                "evidence/metamorphic_adaptation/full_receipt_pack_20260907T104807Z/dio-metamorphic-adaptation-controlled-starter-code-generation-1/controlled_starter_code_generation_receipt.json",
            ],
            "T23": [
                "/data/data/com.termux/files/home/dio-runs/t22-html-proof-surface/dio_trust_dossier_studio/dossier_index.json",
                "/data/data/com.termux/files/home/dio-runs/t23-html-proof-surface-dossier-linking/t23_html_proof_surface_dossier_linking_receipt.json",
            ],
        },
        "actual_product_execution_authorized": False,
        "product_capability_execution_authorized": False,
        "external_use_authorized": False,
        "external_deployment_authorized": False,
        "autonomous_development_authorized": False,
        "autonomous_action_claim_authorized": False,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "agi_claim_authorized": False,
        "world_first_claim_authorized": False,
        "authority_expansion_authorized": False,
    }


def test_t25_purifies_stage_sources_and_writes_breakthrough_ledger(tmp_path: Path) -> None:
    t24_path = tmp_path / "t24" / "t24_canonical_continuity_digest_receipt.json"
    receipt_output = tmp_path / "t25" / "t25_stage_source_purification_breakthrough_ledger_receipt.json"
    markdown_output = tmp_path / "t25" / "DIO_METAMORPHIC_ADAPTATION_BREAKTHROUGH_LEDGER.md"
    _write_json(t24_path, _valid_t24_receipt())

    receipt = build_t25_stage_source_purification_breakthrough_ledger(
        t24_receipt_path=t24_path,
        receipt_output_path=receipt_output,
        markdown_output_path=markdown_output,
    )

    assert receipt.status == T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_READY_TOKEN
    assert receipt.allowed_claim_tier == "T25_INTERNAL_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER"
    assert receipt.source_bound is True
    assert receipt.stages_expected == 23
    assert receipt.stages_source_bound == 23
    assert receipt.gaps_pending == []
    assert receipt.stage_sources_purified is True
    assert receipt.breakthrough_ledger_written is True
    assert receipt.marketing_safe_breakthrough_summary_authorized is True
    assert receipt.primary_stage_sources["T7"].endswith("market_command_marketing_proof_pack_receipt.json")
    assert receipt.primary_stage_sources["T16"].endswith("controlled_starter_code_generation_receipt.json")
    assert receipt.primary_stage_sources["T23"].endswith("t23_html_proof_surface_dossier_linking_receipt.json")
    assert receipt.external_deployment_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert receipt_output.exists()
    assert markdown_output.exists()

    markdown = markdown_output.read_text()
    assert "# DIO Metamorphic Adaptation Breakthrough Ledger" in markdown
    assert "T7: market-command sensorium pivoting" in markdown
    assert "T8: adaptive linguistic market recomposition" in markdown
    assert "T11: governed product-incarnation development" in markdown
    assert "T16: controlled local starter-code generation" in markdown
    assert "T23: HTML proof surface dossier linking" in markdown
    assert "Not commercial validation" in markdown
    assert "Not AGI" in markdown


def test_t25_refuses_when_t24_has_gaps(tmp_path: Path) -> None:
    t24 = _valid_t24_receipt()
    t24["stages_source_bound"] = 22
    t24["gaps_pending"] = ["T9"]
    t24["tiers_present"]["T9"] = False
    t24_path = tmp_path / "bad" / "t24.json"
    receipt_output = tmp_path / "bad" / "receipt.json"
    markdown_output = tmp_path / "bad" / "ledger.md"
    _write_json(t24_path, t24)

    receipt = build_t25_stage_source_purification_breakthrough_ledger(
        t24_receipt_path=t24_path,
        receipt_output_path=receipt_output,
        markdown_output_path=markdown_output,
    )

    assert receipt.status == "DIO_METAMORPHIC_ADAPTATION_T25_STAGE_SOURCE_PURIFICATION_BREAKTHROUGH_LEDGER_REFUSED"
    assert receipt.stage_sources_purified is False
    assert receipt.breakthrough_ledger_written is False
    assert receipt.gaps_pending == ["T9"]
    assert not markdown_output.exists()
