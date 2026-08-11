from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from assurance import (
    AssuranceError,
    assess_continuous_assurance,
    compare_twin_snapshots,
    validate_assurance_receipt,
)
from twin import build_evidence_authority_twin

T0 = "2026-08-11T20:00:00+00:00"
T1 = "2026-08-11T21:00:00+00:00"
T2 = "2026-08-12T21:00:00+00:00"
EXPIRY = "2026-08-12T20:30:00+00:00"


def sample_case(*, claim_state: str = "SUPPORTED", requirement_state: str = "satisfied", action_target: str = "draft-A", event_ref: str = "composition://COMPR-001") -> dict:
    return {
        "schema": "dio.governed_case.v2",
        "case_id": "CASE-ASSURE-001",
        "updated_at": T0,
        "scope": {"world_state_ref": "world://za/current"},
        "evidence": [
            {
                "evidence_id": "EVID-1",
                "freshness_state": "current",
                "trust_state": "trusted_for_review",
                "expires_at": EXPIRY,
                "source_ref": "source://governed",
            }
        ],
        "claims": [
            {
                "claim_id": "CLAIM-1",
                "lineage_id": "LINEAGE-1",
                "statement": "The governed action is currently justified.",
                "epistemic_state": claim_state,
            }
        ],
        "requirements": [
            {
                "requirement_id": "REQ-1",
                "statement": "Current evidence and authority must remain valid.",
                "state": requirement_state,
                "expires_at": EXPIRY,
            }
        ],
        "actions": [
            {
                "action_id": "ACTION-1",
                "action_type": "outlook_send",
                "risk_tier": "external",
                "target": action_target,
            }
        ],
        "event_refs": [event_ref],
    }


def authority_rows(*, expires_at: str = EXPIRY) -> list[dict]:
    return [{
        "schema": "dio.authority.receipt.v1",
        "case_id": "CASE-ASSURE-001",
        "authority_receipt_id": "AUTH-1",
        "verdict": "ALLOW",
        "expires_at": expires_at,
    }]


def lease_rows(*, expires_at: str = EXPIRY, state: str = "active") -> list[dict]:
    return [{
        "schema": "dio.capability_lease.v1",
        "case_id": "CASE-ASSURE-001",
        "lease_id": "LEASE-1",
        "state": state,
        "used_count": 0,
        "maximum_uses": 1,
        "expires_at": expires_at,
    }]


def execution_rows(*, status: str = "executed") -> list[dict]:
    return [{
        "case_id": "CASE-ASSURE-001",
        "execution_receipt_id": "EXEC-1",
        "vertical_request_id": "VEXEC-1",
        "status": status,
    }]


def world_rows(*, expires_at: str = EXPIRY, state: str = "current") -> list[dict]:
    return [{
        "case_id": "CASE-ASSURE-001",
        "world_state_id": "WORLD-1",
        "state": state,
        "expires_at": expires_at,
    }]


def make_twin(
    *,
    observed_at: str = T0,
    case: dict | None = None,
    authority: list[dict] | None = None,
    leases: list[dict] | None = None,
    executions: list[dict] | None = None,
    world: list[dict] | None = None,
) -> dict:
    return build_evidence_authority_twin(
        cases=[case or sample_case()],
        authority_receipts=authority if authority is not None else authority_rows(),
        capability_leases=leases if leases is not None else lease_rows(),
        execution_receipts=executions if executions is not None else execution_rows(),
        world_state=world if world is not None else world_rows(),
        observed_at=observed_at,
    )


def categories(receipt: dict) -> set[str]:
    return {row["category"] for row in receipt["findings"]}


def test_continuous_assurance_config_schema_and_all_twin_layers() -> None:
    schema = json.loads(Path("schemas/dio_continuous_assurance.schema.json").read_text(encoding="utf-8"))
    payload = json.loads(Path("config/dio_continuous_assurance.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert len(payload["watch_layers"]) == 8
    assert payload["authority"]["continuous_assurance_has_authority"] is False
    assert payload["authority"]["continuous_assurance_can_execute"] is False


def test_same_snapshot_has_no_drift_and_does_not_rerun_loki() -> None:
    twin = make_twin()
    receipt = assess_continuous_assurance(twin, twin)
    assert receipt["finding_count"] == 0
    assert receipt["material_drift"] is False
    assert receipt["loki_rerun"] is False
    assert receipt["recommended_state"] == "ASSURED_NO_MATERIAL_DRIFT"


def test_time_advance_without_currency_change_is_not_material_drift() -> None:
    previous = make_twin(observed_at=T0)
    current = make_twin(observed_at=T1)
    receipt = assess_continuous_assurance(previous, current)
    assert receipt["finding_count"] == 0
    assert receipt["loki_rerun"] is False


def test_evidence_expiry_is_detected_as_needs_evidence() -> None:
    receipt = assess_continuous_assurance(make_twin(observed_at=T0), make_twin(observed_at=T2))
    finding = next(row for row in receipt["findings"] if row["category"] == "evidence_became_noncurrent")
    assert finding["response"] == "needs_evidence"
    assert finding["reopen_case"] is True
    assert finding["block_execution"] is False


def test_authority_expiry_is_critical_and_blocks_execution_recommendation() -> None:
    receipt = assess_continuous_assurance(make_twin(observed_at=T0), make_twin(observed_at=T2))
    finding = next(row for row in receipt["findings"] if row["category"] == "authority_became_noncurrent")
    assert finding["severity"] == "critical"
    assert finding["response"] == "needs_you"
    assert finding["block_execution"] is True
    assert "CASE-ASSURE-001" in receipt["block_execution_case_ids"]


def test_capability_expiry_is_critical() -> None:
    receipt = assess_continuous_assurance(make_twin(observed_at=T0), make_twin(observed_at=T2))
    assert "capability_became_noncurrent" in categories(receipt)
    assert receipt["recommended_state"] == "BLOCK_AND_REVIEW"


def test_world_expiry_triggers_review_and_reopen() -> None:
    receipt = assess_continuous_assurance(make_twin(observed_at=T0), make_twin(observed_at=T2))
    finding = next(row for row in receipt["findings"] if row["category"] == "world_state_became_noncurrent")
    assert finding["response"] == "review"
    assert finding["reopen_case"] is True


def test_claim_state_change_is_material_and_reopens_case() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, case=sample_case(claim_state="CONTESTED"))
    receipt = assess_continuous_assurance(previous, current)
    assert "claim_state_changed" in categories(receipt)
    assert "CASE-ASSURE-001" in receipt["reopen_case_ids"]


def test_requirement_regression_is_material() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, case=sample_case(requirement_state="evidence_needed"))
    receipt = assess_continuous_assurance(previous, current)
    finding = next(row for row in receipt["findings"] if row["category"] == "requirement_state_changed")
    assert finding["response"] == "needs_evidence"


def test_action_payload_drift_is_critical() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, case=sample_case(action_target="draft-B"))
    receipt = assess_continuous_assurance(previous, current)
    finding = next(row for row in receipt["findings"] if row["category"] == "action_payload_changed")
    assert finding["severity"] == "critical"
    assert finding["block_execution"] is True


def test_execution_receipt_change_is_critical() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, executions=execution_rows(status="failed"))
    receipt = assess_continuous_assurance(previous, current)
    assert "receipt_chain_changed" in categories(receipt)
    assert receipt["critical_finding_count"] >= 1


def test_missing_receipt_is_critical() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, executions=[])
    receipt = assess_continuous_assurance(previous, current)
    assert "receipt_missing" in categories(receipt)


def test_material_drift_reruns_loki_against_exact_current_twin() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, case=sample_case(claim_state="CONTESTED"))
    receipt = assess_continuous_assurance(previous, current)
    assert receipt["loki_rerun"] is True
    assert receipt["loki_mirror_maze_id"].startswith("LOKI-MAZE-")
    assert receipt["current_twin_fingerprint"] == current["fingerprint"]


def test_loki_rerun_preserves_all_eight_mirror_divergence_classes_when_layers_exist() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, case=sample_case(claim_state="CONTESTED"))
    receipt = assess_continuous_assurance(previous, current)
    assert set(receipt["mirror_divergence_categories"]) == {
        "action_payload_drift",
        "authority_expiry",
        "claim_contradiction",
        "lease_revocation",
        "receipt_fork",
        "requirement_regression",
        "stale_evidence",
        "world_state_drift",
    }


def test_assurance_receipt_is_deterministic_for_same_twin_pair() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, case=sample_case(claim_state="CONTESTED"))
    first = assess_continuous_assurance(previous, current)
    second = assess_continuous_assurance(previous, current)
    assert first["assurance_receipt_id"] == second["assurance_receipt_id"]
    assert first["fingerprint"] == second["fingerprint"]


def test_tampered_assurance_receipt_is_refused() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, case=sample_case(claim_state="CONTESTED"))
    receipt = assess_continuous_assurance(previous, current)
    forged = copy.deepcopy(receipt)
    forged["authority_created"] = True
    with pytest.raises(AssuranceError, match="authority or execution"):
        validate_assurance_receipt(forged, previous_twin=previous, current_twin=current)


def test_findings_never_self_apply_authority_or_execution() -> None:
    receipt = assess_continuous_assurance(make_twin(observed_at=T0), make_twin(observed_at=T2))
    for finding in receipt["findings"]:
        assert finding["authority_effect"] is False
        assert finding["execution_effect"] is False
        assert finding["synthetic"] is False
    assert receipt["authority_created"] is False
    assert receipt["execution_created"] is False


def test_backwards_time_is_refused() -> None:
    with pytest.raises(AssuranceError, match="older than the previous Twin"):
        compare_twin_snapshots(make_twin(observed_at=T1), make_twin(observed_at=T0))


def test_synthetic_injection_into_canonical_current_twin_is_refused() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1)
    forged = copy.deepcopy(current)
    forged["layers"]["claim_state"][0]["synthetic"] = True
    with pytest.raises(AssuranceError, match="synthetic state"):
        compare_twin_snapshots(previous, forged)


def test_continuous_assurance_remains_below_valinor_and_arda_boundaries() -> None:
    previous = make_twin()
    current = make_twin(observed_at=T1, case=sample_case(claim_state="CONTESTED"))
    receipt = assess_continuous_assurance(previous, current)
    laws = receipt["laws"]
    assert laws["continuous_assurance_has_no_authority"] is True
    assert laws["continuous_assurance_never_executes"] is True
    assert laws["valinor_remains_sole_kernel_authority"] is True
    assert laws["arda_remains_execution_identity_only"] is True
