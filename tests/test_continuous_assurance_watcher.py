from __future__ import annotations

import copy

import pytest

from assurance import AssuranceError, ContinuousAssuranceWatcher
from twin import build_evidence_authority_twin

T0 = "2026-08-11T20:00:00+00:00"
T1 = "2026-08-11T21:00:00+00:00"


def case(claim_state: str = "SUPPORTED") -> dict:
    return {
        "schema": "dio.governed_case.v2",
        "case_id": "CASE-WATCH-1",
        "updated_at": T0,
        "scope": {"world_state_ref": "world://watch"},
        "evidence": [],
        "claims": [{"claim_id": "CLAIM-1", "lineage_id": "LINEAGE-1", "statement": "watch", "epistemic_state": claim_state}],
        "requirements": [],
        "actions": [],
        "event_refs": [],
    }


def twin(observed_at: str, claim_state: str = "SUPPORTED") -> dict:
    return build_evidence_authority_twin(cases=[case(claim_state)], observed_at=observed_at)


def test_watcher_advances_only_after_valid_assurance_receipt() -> None:
    baseline = twin(T0)
    watcher = ContinuousAssuranceWatcher(baseline)
    next_twin = twin(T1, "CONTESTED")
    receipt = watcher.observe(next_twin)
    assert receipt["material_drift"] is True
    assert watcher.current_twin["twin_id"] == next_twin["twin_id"]
    assert watcher.state()["receipt_count"] == 1


def test_watcher_does_not_advance_on_invalid_snapshot() -> None:
    baseline = twin(T0)
    watcher = ContinuousAssuranceWatcher(baseline)
    forged = copy.deepcopy(twin(T1))
    forged["layers"]["claim_state"][0]["synthetic"] = True
    with pytest.raises(Exception):
        watcher.observe(forged)
    assert watcher.current_twin["twin_id"] == baseline["twin_id"]
    assert watcher.state()["receipt_count"] == 0


def test_watcher_state_has_no_authority_or_execution() -> None:
    watcher = ContinuousAssuranceWatcher(twin(T0))
    state = watcher.state()
    assert state["authority"] is False
    assert state["execution"] is False
