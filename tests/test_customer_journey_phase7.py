from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from adapters.vamp.snapshot_pipeline import build_snapshot
from presence_core.organ_adapter_gauntlet import (
    ORGAN_FAMILIES,
    NEEDS_BINDING,
    NEEDS_HOST,
    REFUSE,
    VERIFIED_NATIVE,
    inspect_family,
    phase7_preflight,
    seal_native_execution,
    validate_execution_evidence,
    execute_verified_family,
)
from tests.test_vamp_snapshot_adapter import create_fixture_database


ROOT = Path(__file__).resolve().parents[1]
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
        assert binding["execution_class"] in {"native", "external_repo", "host_bound", "unbound"}
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


def test_seal_native_execution_hashes_current_artifact_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "snapshot.json"
    artifact.write_bytes(b'{"fresh":"artifact"}\n')
    evidence = seal_native_execution(
        "vamp_snapshot",
        fulfilment_request_sha256="a" * 64,
        execution_profile_sha256="b" * 64,
        artifacts=[{"artifact_id": "snapshot-json", "kind": "application/json", "path": artifact}],
        evidence_refs=["native-run:vamp-snapshot"],
    )
    assert evidence["artifacts"][0]["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert evidence["artifacts"][0]["release_state"] == "HELD"
    assert evidence["authority_created"] is False
    verdict = validate_execution_evidence(
        "vamp_snapshot",
        evidence,
        expected_request_sha256="a" * 64,
        expected_profile_sha256="b" * 64,
    )
    assert verdict["verdict"] == VERIFIED_NATIVE


def test_seal_native_execution_refuses_non_native_family_and_missing_files(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="not a permitted native execution binding"):
        seal_native_execution(
            "sophia_review",
            fulfilment_request_sha256="a" * 64,
            execution_profile_sha256="b" * 64,
            artifacts=[{"artifact_id": "evidence", "kind": "application/json", "path": missing}],
            evidence_refs=["run:evidex"],
        )
    with pytest.raises(FileNotFoundError):
        seal_native_execution(
            "vamp_snapshot",
            fulfilment_request_sha256="a" * 64,
            execution_profile_sha256="b" * 64,
            artifacts=[{"artifact_id": "snapshot", "kind": "application/json", "path": missing}],
            evidence_refs=["run:vamp"],
        )


def test_real_vamp_pipeline_can_be_sealed_as_current_phase7_execution(tmp_path: Path) -> None:
    database = tmp_path / "progress.db"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    create_fixture_database(database, evidence_dir)
    request = {
        "schema": "dio.vamp_snapshot_request.v1",
        "job_id": "PHASE7-VAMP-001",
        "profile_path": str(ROOT / "config" / "vamp_profiles" / "nwu_academic_v1.json"),
        "source": {"kind": "vamp_sqlite", "database_path": str(database), "staff_id": "TEST", "year": 2026},
        "review": {"months": ["2026-01"]},
        "privacy_mode": "redacted_demo",
        "consents": {
            "evidence_owner_authorized": True,
            "performance_data_processing_approved": True,
            "human_review_terms_accepted": True,
        },
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    output = build_snapshot(request_path, tmp_path / "output", run_evidex=False)
    snapshot_path = output / "VAMP_SNAPSHOT.json"
    zip_path = output / "PHASE7-VAMP-001_VAMP_EVIDENCE_SNAPSHOT.zip"
    evidence = seal_native_execution(
        "vamp_snapshot",
        fulfilment_request_sha256="1" * 64,
        execution_profile_sha256="2" * 64,
        artifacts=[
            {"artifact_id": "vamp-snapshot-json", "kind": "application/json", "path": snapshot_path},
            {"artifact_id": "vamp-snapshot-pack", "kind": "application/zip", "path": zip_path},
        ],
        evidence_refs=["phase7-native:vamp_snapshot"],
    )
    verdict = validate_execution_evidence(
        "vamp_snapshot",
        evidence,
        expected_request_sha256="1" * 64,
        expected_profile_sha256="2" * 64,
    )
    assert verdict["verdict"] == VERIFIED_NATIVE
    assert all(item["release_state"] == "HELD" for item in evidence["artifacts"])


def test_execute_verified_family_binds_real_phase4_request_and_normalizes_adapter_result(tmp_path: Path) -> None:
    from presence_core.fulfilment_contract import build_fulfilment_request, dispatch_fulfilment
    from tests.test_customer_journey_phase4 import _eligible_case, _profile

    case = _eligible_case(tmp_path, product_id="VAMP Performance")
    profile = _profile("VAMP Performance", adapter_id="dio.organ.vamp_snapshot")
    # Phase 7 owns adapter version 1. Re-project the fixture with the exact binding version
    # rather than mutating a signed execution profile.
    from presence_core.fulfilment_contract import project_execution_profile
    compiled = {
        "schema": "dio.compiled_product.v1",
        "compiler_version": "1.1.0",
        "product_id": "vamp-performance",
        "name": "VAMP Performance",
        "composition_fingerprint": "sha256:" + "1" * 64,
        "compilation_fingerprint": "sha256:" + "2" * 64,
        "capability_plan": [{
            "capability_id": "vamp.snapshot",
            "required": True,
            "execution_required": True,
            "resolution_state": "RESOLVED",
            "provider": {
                "provider_id": "vamp-snapshot",
                "provider_kind": "local",
                "ref": "adapters/vamp/snapshot_pipeline.py",
                "execution_capable": True,
                "product_scope": ["VAMP Performance"],
            },
            "reason": "Phase 7 verified family",
        }],
        "gates": {"execution": {"state": "NEEDS_YOU", "reason": "explicit Journey invocation"}},
        "output_plan": {"schema": "dio.compiled_output_plan.v1", "outputs": [{"kind": "evidence_pack"}]},
    }
    profile = project_execution_profile(
        compiled,
        adapter_id="dio.organ.vamp_snapshot",
        adapter_version=ORGAN_FAMILIES["vamp_snapshot"]["adapter_version"],
    )
    request = build_fulfilment_request(tmp_path, case["case_id"], profile)

    artifact = tmp_path / "vamp-current.json"
    artifact.write_text('{"current":"phase7"}\n', encoding="utf-8")

    def runner(*, family, binding, request, execution_profile):
        assert family == "vamp_snapshot"
        assert binding["adapter_id"] == request["adapter_id"]
        return seal_native_execution(
            family,
            fulfilment_request_sha256=request["fulfilment_request_sha256"],
            execution_profile_sha256=execution_profile["execution_profile_sha256"],
            artifacts=[{
                "artifact_id": "vamp-current",
                "kind": "application/json",
                "path": artifact,
            }],
            evidence_refs=["phase7:request-bound:vamp"],
        )

    def adapter(adapter_request: dict, adapter_profile: dict) -> dict:
        return execute_verified_family(
            "vamp_snapshot",
            request=adapter_request,
            execution_profile=adapter_profile,
            runner=runner,
        )

    result = dispatch_fulfilment(
        tmp_path,
        request,
        {"dio.organ.vamp_snapshot": adapter},
    )
    assert result["status"] == "COMPLETED"
    assert result["fulfilment_request_sha256"] == request["fulfilment_request_sha256"]
    assert result["execution_profile_sha256"] == profile["execution_profile_sha256"]
    assert result["artifacts"][0]["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert result["artifacts"][0]["release_state"] == "HELD"
    assert result["authority_created"] is False
