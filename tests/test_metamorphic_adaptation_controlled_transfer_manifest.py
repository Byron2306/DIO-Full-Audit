import json
from dataclasses import asdict

from experiments.metamorphic_adaptation.controlled_transfer_manifest import (
    CONTROLLED_TRANSFER_MANIFEST_READY_TOKEN,
    CONTROLLED_TRANSFER_MANIFEST_VERSION,
    build_controlled_transfer_manifest,
    write_controlled_transfer_manifest,
)


def _write_readiness_digest(path, *, ready=True, adaptive_claim=False, world_claim=False):
    path.write_text(json.dumps({
        "status": "DIO_METAMORPHIC_ADAPTATION_NATIVE_READINESS_DIGEST_READY",
        "ready_for_controlled_transfer_run": ready,
        "adaptive_claim_authorized": adaptive_claim,
        "commercial_or_world_first_claim_authorized": world_claim,
    }, indent=2, sort_keys=True))


def test_controlled_transfer_manifest_authorizes_staging_from_clean_readiness_digest(tmp_path):
    readiness = tmp_path / "native_readiness_digest.json"
    _write_readiness_digest(readiness)

    manifest = build_controlled_transfer_manifest(
        readiness_digest_path=readiness,
        encounter_count=5,
    )

    assert manifest.manifest_version == CONTROLLED_TRANSFER_MANIFEST_VERSION
    assert manifest.status == CONTROLLED_TRANSFER_MANIFEST_READY_TOKEN
    assert manifest.transfer_run_authorized is True
    assert manifest.execute_by_default is False
    assert manifest.adaptive_claim_authorized is False
    assert manifest.commercial_or_world_first_claim_authorized is False
    assert manifest.encounter_count == 5
    assert len(manifest.arms) == 5


def test_controlled_transfer_manifest_refuses_when_readiness_digest_not_ready(tmp_path):
    readiness = tmp_path / "native_readiness_digest.json"
    _write_readiness_digest(readiness, ready=False)

    manifest = build_controlled_transfer_manifest(readiness_digest_path=readiness)

    assert manifest.transfer_run_authorized is False
    assert manifest.execute_by_default is False


def test_controlled_transfer_manifest_refuses_if_upstream_claims_are_authorized(tmp_path):
    readiness = tmp_path / "native_readiness_digest.json"
    _write_readiness_digest(readiness, adaptive_claim=True, world_claim=True)

    manifest = build_controlled_transfer_manifest(readiness_digest_path=readiness)

    assert manifest.transfer_run_authorized is False
    assert manifest.adaptive_claim_authorized is False
    assert manifest.commercial_or_world_first_claim_authorized is False


def test_controlled_transfer_manifest_requires_blind_and_factorial_evidence(tmp_path):
    readiness = tmp_path / "native_readiness_digest.json"
    _write_readiness_digest(readiness)

    manifest = build_controlled_transfer_manifest(readiness_digest_path=readiness)

    assert manifest.frozen_input_required is True
    assert manifest.blind_evaluation_required is True
    assert manifest.factorial_analysis_required is True
    assert "blind_evaluation_receipt.json" in manifest.output_artifacts
    assert "factorial_analysis_receipt.json" in manifest.output_artifacts
    assert "transfer_claim_gate.json" in manifest.output_artifacts


def test_controlled_transfer_manifest_writes_json_and_hashes_readiness_digest(tmp_path):
    readiness = tmp_path / "native_readiness_digest.json"
    output = tmp_path / "controlled_transfer_manifest.json"
    _write_readiness_digest(readiness)

    manifest = write_controlled_transfer_manifest(
        readiness_digest_path=readiness,
        output_path=output,
        encounter_count=7,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(manifest)))
    assert data["encounter_count"] == 7
    assert len(data["readiness_digest_sha256"]) == 64


def test_controlled_transfer_manifest_boundary_blocks_overclaiming(tmp_path):
    readiness = tmp_path / "native_readiness_digest.json"
    _write_readiness_digest(readiness)

    manifest = build_controlled_transfer_manifest(readiness_digest_path=readiness)

    boundary = manifest.boundary.lower()

    assert "staging of a controlled transfer run only" in boundary
    assert "does not execute" in boundary
    assert "does not authorize" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary
