from __future__ import annotations

from scripts.run_evidence_review_profile_pilot_checkpoint import _explicit_state_contract_satisfied


def test_checkpoint_requires_every_explicit_review_state() -> None:
    expected = {"CONTESTED", "PARTIAL"}
    assert _explicit_state_contract_satisfied(expected, {"CONTESTED", "PARTIAL"}) is True
    assert _explicit_state_contract_satisfied(expected, {"CONTESTED"}) is False
    assert _explicit_state_contract_satisfied(expected, {"PARTIAL"}) is False
    assert _explicit_state_contract_satisfied(expected, set()) is False


def test_checkpoint_refuses_empty_explicit_state_contract() -> None:
    assert _explicit_state_contract_satisfied(set(), {"CONTESTED"}) is False
