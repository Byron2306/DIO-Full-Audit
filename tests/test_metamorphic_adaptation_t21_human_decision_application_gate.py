from __future__ import annotations

import json
from pathlib import Path

from experiments.metamorphic_adaptation.t21_human_decision_application_gate import (
    T21_HUMAN_DECISION_APPLICATION_READY_TOKEN,
    apply_t21_human_decision,
)


def _write_t20(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "DIO_METAMORPHIC_ADAPTATION_T20_HUMAN_APPROVAL_DECISION_PACKET_READY",
                "allowed_claim_tier": "T20_INTERNAL_HUMAN_APPROVAL_DECISION_PACKET_READY",
                "decision_options": [
                    "APPROVE_LOCAL_RC",
                    "REQUEST_CHANGES",
                    "REFUSE_RELEASE_CANDIDATE",
                ],
                "decision_packet_authorized": True,
                "default_decision": "NO_RELEASE_WITHOUT_HUMAN_APPROVAL",
                "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
                "source_bound": True,
                "synthetic_dry_run_evidence": True,
                "synthetic_inputs_processed": 3,
                "draft_dossiers_written": 3,
                "dry_run_receipts_written": 3,
                "human_gate_checks_written": 3,
                "human_gates_preserved": True,
                "human_approval_required": True,
                "human_approval_state": "NEEDS_YOU",
                "local_release_candidate_claim_authorized": True,
                "release_candidate_packaging_authorized": True,
                "release_approved": False,
                "release_refused": False,
                "changes_requested": False,
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
        )
        + "\n"
    )


def test_t21_approves_local_rc_only_without_external_authority(tmp_path: Path) -> None:
    t20_path = tmp_path / "t20.json"
    out = tmp_path / "t21.json"
    _write_t20(t20_path)

    receipt = apply_t21_human_decision(
        t20_receipt_path=t20_path,
        human_decision="APPROVE_LOCAL_RC",
        output_path=out,
    )

    assert receipt.status == T21_HUMAN_DECISION_APPLICATION_READY_TOKEN
    assert receipt.allowed_claim_tier == "T21_HUMAN_APPROVED_LOCAL_RC_ONLY"
    assert receipt.human_decision_applied == "APPROVE_LOCAL_RC"
    assert receipt.local_rc_approved is True
    assert receipt.release_approved is True
    assert receipt.changes_requested is False
    assert receipt.release_refused is False
    assert receipt.actual_product_execution_authorized is False
    assert receipt.external_deployment_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert receipt.product_capability_execution_authorized is False
    assert json.loads(out.read_text())["status"] == T21_HUMAN_DECISION_APPLICATION_READY_TOKEN


def test_t21_request_changes_keeps_release_unapproved(tmp_path: Path) -> None:
    t20_path = tmp_path / "t20.json"
    out = tmp_path / "t21.json"
    _write_t20(t20_path)

    receipt = apply_t21_human_decision(
        t20_receipt_path=t20_path,
        human_decision="REQUEST_CHANGES",
        output_path=out,
    )

    assert receipt.status == T21_HUMAN_DECISION_APPLICATION_READY_TOKEN
    assert receipt.allowed_claim_tier == "T21_CHANGES_REQUESTED"
    assert receipt.local_rc_approved is False
    assert receipt.release_approved is False
    assert receipt.changes_requested is True
    assert receipt.release_refused is False
    assert receipt.external_deployment_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_t21_refuse_release_candidate_keeps_release_locked(tmp_path: Path) -> None:
    t20_path = tmp_path / "t20.json"
    out = tmp_path / "t21.json"
    _write_t20(t20_path)

    receipt = apply_t21_human_decision(
        t20_receipt_path=t20_path,
        human_decision="REFUSE_RELEASE_CANDIDATE",
        output_path=out,
    )

    assert receipt.status == T21_HUMAN_DECISION_APPLICATION_READY_TOKEN
    assert receipt.allowed_claim_tier == "T21_RELEASE_CANDIDATE_REFUSED"
    assert receipt.local_rc_approved is False
    assert receipt.release_approved is False
    assert receipt.changes_requested is False
    assert receipt.release_refused is True
    assert receipt.external_use_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_t21_rejects_invalid_decision(tmp_path: Path) -> None:
    t20_path = tmp_path / "t20.json"
    out = tmp_path / "t21.json"
    _write_t20(t20_path)

    receipt = apply_t21_human_decision(
        t20_receipt_path=t20_path,
        human_decision="SHIP_IT_TO_THE_WORLD",
        output_path=out,
    )

    assert receipt.status == "DIO_METAMORPHIC_ADAPTATION_T21_HUMAN_DECISION_APPLICATION_REFUSED"
    assert receipt.allowed_claim_tier == "T21_REFUSED_INVALID_OR_UNBOUND_HUMAN_DECISION"
    assert receipt.local_rc_approved is False
    assert receipt.release_approved is False
    assert receipt.actual_product_execution_authorized is False
    assert receipt.external_deployment_authorized is False
    assert receipt.authority_expansion_authorized is False
