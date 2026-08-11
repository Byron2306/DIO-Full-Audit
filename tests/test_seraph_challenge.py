from __future__ import annotations

from pathlib import Path

from adapters.seraph.challenge import build_challenge_receipt, project_challenge_into_case
from products.governed_case import add_claim, new_case


def _case():
    case = new_case(
        product="dio_assurance",
        job_id="seraph-test",
        source={},
        source_path=Path("request.json"),
        evidence_inputs=[],
        expected_outputs=[],
        required_authorities=["human_operator"],
        intake_state="approved",
    )
    claim = add_claim(case, statement="The proposed action is safe to execute.")
    return case, claim


def test_clear_requires_complete_coverage_and_never_authorizes_execution() -> None:
    receipt = build_challenge_receipt(
        {"case_id": "CASE-1", "target_type": "case", "target_id": "CASE-1", "coverage_state": "complete", "findings": []}
    )
    assert receipt["verdict"] == "CLEAR"
    assert receipt["execution_authorized"] is False
    assert receipt["external_action_executed"] is False
    assert receipt["response_action_executed"] is False
    assert receipt["kernel_authority"] == "Valinor"


def test_incomplete_coverage_is_not_clear() -> None:
    receipt = build_challenge_receipt(
        {"case_id": "CASE-1", "target_type": "case", "target_id": "CASE-1", "coverage_state": "partial", "findings": []}
    )
    assert receipt["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert receipt["execution_authorized"] is False


def test_material_finding_contests_claim_and_projects_open_challenge() -> None:
    case, claim = _case()
    receipt = build_challenge_receipt(
        {
            "case_id": case["case_id"],
            "target_type": "claim",
            "target_id": claim["claim_id"],
            "coverage_state": "complete",
            "findings": [
                {
                    "kind": "contradiction",
                    "severity": "material",
                    "detail": "Observed evidence contradicts the safety claim.",
                }
            ],
        }
    )
    assert receipt["verdict"] == "CONTESTED"
    rows = project_challenge_into_case(case, receipt)
    assert len(rows) == 1
    assert rows[0]["raised_by"] == "seraph"
    assert rows[0]["state"] == "open"
    assert claim["epistemic_state"] == "CONTESTED"


def test_hostile_signal_still_has_no_response_authority() -> None:
    receipt = build_challenge_receipt(
        {
            "case_id": "CASE-1",
            "target_type": "action",
            "target_id": "ACTION-1",
            "coverage_state": "complete",
            "requested_action": "contain_endpoint",
            "findings": [
                {
                    "kind": "threat",
                    "severity": "blocking",
                    "hostile_signal": True,
                    "detail": "Machine-paced hostile behavior detected.",
                    "mitre_refs": ["T1059"],
                }
            ],
        }
    )
    assert receipt["verdict"] == "HOSTILE"
    assert receipt["response_action_requested"] == "contain_endpoint"
    assert receipt["response_action_executed"] is False
    assert receipt["execution_authorized"] is False
