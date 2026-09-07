import json
from dataclasses import asdict

from experiments.metamorphic_adaptation.native_readiness_digest import (
    READINESS_DIGEST_READY_TOKEN,
    READINESS_DIGEST_VERSION,
    build_native_readiness_digest,
    write_native_readiness_digest,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _fixture_bundle(tmp_path, *, failed_runtime=0, adaptive_claim=False):
    preflight = tmp_path / "native_preflight_receipt.json"
    execution = tmp_path / "native_execution_receipt.json"
    compatibility = tmp_path / "native_compatibility_summary.json"

    _write(preflight, {
        "status": "DIO_METAMORPHIC_ADAPTATION_NATIVE_PREFLIGHT_READY",
    })

    _write(execution, {
        "status": "DIO_METAMORPHIC_ADAPTATION_NATIVE_EXECUTION_COMPLETED",
        "adaptive_claim_authorized": adaptive_claim,
    })

    _write(compatibility, {
        "status": "DIO_METAMORPHIC_ADAPTATION_NATIVE_COMPATIBILITY_CLASSIFIED",
        "compatible_fast": 10,
        "compatible_long_running": 2,
        "failed_contract": 0,
        "failed_dependency": 0,
        "failed_runtime": failed_runtime,
        "adaptive_claim_authorized": adaptive_claim,
    })

    return preflight, execution, compatibility


def test_readiness_digest_marks_clean_compatibility_ready_for_transfer(tmp_path):
    preflight, execution, compatibility = _fixture_bundle(tmp_path)

    digest = build_native_readiness_digest(
        preflight_receipt_path=preflight,
        execution_receipt_path=execution,
        compatibility_summary_path=compatibility,
    )

    assert digest.digest_version == READINESS_DIGEST_VERSION
    assert digest.status == READINESS_DIGEST_READY_TOKEN
    assert digest.compatible_fast == 10
    assert digest.compatible_long_running == 2
    assert digest.failed_runtime == 0
    assert digest.ready_for_controlled_transfer_run is True
    assert digest.adaptive_claim_authorized is False
    assert digest.commercial_or_world_first_claim_authorized is False


def test_readiness_digest_refuses_transfer_ready_when_failures_exist(tmp_path):
    preflight, execution, compatibility = _fixture_bundle(tmp_path, failed_runtime=1)

    digest = build_native_readiness_digest(
        preflight_receipt_path=preflight,
        execution_receipt_path=execution,
        compatibility_summary_path=compatibility,
    )

    assert digest.ready_for_controlled_transfer_run is False
    assert digest.failed_runtime == 1
    assert digest.adaptive_claim_authorized is False


def test_readiness_digest_refuses_if_any_upstream_claim_authorized(tmp_path):
    preflight, execution, compatibility = _fixture_bundle(tmp_path, adaptive_claim=True)

    digest = build_native_readiness_digest(
        preflight_receipt_path=preflight,
        execution_receipt_path=execution,
        compatibility_summary_path=compatibility,
    )

    assert digest.ready_for_controlled_transfer_run is False
    assert digest.adaptive_claim_authorized is False
    assert digest.commercial_or_world_first_claim_authorized is False


def test_readiness_digest_writes_json_and_hashes_sources(tmp_path):
    preflight, execution, compatibility = _fixture_bundle(tmp_path)
    output = tmp_path / "native_readiness_digest.json"

    digest = write_native_readiness_digest(
        preflight_receipt_path=preflight,
        execution_receipt_path=execution,
        compatibility_summary_path=compatibility,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(digest)))
    assert len(data["preflight_sha256"]) == 64
    assert len(data["execution_receipt_sha256"]) == 64
    assert len(data["compatibility_sha256"]) == 64


def test_readiness_digest_boundary_blocks_overclaiming(tmp_path):
    preflight, execution, compatibility = _fixture_bundle(tmp_path)

    digest = build_native_readiness_digest(
        preflight_receipt_path=preflight,
        execution_receipt_path=execution,
        compatibility_summary_path=compatibility,
    )

    boundary = digest.boundary.lower()

    assert "controlled transfer run" in boundary
    assert "does not authorize" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary
