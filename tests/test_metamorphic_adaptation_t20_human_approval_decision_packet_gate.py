from __future__ import annotations

import json
from pathlib import Path

from experiments.metamorphic_adaptation.t20_human_approval_decision_packet_gate import (
    T20_HUMAN_APPROVAL_DECISION_PACKET_READY_TOKEN,
    build_t20_human_approval_decision_packet,
)


def _write_t19_receipt(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "DIO_METAMORPHIC_ADAPTATION_T19_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_READY",
                "gate_version": "DIO_METAMORPHIC_ADAPTATION_T19_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_GATE_V1",
                "allowed_claim_tier": "T19_INTERNAL_HUMAN_GATED_LOCAL_RELEASE_CANDIDATE_PACKAGING",
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
                "release_candidate_packaging_authorized": True,
                "local_release_candidate_claim_authorized": True,
                "external_deployment_authorized": False,
                "external_use_authorized": False,
                "actual_product_execution_authorized": False,
                "product_capability_execution_authorized": False,
                "commercial_validation_claim_authorized": False,
                "product_market_fit_claim_authorized": False,
                "autonomous_development_authorized": False,
                "authority_expansion_authorized": False,
                "world_first_claim_authorized": False,
                "publication_authorized": False,
                "spend_authorized": False,
                "fulfilment_authorized": False,
            }
        )
    )


def test_t20_packages_human_decision_surface_without_approving_release(tmp_path: Path) -> None:
    t19_path = tmp_path / "t19_receipt.json"
    output_path = tmp_path / "t20_decision_packet.json"
    _write_t19_receipt(t19_path)

    receipt = build_t20_human_approval_decision_packet(
        t19_receipt_path=t19_path,
        output_path=output_path,
    )

    assert receipt.status == T20_HUMAN_APPROVAL_DECISION_PACKET_READY_TOKEN
    assert receipt.allowed_claim_tier == "T20_INTERNAL_HUMAN_APPROVAL_DECISION_PACKET_READY"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.source_bound is True
    assert receipt.human_approval_required is True
    assert receipt.human_approval_state == "NEEDS_YOU"
    assert receipt.decision_options == [
        "APPROVE_LOCAL_RC",
        "REQUEST_CHANGES",
        "REFUSE_RELEASE_CANDIDATE",
    ]
    assert receipt.default_decision == "NO_RELEASE_WITHOUT_HUMAN_APPROVAL"
    assert receipt.decision_packet_authorized is True
    assert receipt.release_approved is False
    assert receipt.external_deployment_authorized is False
    assert receipt.actual_product_execution_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert output_path.exists()


def test_t20_refuses_when_t19_does_not_preserve_human_gate(tmp_path: Path) -> None:
    t19_path = tmp_path / "bad_t19_receipt.json"
    output_path = tmp_path / "refused.json"
    _write_t19_receipt(t19_path)
    data = json.loads(t19_path.read_text())
    data["human_approval_state"] = "APPROVED"
    t19_path.write_text(json.dumps(data))

    receipt = build_t20_human_approval_decision_packet(
        t19_receipt_path=t19_path,
        output_path=output_path,
    )

    assert receipt.status == "DIO_METAMORPHIC_ADAPTATION_T20_HUMAN_APPROVAL_DECISION_PACKET_REFUSED"
    assert receipt.decision_packet_authorized is False
    assert receipt.release_approved is False
    assert receipt.external_deployment_authorized is False
    assert receipt.authority_expansion_authorized is False
