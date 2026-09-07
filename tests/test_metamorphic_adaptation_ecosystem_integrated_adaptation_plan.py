import json
import subprocess
import sys

from experiments.metamorphic_adaptation.ecosystem_integrated_adaptation_plan import (
    ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY_TOKEN,
    ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_REFUSED_TOKEN,
    ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_VERSION,
    build_ecosystem_integrated_adaptation_plan,
)


def _write_registry(path, *, ready=True):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_REFUSED"
        ),
        "real_ecosystem_execution_authorized": ready,
        "adaptive_claim_authorized": False,
        "organ_ids": [
            "DIO_CORE",
            "LINGUA",
            "BEAST",
            "SOPHIA",
            "EVIDEX",
            "HIVENANCE",
            "MARKET_SENSORIUM",
            "LEGALIS",
            "DOCUMENT_STUDIO",
            "NICHEFOUNDRY",
            "HOMS",
        ],
    }, indent=2, sort_keys=True))


def _write_evidence_digest(path, *, ready=True):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_REFUSED"
        ),
        "full_transfer_end_to_end_proven": ready,
        "real_task_quality_end_to_end_proven": ready,
        "adaptive_claim_authorized": False,
    }, indent=2, sort_keys=True))


def test_ecosystem_plan_stages_organ_mediated_surface(tmp_path):
    registry = tmp_path / "registry.json"
    evidence = tmp_path / "evidence.json"
    _write_registry(registry)
    _write_evidence_digest(evidence)

    receipt = build_ecosystem_integrated_adaptation_plan(
        registry_receipt_path=registry,
        evidence_digest_path=evidence,
        output_dir=tmp_path,
    )

    assert receipt.plan_version == ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_VERSION
    assert receipt.status == ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY_TOKEN
    assert receipt.arms_planned == 5
    assert receipt.tasks_planned == 5
    assert receipt.planned_encounters == 25
    assert receipt.tests_true_adaptive_surface is True
    assert receipt.execute_by_default is False
    assert receipt.adaptive_claim_authorized is False


def test_ecosystem_plan_writes_blinded_assignments_and_label_join(tmp_path):
    registry = tmp_path / "registry.json"
    evidence = tmp_path / "evidence.json"
    _write_registry(registry)
    _write_evidence_digest(evidence)

    receipt = build_ecosystem_integrated_adaptation_plan(
        registry_receipt_path=registry,
        evidence_digest_path=evidence,
        output_dir=tmp_path,
    )

    assignments = (tmp_path / "ecosystem_integrated_blinded_assignments.jsonl").read_text().splitlines()
    labels = json.loads((tmp_path / "ecosystem_integrated_label_join.json").read_text())
    plan = json.loads((tmp_path / "ecosystem_integrated_adaptation_plan.json").read_text())

    assert len(assignments) == 25
    assert len(labels) == 25
    assert len(plan["arms"]) == 5
    assert len(plan["tasks"]) == 5
    first = json.loads(assignments[0])
    assert first["blind_id"] in labels
    assert first["status"] == "ECOSYSTEM_INTEGRATED_ASSIGNMENT_STAGED_NOT_EXECUTED"
    assert first["execute_by_default"] is False
    assert first["adaptive_claim_authorized"] is False


def test_ecosystem_plan_refuses_without_registry(tmp_path):
    registry = tmp_path / "registry.json"
    evidence = tmp_path / "evidence.json"
    _write_registry(registry, ready=False)
    _write_evidence_digest(evidence)

    receipt = build_ecosystem_integrated_adaptation_plan(
        registry_receipt_path=registry,
        evidence_digest_path=evidence,
        output_dir=tmp_path,
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_REFUSED_TOKEN
    assert receipt.planned_encounters == 0
    assert receipt.tests_true_adaptive_surface is False


def test_ecosystem_plan_refuses_without_prior_evidence_digest(tmp_path):
    registry = tmp_path / "registry.json"
    evidence = tmp_path / "evidence.json"
    _write_registry(registry)
    _write_evidence_digest(evidence, ready=False)

    receipt = build_ecosystem_integrated_adaptation_plan(
        registry_receipt_path=registry,
        evidence_digest_path=evidence,
        output_dir=tmp_path,
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_REFUSED_TOKEN
    assert receipt.planned_encounters == 0
    assert receipt.adaptive_claim_authorized is False


def test_ecosystem_plan_boundary_blocks_overclaiming(tmp_path):
    registry = tmp_path / "registry.json"
    evidence = tmp_path / "evidence.json"
    _write_registry(registry)
    _write_evidence_digest(evidence)

    receipt = build_ecosystem_integrated_adaptation_plan(
        registry_receipt_path=registry,
        evidence_digest_path=evidence,
        output_dir=tmp_path,
    )

    boundary = receipt.boundary.lower()
    assert "ecosystem integrated adaptation gauntlet" in boundary
    assert "beast" in boundary
    assert "sophia" in boundary
    assert "hivenance" in boundary
    assert "executes nothing by default" in boundary
    assert "authority-expansion" in boundary


def test_ecosystem_plan_cli_runner(tmp_path):
    registry = tmp_path / "registry.json"
    evidence = tmp_path / "evidence.json"
    output = tmp_path / "out"
    _write_registry(registry)
    _write_evidence_digest(evidence)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_ecosystem_integrated_adaptation_plan.py",
            "--registry-receipt",
            str(registry),
            "--evidence-digest",
            str(evidence),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY_TOKEN in completed.stdout
    assert (output / "ecosystem_integrated_adaptation_plan_receipt.json").exists()
