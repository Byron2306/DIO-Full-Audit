import json
import subprocess
import sys

from experiments.metamorphic_adaptation.controlled_transfer_runner import (
    CONTROLLED_TRANSFER_RUN_READY_TOKEN,
    CONTROLLED_TRANSFER_RUN_REFUSED_TOKEN,
    CONTROLLED_TRANSFER_RUN_VERSION,
    stage_controlled_transfer_run,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_manifest(path, *, authorized=True, encounter_count=5):
    path.write_text(json.dumps({
        "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_MANIFEST_READY",
        "transfer_run_authorized": authorized,
        "execute_by_default": False,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
        "arms": ARMS,
        "encounter_count": encounter_count,
    }, indent=2, sort_keys=True))


def test_controlled_transfer_runner_stages_all_arms_and_encounters(tmp_path):
    manifest = tmp_path / "controlled_transfer_manifest.json"
    output = tmp_path / "run"
    _write_manifest(manifest, encounter_count=5)

    receipt = stage_controlled_transfer_run(
        manifest_path=manifest,
        output_dir=output,
    )

    assert receipt.run_version == CONTROLLED_TRANSFER_RUN_VERSION
    assert receipt.status == CONTROLLED_TRANSFER_RUN_READY_TOKEN
    assert receipt.transfer_run_authorized is True
    assert receipt.execute_requested is False
    assert receipt.executed is False
    assert receipt.arms_staged == 5
    assert receipt.encounters_staged == 25
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False

    for arm in ARMS:
        assert (output / arm).is_dir()

    lines = (output / "encounter_receipts.jsonl").read_text().splitlines()
    assert len(lines) == 25
    assert all(json.loads(line)["status"] == "STAGED_NOT_EXECUTED" for line in lines)
    assert all(json.loads(line)["executed"] is False for line in lines)


def test_controlled_transfer_runner_refuses_when_manifest_not_authorized(tmp_path):
    manifest = tmp_path / "controlled_transfer_manifest.json"
    output = tmp_path / "run"
    _write_manifest(manifest, authorized=False)

    receipt = stage_controlled_transfer_run(
        manifest_path=manifest,
        output_dir=output,
    )

    assert receipt.status == CONTROLLED_TRANSFER_RUN_REFUSED_TOKEN
    assert receipt.transfer_run_authorized is False
    assert receipt.executed is False
    assert receipt.arms_staged == 0
    assert receipt.encounters_staged == 0
    assert receipt.adaptive_claim_authorized is False


def test_controlled_transfer_runner_records_execute_request_without_executing(tmp_path):
    manifest = tmp_path / "controlled_transfer_manifest.json"
    output = tmp_path / "run"
    _write_manifest(manifest)

    receipt = stage_controlled_transfer_run(
        manifest_path=manifest,
        output_dir=output,
        execute=True,
    )

    assert receipt.execute_requested is True
    assert receipt.executed is False
    assert receipt.status == CONTROLLED_TRANSFER_RUN_READY_TOKEN


def test_controlled_transfer_runner_writes_run_receipt(tmp_path):
    manifest = tmp_path / "controlled_transfer_manifest.json"
    output = tmp_path / "run"
    _write_manifest(manifest)

    receipt = stage_controlled_transfer_run(
        manifest_path=manifest,
        output_dir=output,
    )

    data = json.loads((output / "controlled_transfer_run_receipt.json").read_text())

    assert data["status"] == receipt.status
    assert data["encounters_staged"] == 25
    assert data["adaptive_claim_authorized"] is False


def test_controlled_transfer_runner_boundary_blocks_overclaiming(tmp_path):
    manifest = tmp_path / "controlled_transfer_manifest.json"
    output = tmp_path / "run"
    _write_manifest(manifest)

    receipt = stage_controlled_transfer_run(
        manifest_path=manifest,
        output_dir=output,
    )

    boundary = receipt.boundary.lower()

    assert "stages controlled transfer encounters only" in boundary
    assert "does not execute" in boundary
    assert "does not claim improvement" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_controlled_transfer_cli_runner_writes_receipt(tmp_path):
    manifest = tmp_path / "controlled_transfer_manifest.json"
    output = tmp_path / "run"
    _write_manifest(manifest, encounter_count=2)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_controlled_transfer.py",
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert CONTROLLED_TRANSFER_RUN_READY_TOKEN in completed.stdout
    assert (output / "controlled_transfer_run_receipt.json").exists()
    assert (output / "encounter_receipts.jsonl").exists()

    lines = (output / "encounter_receipts.jsonl").read_text().splitlines()
    assert len(lines) == 10
