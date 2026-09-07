import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_controlled_transfer_plan import (
    REAL_TRANSFER_PLAN_READY_TOKEN,
    REAL_TRANSFER_PLAN_REFUSED_TOKEN,
    REAL_TRANSFER_PLAN_VERSION,
    build_real_controlled_transfer_plan,
    write_real_controlled_transfer_plan,
)


def _write_fixture_digest(path, *, ready=True, mechanics=True, adaptive_claim=False):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FIXTURE_EXPERIMENT_DIGEST_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_FIXTURE_EXPERIMENT_DIGEST_REFUSED"
        ),
        "end_to_end_fixture_mechanics_proven": mechanics,
        "ready_for_real_controlled_transfer_execution": ready and mechanics,
        "adaptive_claim_authorized": adaptive_claim,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def test_real_controlled_transfer_plan_authorizes_limited_pilot_from_fixture_digest(tmp_path):
    digest = tmp_path / "fixture_experiment_digest.json"
    _write_fixture_digest(digest)

    plan = build_real_controlled_transfer_plan(fixture_digest_path=digest)

    assert plan.plan_version == REAL_TRANSFER_PLAN_VERSION
    assert plan.status == REAL_TRANSFER_PLAN_READY_TOKEN
    assert plan.real_pilot_authorized is True
    assert plan.execute_by_default is False
    assert plan.pilot_encounters == 5
    assert plan.full_run_encounters_locked == 25
    assert len(plan.arms) == 5
    assert plan.adaptive_claim_authorized is False
    assert plan.commercial_or_world_first_claim_authorized is False


def test_real_controlled_transfer_plan_refuses_when_fixture_digest_not_ready(tmp_path):
    digest = tmp_path / "fixture_experiment_digest.json"
    _write_fixture_digest(digest, ready=False, mechanics=False)

    plan = build_real_controlled_transfer_plan(fixture_digest_path=digest)

    assert plan.status == REAL_TRANSFER_PLAN_REFUSED_TOKEN
    assert plan.real_pilot_authorized is False
    assert plan.pilot_encounters == 0
    assert plan.execute_by_default is False


def test_real_controlled_transfer_plan_refuses_if_upstream_adaptive_claim_exists(tmp_path):
    digest = tmp_path / "fixture_experiment_digest.json"
    _write_fixture_digest(digest, adaptive_claim=True)

    plan = build_real_controlled_transfer_plan(fixture_digest_path=digest)

    assert plan.status == REAL_TRANSFER_PLAN_REFUSED_TOKEN
    assert plan.real_pilot_authorized is False
    assert plan.adaptive_claim_authorized is False


def test_real_controlled_transfer_plan_writes_json_and_hashes_digest(tmp_path):
    digest = tmp_path / "fixture_experiment_digest.json"
    output = tmp_path / "real_controlled_transfer_plan.json"
    _write_fixture_digest(digest)

    plan = write_real_controlled_transfer_plan(
        fixture_digest_path=digest,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(plan)))
    assert len(data["fixture_digest_sha256"]) == 64
    assert data["status"] == REAL_TRANSFER_PLAN_READY_TOKEN


def test_real_controlled_transfer_plan_boundary_blocks_overclaiming(tmp_path):
    digest = tmp_path / "fixture_experiment_digest.json"
    _write_fixture_digest(digest)

    plan = build_real_controlled_transfer_plan(fixture_digest_path=digest)

    boundary = plan.boundary.lower()

    assert "limited real native controlled-transfer pilot only" in boundary
    assert "does not execute by default" in boundary
    assert "does not authorize the full 25-encounter run" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_real_controlled_transfer_plan_cli_runner(tmp_path):
    digest = tmp_path / "fixture_experiment_digest.json"
    output = tmp_path / "real_controlled_transfer_plan.json"
    _write_fixture_digest(digest)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_controlled_transfer_plan.py",
            "--fixture-digest",
            str(digest),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_TRANSFER_PLAN_READY_TOKEN in completed.stdout
    assert output.exists()
