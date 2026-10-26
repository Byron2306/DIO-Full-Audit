from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from twin import (
    TwinError,
    build_evidence_authority_twin,
    build_loki_mirror_maze,
    compare_canonical_to_mirror,
    current_twin_view,
    validate_loki_mirror,
    validate_twin,
)
from twin.loki_mirror import LOKI_SOURCE

OBSERVED = "2026-08-11T20:00:00+00:00"
FUTURE = "2026-08-12T20:00:00+00:00"
PAST = "2026-08-10T20:00:00+00:00"


def sample_case() -> dict:
    return {
        "schema": "dio.governed_case.v2",
        "case_id": "CASE-TWIN-001",
        "updated_at": OBSERVED,
        "scope": {"world_state_ref": "world://za/current"},
        "evidence": [
            {
                "evidence_id": "EVID-CURRENT",
                "freshness_state": "current",
                "trust_state": "trusted_for_review",
                "expires_at": FUTURE,
                "source_ref": "source://current",
            },
            {
                "evidence_id": "EVID-STALE",
                "freshness_state": "stale",
                "trust_state": "trusted_for_review",
                "expires_at": FUTURE,
                "source_ref": "source://old",
            },
        ],
        "claims": [
            {
                "claim_id": "CLAIM-1",
                "lineage_id": "LINEAGE-1",
                "statement": "A governed action has current evidence.",
                "epistemic_state": "SUPPORTED",
            }
        ],
        "requirements": [
            {
                "requirement_id": "REQ-1",
                "statement": "Current authority must exist.",
                "state": "satisfied",
                "expires_at": FUTURE,
            }
        ],
        "actions": [
            {
                "action_id": "ACTION-1",
                "action_type": "outlook_send",
                "risk_tier": "external",
            }
        ],
        "event_refs": ["composition://COMPR-001"],
    }


def authority_rows() -> list[dict]:
    return [
        {
            "schema": "dio.authority.receipt.v1",
            "case_id": "CASE-TWIN-001",
            "authority_receipt_id": "AUTH-CURRENT",
            "verdict": "ALLOW",
            "expires_at": FUTURE,
        },
        {
            "schema": "dio.authority.receipt.v1",
            "case_id": "CASE-TWIN-001",
            "authority_receipt_id": "AUTH-EXPIRED",
            "verdict": "ALLOW",
            "expires_at": PAST,
        },
    ]


def lease_rows() -> list[dict]:
    return [
        {
            "schema": "dio.capability_lease.v1",
            "case_id": "CASE-TWIN-001",
            "lease_id": "LEASE-CURRENT",
            "state": "active",
            "used_count": 0,
            "maximum_uses": 1,
            "expires_at": FUTURE,
        },
        {
            "schema": "dio.capability_lease.v1",
            "case_id": "CASE-TWIN-001",
            "lease_id": "LEASE-REVOKED",
            "state": "revoked",
            "used_count": 0,
            "maximum_uses": 1,
            "expires_at": FUTURE,
        },
    ]


def make_twin() -> dict:
    return build_evidence_authority_twin(
        cases=[sample_case()],
        authority_receipts=authority_rows(),
        capability_leases=lease_rows(),
        execution_receipts=[
            {
                "case_id": "CASE-TWIN-001",
                "execution_receipt_id": "EXEC-1",
                "vertical_request_id": "VEXEC-1",
                "status": "executed",
            }
        ],
        world_state=[
            {
                "case_id": "CASE-TWIN-001",
                "world_state_id": "WORLD-1",
                "state": "current",
                "expires_at": FUTURE,
            }
        ],
        observed_at=OBSERVED,
    )


def test_twin_config_schema_and_all_eight_layers() -> None:
    schema = json.loads(Path("schemas/dio_evidence_authority_twin.schema.json").read_text(encoding="utf-8"))
    payload = json.loads(Path("config/dio_evidence_authority_twin.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert set(payload["layers"]) == {
        "world_state", "evidence_state", "claim_state", "requirement_state",
        "authority_state", "capability_state", "action_state", "receipt_state",
    }


def test_twin_is_deterministic_for_same_state_and_observation_time() -> None:
    first = make_twin()
    second = make_twin()
    assert first["twin_id"] == second["twin_id"]
    assert first["fingerprint"] == second["fingerprint"]


def test_stale_evidence_is_preserved_but_not_current() -> None:
    twin = make_twin()
    rows = {row["source_id"]: row for row in twin["layers"]["evidence_state"]}
    assert rows["EVID-STALE"]["current"] is False
    assert rows["EVID-CURRENT"]["current"] is True


def test_expired_authority_is_preserved_but_not_current() -> None:
    twin = make_twin()
    rows = {row["source_id"]: row for row in twin["layers"]["authority_state"]}
    assert rows["AUTH-EXPIRED"]["current"] is False
    assert rows["AUTH-CURRENT"]["current"] is True


def test_revoked_lease_is_preserved_but_not_current() -> None:
    twin = make_twin()
    rows = {row["source_id"]: row for row in twin["layers"]["capability_state"]}
    assert rows["LEASE-REVOKED"]["current"] is False
    assert rows["LEASE-CURRENT"]["current"] is True


def test_current_view_never_resurrects_historical_state() -> None:
    view = current_twin_view(make_twin())
    evidence_ids = {row["source_id"] for row in view["layers"]["evidence_state"]}
    authority_ids = {row["source_id"] for row in view["layers"]["authority_state"]}
    lease_ids = {row["source_id"] for row in view["layers"]["capability_state"]}
    assert "EVID-STALE" not in evidence_ids
    assert "AUTH-EXPIRED" not in authority_ids
    assert "LEASE-REVOKED" not in lease_ids


def test_canonical_twin_rejects_synthetic_injection() -> None:
    twin = make_twin()
    forged = copy.deepcopy(twin)
    forged["layers"]["claim_state"][0]["synthetic"] = True
    with pytest.raises(TwinError, match="synthetic state"):
        validate_twin(forged)


def test_loki_is_pinned_to_canonical_metatron_source() -> None:
    assert LOKI_SOURCE["repository"] == "Byron2306/Metatron"
    assert LOKI_SOURCE["commit"] == "532f8f4d22568c3812352150da7c7baf923d76e6"
    assert LOKI_SOURCE["triune_loki"] == "backend/triune/loki_ai.py"
    assert LOKI_SOURCE["mirror_maze"] == "backend/services/mystique_maze.py"


def test_loki_mirror_is_deterministic_for_same_canonical_twin() -> None:
    twin = make_twin()
    first = build_loki_mirror_maze(twin)
    second = build_loki_mirror_maze(twin)
    assert first["mirror_maze_id"] == second["mirror_maze_id"]
    assert first["fingerprint"] == second["fingerprint"]


def test_loki_mirror_attacks_all_available_twin_layers() -> None:
    maze = build_loki_mirror_maze(make_twin())
    categories = {row["category"] for row in maze["nodes"]}
    assert {
        "stale_evidence",
        "claim_contradiction",
        "requirement_regression",
        "authority_expiry",
        "lease_revocation",
        "action_payload_drift",
        "receipt_fork",
        "world_state_drift",
    }.issubset(categories)


def test_every_loki_node_is_permanently_synthetic_and_non_authoritative() -> None:
    maze = build_loki_mirror_maze(make_twin())
    for row in maze["nodes"]:
        assert row["synthetic"] is True
        assert row["canonical_effect"] is False
        assert row["authority_effect"] is False


def test_loki_mirror_cannot_mutate_canonical_twin() -> None:
    twin = make_twin()
    before = copy.deepcopy(twin)
    maze = build_loki_mirror_maze(twin)
    report = compare_canonical_to_mirror(twin, maze)
    assert twin == before
    assert report["canonical_mutated"] is False
    assert report["authority_created"] is False
    assert report["execution_created"] is False


def test_loki_synthetic_escape_attempt_is_refused() -> None:
    twin = make_twin()
    maze = build_loki_mirror_maze(twin)
    forged = copy.deepcopy(maze)
    forged["nodes"][0]["authority_effect"] = True
    with pytest.raises(TwinError, match="escape synthetic containment"):
        validate_loki_mirror(forged, twin=twin)


def test_loki_mirror_is_bound_to_exact_twin_fingerprint() -> None:
    twin = make_twin()
    maze = build_loki_mirror_maze(twin)
    other = copy.deepcopy(twin)
    other["observed_at"] = "2026-08-11T20:01:00+00:00"
    # Build a genuine second twin rather than tampering the first one's hash.
    other = build_evidence_authority_twin(
        cases=[sample_case()],
        authority_receipts=authority_rows(),
        capability_leases=lease_rows(),
        observed_at="2026-08-11T20:01:00+00:00",
    )
    with pytest.raises(TwinError, match="not bound to this canonical twin"):
        validate_loki_mirror(maze, twin=other)


def test_receipt_fork_remains_a_hypothesis_not_a_receipt() -> None:
    maze = build_loki_mirror_maze(make_twin())
    fork = next(row for row in maze["nodes"] if row["category"] == "receipt_fork")
    assert fork["layer"] == "receipt_state"
    assert fork["mutation"]["synthetic_receipt_fork"] is True
    assert fork["canonical_effect"] is False


def test_world_drift_remains_synthetic_until_real_world_state_changes() -> None:
    maze = build_loki_mirror_maze(make_twin())
    drift = next(row for row in maze["nodes"] if row["category"] == "world_state_drift")
    assert drift["mutation"]["synthetic_world_drift"] is True
    assert drift["synthetic"] is True


def test_mirror_maze_has_branching_graph_and_valid_parent_links() -> None:
    maze = build_loki_mirror_maze(make_twin())
    ids = {row["mirror_node_id"] for row in maze["nodes"]}
    assert maze["tier"] in {"surface", "shallow", "deep", "labyrinth"}
    assert any(len(row["children"]) > 1 for row in maze["nodes"])
    for row in maze["nodes"]:
        if row["parent_id"]:
            assert row["parent_id"] in ids


def test_twin_and_loki_both_remain_below_valinor_authority() -> None:
    twin = make_twin()
    maze = build_loki_mirror_maze(twin)
    assert twin["laws"]["twin_has_no_authority"] is True
    assert twin["laws"]["valinor_remains_sole_kernel_authority"] is True
    assert maze["laws"]["mirror_never_mints_authority"] is True
    assert maze["laws"]["mirror_never_executes"] is True
