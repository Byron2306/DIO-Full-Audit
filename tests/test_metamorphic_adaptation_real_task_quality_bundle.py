import json
import subprocess
import sys

from experiments.metamorphic_adaptation.real_task_quality_bundle import (
    REAL_TASK_QUALITY_BUNDLE_READY_TOKEN,
    REAL_TASK_QUALITY_BUNDLE_REFUSED_TOKEN,
    REAL_TASK_QUALITY_BUNDLE_VERSION,
    build_real_task_quality_bundle,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_digest(path, *, ready=True):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_REFUSED"
        ),
        "full_transfer_end_to_end_proven": ready,
        "allowed_claim_tier": (
            "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY"
            if ready
            else "T0_NO_CLAIM"
        ),
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_scaffold(encounters_path, labels_path, *, count=25):
    labels = {}
    with encounters_path.open("w") as fh:
        ordinal = 1
        for arm in ARMS:
            for encounter_index in range(1, 6):
                if ordinal > count:
                    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))
                    return
                blind_id = f"FULL-TRANSFER-BLIND-{ordinal:04d}"
                fh.write(json.dumps({
                    "blind_id": blind_id,
                    "arm": arm,
                    "encounter_index": encounter_index,
                    "status": "FULL_CONTROLLED_TRANSFER_STAGED_NOT_EXECUTED",
                    "executed": False,
                    "native_execution_allowed_only_with_explicit_flag": True,
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")
                labels[blind_id] = {
                    "arm": arm,
                    "encounter_index": encounter_index,
                }
                ordinal += 1
    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True))


def test_real_task_quality_bundle_stages_25_blinded_assignments(tmp_path):
    digest = tmp_path / "full_controlled_transfer_digest.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_labels.json"
    output = tmp_path / "quality_bundle"

    _write_digest(digest)
    _write_scaffold(encounters, labels)

    receipt = build_real_task_quality_bundle(
        full_transfer_digest_path=digest,
        scaffold_encounters_path=encounters,
        scaffold_labels_path=labels,
        output_dir=output,
    )

    assert receipt.bundle_version == REAL_TASK_QUALITY_BUNDLE_VERSION
    assert receipt.status == REAL_TASK_QUALITY_BUNDLE_READY_TOKEN
    assert receipt.task_bank_size == 5
    assert receipt.task_assignments_staged == 25
    assert receipt.real_task_quality_scoring_authorized is True
    assert receipt.execute_by_default is False
    assert receipt.adaptive_claim_authorized is False

    assignments = (output / "real_task_quality_blinded_assignments.jsonl").read_text().splitlines()
    assert len(assignments) == 25

    first = json.loads(assignments[0])
    assert first["blind_id"] == "FULL-TRANSFER-BLIND-0001"
    assert first["task_id"] == "RTQ-001"
    assert "arm" not in first
    assert first["real_task_quality_scoring_authorized"] is True


def test_real_task_quality_bundle_rotates_five_tasks_across_25_assignments(tmp_path):
    digest = tmp_path / "full_controlled_transfer_digest.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_labels.json"
    output = tmp_path / "quality_bundle"

    _write_digest(digest)
    _write_scaffold(encounters, labels)

    build_real_task_quality_bundle(
        full_transfer_digest_path=digest,
        scaffold_encounters_path=encounters,
        scaffold_labels_path=labels,
        output_dir=output,
    )

    assignments = [
        json.loads(line)
        for line in (output / "real_task_quality_blinded_assignments.jsonl").read_text().splitlines()
    ]
    task_ids = [item["task_id"] for item in assignments]

    assert task_ids[:5] == ["RTQ-001", "RTQ-002", "RTQ-003", "RTQ-004", "RTQ-005"]
    assert task_ids[20:25] == ["RTQ-001", "RTQ-002", "RTQ-003", "RTQ-004", "RTQ-005"]


def test_real_task_quality_bundle_writes_label_join_without_leaking_into_assignments(tmp_path):
    digest = tmp_path / "full_controlled_transfer_digest.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_labels.json"
    output = tmp_path / "quality_bundle"

    _write_digest(digest)
    _write_scaffold(encounters, labels)

    build_real_task_quality_bundle(
        full_transfer_digest_path=digest,
        scaffold_encounters_path=encounters,
        scaffold_labels_path=labels,
        output_dir=output,
    )

    join = json.loads((output / "real_task_quality_label_join.json").read_text())
    assignments = [
        json.loads(line)
        for line in (output / "real_task_quality_blinded_assignments.jsonl").read_text().splitlines()
    ]

    assert join["FULL-TRANSFER-BLIND-0001"]["arm"] == "A_STATELESS_RESET"
    assert join["FULL-TRANSFER-BLIND-0025"]["arm"] == "E_FULL_SEMANTIC_MARKET_BEAST"
    assert all("arm" not in item for item in assignments)


def test_real_task_quality_bundle_refuses_without_ready_digest(tmp_path):
    digest = tmp_path / "full_controlled_transfer_digest.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_labels.json"
    output = tmp_path / "quality_bundle"

    _write_digest(digest, ready=False)
    _write_scaffold(encounters, labels)

    receipt = build_real_task_quality_bundle(
        full_transfer_digest_path=digest,
        scaffold_encounters_path=encounters,
        scaffold_labels_path=labels,
        output_dir=output,
    )

    assert receipt.status == REAL_TASK_QUALITY_BUNDLE_REFUSED_TOKEN
    assert receipt.task_assignments_staged == 0
    assert receipt.real_task_quality_scoring_authorized is False
    assert receipt.adaptive_claim_authorized is False


def test_real_task_quality_bundle_refuses_incomplete_scaffold(tmp_path):
    digest = tmp_path / "full_controlled_transfer_digest.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_labels.json"
    output = tmp_path / "quality_bundle"

    _write_digest(digest)
    _write_scaffold(encounters, labels, count=24)

    receipt = build_real_task_quality_bundle(
        full_transfer_digest_path=digest,
        scaffold_encounters_path=encounters,
        scaffold_labels_path=labels,
        output_dir=output,
    )

    assert receipt.status == REAL_TASK_QUALITY_BUNDLE_REFUSED_TOKEN
    assert receipt.task_assignments_staged == 0


def test_real_task_quality_bundle_writes_receipt_and_hashes_sources(tmp_path):
    digest = tmp_path / "full_controlled_transfer_digest.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_labels.json"
    output = tmp_path / "quality_bundle"

    _write_digest(digest)
    _write_scaffold(encounters, labels)

    receipt = build_real_task_quality_bundle(
        full_transfer_digest_path=digest,
        scaffold_encounters_path=encounters,
        scaffold_labels_path=labels,
        output_dir=output,
    )

    data = json.loads((output / "real_task_quality_bundle_receipt.json").read_text())

    assert data["status"] == receipt.status
    assert len(data["full_transfer_digest_sha256"]) == 64
    assert len(data["scaffold_encounters_sha256"]) == 64
    assert len(data["scaffold_labels_sha256"]) == 64


def test_real_task_quality_bundle_boundary_blocks_overclaiming(tmp_path):
    digest = tmp_path / "full_controlled_transfer_digest.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_labels.json"
    output = tmp_path / "quality_bundle"

    _write_digest(digest)
    _write_scaffold(encounters, labels)

    receipt = build_real_task_quality_bundle(
        full_transfer_digest_path=digest,
        scaffold_encounters_path=encounters,
        scaffold_labels_path=labels,
        output_dir=output,
    )

    boundary = receipt.boundary.lower()

    assert "25 blinded real task-quality assignments" in boundary
    assert "task-quality scoring preparation only" in boundary
    assert "does not execute tasks by default" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_real_task_quality_bundle_cli_runner(tmp_path):
    digest = tmp_path / "full_controlled_transfer_digest.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    labels = tmp_path / "full_controlled_transfer_blind_labels.json"
    output = tmp_path / "quality_bundle"

    _write_digest(digest)
    _write_scaffold(encounters, labels)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_bundle.py",
            "--full-transfer-digest",
            str(digest),
            "--scaffold-encounters",
            str(encounters),
            "--scaffold-labels",
            str(labels),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_TASK_QUALITY_BUNDLE_READY_TOKEN in completed.stdout
    assert (output / "real_task_quality_bundle_receipt.json").exists()
    assert (output / "real_task_quality_blinded_assignments.jsonl").exists()
    assert (output / "real_task_quality_task_bank.json").exists()
    assert (output / "real_task_quality_label_join.json").exists()
