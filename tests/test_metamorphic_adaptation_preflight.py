import json
from pathlib import Path

from experiments.metamorphic_adaptation.preflight import (
    PREFLIGHT_READY_TOKEN,
    PREFLIGHT_VERSION,
    write_native_preflight_bundle,
)


def test_native_preflight_writes_manifest_dry_run_report_and_receipt(tmp_path):
    receipt = write_native_preflight_bundle(tmp_path / "preflight")

    receipt_path = tmp_path / "preflight" / "native_preflight_receipt.json"
    manifest_path = tmp_path / "preflight" / "confirmatory_manifest.json"
    dry_run_path = tmp_path / "preflight" / "native_dry_run_report.json"

    assert receipt_path.exists()
    assert manifest_path.exists()
    assert dry_run_path.exists()

    data = json.loads(receipt_path.read_text())

    assert data["preflight_version"] == PREFLIGHT_VERSION
    assert data["status"] == PREFLIGHT_READY_TOKEN
    assert data["manifest_sha256"] == receipt.manifest_sha256
    assert data["dry_run_report_sha256"] == receipt.dry_run_report_sha256
    assert data["full_native_execution_allowed"] is False


def test_native_preflight_manifest_remains_confirmatory_only(tmp_path):
    write_native_preflight_bundle(tmp_path / "preflight")

    manifest = json.loads((tmp_path / "preflight" / "confirmatory_manifest.json").read_text())

    assert manifest["manifest_version"] == "DIO_METAMORPHIC_ADAPTATION_CONFIRMATORY_MANIFEST_V1"
    assert manifest["dry_run_status"] == "NATIVE_DRY_RUN_VALIDATED"
    assert manifest["authority_invariant"] == "AUTHORITY_BEFORE_EQUALS_AUTHORITY_AFTER"


def test_native_preflight_dry_run_report_contains_bound_commands(tmp_path):
    write_native_preflight_bundle(tmp_path / "preflight")

    report = json.loads((tmp_path / "preflight" / "native_dry_run_report.json").read_text())

    assert report["status"] == "NATIVE_DRY_RUN_VALIDATED"
    assert report["command_checks"]

    labels = {check["label"] for check in report["command_checks"]}
    assert "media_incarnation_phase16_1" in labels
    assert "professional_task_gauntlet" in labels


def test_native_preflight_refuses_adaptive_claim(tmp_path):
    receipt = write_native_preflight_bundle(tmp_path / "preflight")

    boundary = receipt.refusal_boundary.lower()

    assert receipt.full_native_execution_allowed is False
    assert "does not execute adaptation episodes" in boundary
    assert "does not authorize an adaptive-composition claim" in boundary
