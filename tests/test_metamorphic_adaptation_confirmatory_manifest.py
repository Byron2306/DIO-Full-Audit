import json
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.confirmatory_manifest import (
    MANIFEST_VERSION,
    build_confirmatory_manifest,
    write_confirmatory_manifest,
)


def test_confirmatory_manifest_binds_commit_config_and_dry_run_status(tmp_path):
    manifest = build_confirmatory_manifest(run_output=tmp_path / "run-output")

    assert manifest.manifest_version == MANIFEST_VERSION
    assert manifest.run_id.startswith("dio-adapt-")
    assert manifest.branch
    assert manifest.commit
    assert manifest.config_path == "experiments/metamorphic_adaptation/config/native_bindings.v1.json"
    assert len(manifest.config_sha256) == 64
    assert manifest.native_binding_version == "DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1"
    assert manifest.dry_run_status == "NATIVE_DRY_RUN_VALIDATED"
    assert manifest.adaptation_commands >= 3
    assert manifest.transfer_commands >= 1
    assert manifest.authority_invariant == "AUTHORITY_BEFORE_EQUALS_AUTHORITY_AFTER"


def test_confirmatory_manifest_run_id_is_stable_for_same_commit_and_config(tmp_path):
    first = build_confirmatory_manifest(run_output=tmp_path / "one")
    second = build_confirmatory_manifest(run_output=tmp_path / "two")

    assert first.run_id == second.run_id
    assert first.config_sha256 == second.config_sha256
    assert first.commit == second.commit


def test_confirmatory_manifest_can_be_written_as_json(tmp_path):
    output = tmp_path / "manifest.json"

    manifest = write_confirmatory_manifest(output, run_output=tmp_path / "run-output")

    data = json.loads(output.read_text())
    assert data == asdict(manifest)
    assert data["manifest_version"] == MANIFEST_VERSION
    assert data["dry_run_status"] == "NATIVE_DRY_RUN_VALIDATED"


def test_confirmatory_manifest_terminal_policy_blocks_overclaiming(tmp_path):
    manifest = build_confirmatory_manifest(run_output=tmp_path / "run-output")

    policy = manifest.terminal_claim_policy.lower()

    assert "no adaptive-composition claim" in policy
    assert "frozen-code custody" in policy
    assert "blind evaluation" in policy
    assert "authority invariance" in policy
