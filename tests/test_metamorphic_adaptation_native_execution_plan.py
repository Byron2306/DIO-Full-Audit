import json
from dataclasses import asdict

from experiments.metamorphic_adaptation.native_execution_plan import (
    PLAN_READY_TOKEN,
    PLAN_VERSION,
    write_native_execution_plan,
)


def test_native_execution_plan_writes_plan_and_preflight_bundle(tmp_path):
    output_dir = tmp_path / "native-plan"

    plan = write_native_execution_plan(output_dir)

    plan_path = output_dir / "native_execution_plan.json"
    preflight_receipt = output_dir / "preflight" / "native_preflight_receipt.json"

    assert plan_path.exists()
    assert preflight_receipt.exists()

    data = json.loads(plan_path.read_text())

    assert data == json.loads(json.dumps(asdict(plan)))
    assert data["plan_version"] == PLAN_VERSION
    assert data["status"] == PLAN_READY_TOKEN
    assert data["execute_by_default"] is False


def test_native_execution_plan_expands_all_bound_commands(tmp_path):
    plan = write_native_execution_plan(tmp_path / "native-plan")

    assert len(plan.planned_commands) == 12

    labels = {command.label for command in plan.planned_commands}

    assert "media_incarnation_phase16_1" in labels
    assert "market_sensorium_cycle" in labels
    assert "professional_task_gauntlet" in labels

    for command in plan.planned_commands:
        joined = " ".join(command.resolved_argv)
        assert "{run_output}" not in joined
        assert command.resolved_argv[0] == "python"


def test_native_execution_plan_is_not_execution_or_claim(tmp_path):
    plan = write_native_execution_plan(tmp_path / "native-plan")

    boundary = plan.refusal_boundary.lower()

    assert plan.execute_by_default is False
    assert "does not execute" in boundary
    assert "adaptive-composition claim" in boundary
