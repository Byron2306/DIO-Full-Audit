import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.full_controlled_transfer_plan import (
    FULL_TRANSFER_PLAN_READY_TOKEN,
    FULL_TRANSFER_PLAN_REFUSED_TOKEN,
    FULL_TRANSFER_PLAN_VERSION,
    build_full_controlled_transfer_plan,
    write_full_controlled_transfer_plan,
)


def _write_digest(path, *, ready=True, pilot=True, adaptive_claim=False):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_DIGEST_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_DIGEST_REFUSED"
        ),
        "real_pilot_end_to_end_proven": pilot,
        "ready_to_plan_full_controlled_transfer_run": ready and pilot,
        "allowed_claim_tier": (
            "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
            if ready and pilot
            else "T0_NO_CLAIM"
        ),
        "adaptive_claim_authorized": adaptive_claim,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def test_full_controlled_transfer_plan_authorizes_planning_from_real_pilot_digest(tmp_path):
    digest = tmp_path / "real_pilot_digest.json"
    _write_digest(digest)

    plan = build_full_controlled_transfer_plan(real_pilot_digest_path=digest)

    assert plan.plan_version == FULL_TRANSFER_PLAN_VERSION
    assert plan.status == FULL_TRANSFER_PLAN_READY_TOKEN
    assert plan.full_run_planning_authorized is True
    assert plan.execute_by_default is False
    assert plan.requires_explicit_execute_flag is True
    assert plan.encounters_per_arm == 5
    assert plan.full_run_encounters == 25
    assert len(plan.arms) == 5
    assert plan.requires_blind_evaluation is True
    assert plan.requires_factorial_analysis is True
    assert plan.requires_claim_gate is True
    assert plan.adaptive_claim_authorized is False


def test_full_controlled_transfer_plan_refuses_without_ready_pilot_digest(tmp_path):
    digest = tmp_path / "real_pilot_digest.json"
    _write_digest(digest, ready=False, pilot=False)

    plan = build_full_controlled_transfer_plan(real_pilot_digest_path=digest)

    assert plan.status == FULL_TRANSFER_PLAN_REFUSED_TOKEN
    assert plan.full_run_planning_authorized is False
    assert plan.full_run_encounters == 0
    assert plan.allowed_claim_tier == "T0_NO_CLAIM"


def test_full_controlled_transfer_plan_refuses_upstream_adaptive_claim(tmp_path):
    digest = tmp_path / "real_pilot_digest.json"
    _write_digest(digest, adaptive_claim=True)

    plan = build_full_controlled_transfer_plan(real_pilot_digest_path=digest)

    assert plan.status == FULL_TRANSFER_PLAN_REFUSED_TOKEN
    assert plan.full_run_planning_authorized is False
    assert plan.adaptive_claim_authorized is False


def test_full_controlled_transfer_plan_writes_json_and_hashes_digest(tmp_path):
    digest = tmp_path / "real_pilot_digest.json"
    output = tmp_path / "full_controlled_transfer_plan.json"
    _write_digest(digest)

    plan = write_full_controlled_transfer_plan(
        real_pilot_digest_path=digest,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(plan)))
    assert len(data["real_pilot_digest_sha256"]) == 64
    assert data["status"] == FULL_TRANSFER_PLAN_READY_TOKEN


def test_full_controlled_transfer_plan_boundary_blocks_overclaiming(tmp_path):
    digest = tmp_path / "real_pilot_digest.json"
    _write_digest(digest)

    plan = build_full_controlled_transfer_plan(real_pilot_digest_path=digest)

    boundary = plan.boundary.lower()

    assert "planning of the full 25-encounter real controlled transfer run" in boundary
    assert "does not execute by default" in boundary
    assert "adaptive-composition" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_full_controlled_transfer_plan_cli_runner(tmp_path):
    digest = tmp_path / "real_pilot_digest.json"
    output = tmp_path / "full_controlled_transfer_plan.json"
    _write_digest(digest)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_full_controlled_transfer_plan.py",
            "--real-pilot-digest",
            str(digest),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert FULL_TRANSFER_PLAN_READY_TOKEN in completed.stdout
    assert output.exists()
