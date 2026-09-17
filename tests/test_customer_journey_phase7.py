from __future__ import annotations

from pathlib import Path

import pytest

from presence_core.organ_adapter_gauntlet import (
    ORGAN_FAMILIES,
    NEEDS_BINDING,
    NEEDS_HOST,
    REFUSE,
    VERIFIED_NATIVE,
    inspect_family,
    phase7_preflight,
    validate_execution_evidence,
)


EXPECTED_FAMILIES = {
    "sophia_review",
    "evidex_evidence",
    "vamp_snapshot",
    "homs_assessment",
    "homs_learning",
    "document_studio",
    "nichefoundry_campaign",
    "obligation_assurance",
}


def test_phase7_registry_freezes_exactly_eight_representative_families() -> None:
    assert set(ORGAN_FAMILIES) == EXPECTED_FAMILIES
    assert len(ORGAN_FAMILIES) == 8
    for family_id, binding in ORGAN_FAMILIES.items():
        assert binding["family_id"] == family_id
        assert binding["representative_product"]
        assert binding["adapter_id"]
        assert binding["adapter_version"]
        assert binding["source_path"]
        assert binding["execution_class"] in {"native", "host_bound", "unbound"}
        assert binding["verdict"] in {VERIFIED_NATIVE, NEEDS_HOST, NEEDS_BINDING, REFUSE}
        assert binding["authority_created"] is False
        assert binding["external_send_authority"] is False


def test_preflight_never_counts_host_unavailable_or_unbound_as_verified(tmp_path: Path) -> None:
    report = phase7_preflight(repo_root=tmp_path, host_capabilities=set())
    assert report["schema"] == "dio.customer_journey.phase7_preflight.v1"
    assert report["family_count"] == 8
    assert report["verified_count"] == sum(
        1 for row in report["families"] if row["verdict"] == VERIFIED_NATIVE
    )
    assert all(
        row["verdict"] != VERIFIED_NATIVE
        for row in report["families"]
        if row["execution_class"] in {"host_bound", "unbound"}
    )
    assert report["phase8_unblocked"] is (report["verified_count"] == 8)


def test_inspect_family_refuses_unknown_family() -> None:
    with pytest.raises(ValueError, match="unknown Phase 7 organ family"):
        inspect_family("invented_product_family", repo_root=Path("."), host_capabilities=set())


def _evidence(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "dio.organ_adapter_execution_evidence.v1",
        "family_id": "vamp_snapshot",
        "adapter_id": "dio.organ.vamp_snapshot",
        "adapter_version": "1",
        "fulfilment_request_sha256": "a" * 64,
        "execution_profile_sha256": "b" * 64,
        "fresh_execution": True,
        "historical_specimen": False,
        "status": "COMPLETED",
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
        "artifacts": [
            {
                "artifact_id": "snapshot-json",
                "kind": "application/json",
                "sha256": "c" * 64,
                "release_state": "HELD",
            }
        ],
        "evidence_refs": ["native-run:vamp-snapshot"],
    }
    payload.update(overrides)
    return payload


def test_execution_evidence_requires_fresh_hash_bound_held_artifacts() -> None:
    result = validate_execution_evidence(
        "vamp_snapshot",
        _evidence(),
        expected_request_sha256="a" * 64,
        expected_profile_sha256="b" * 64,
    )
    assert result["verdict"] == VERIFIED_NATIVE
    assert result["authority_created"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        {"historical_specimen": True},
        {"fresh_execution": False},
        {"fulfilment_request_sha256": "d" * 64},
        {"execution_profile_sha256": "e" * 64},
        {"release_authority": True},
        {"external_send_authority": True},
        {"authority_created": True},
        {"status": "prepared_request_only"},
        {"artifacts": [{"artifact_id": "x", "kind": "text/plain", "sha256": "f" * 64, "release_state": "RELEASED"}]},
    ],
)
def test_execution_evidence_refuses_stale_unbound_or_authority_leaking_receipts(mutation: dict[str, object]) -> None:
    result = validate_execution_evidence(
        "vamp_snapshot",
        _evidence(**mutation),
        expected_request_sha256="a" * 64,
        expected_profile_sha256="b" * 64,
    )
    assert result["verdict"] == REFUSE
