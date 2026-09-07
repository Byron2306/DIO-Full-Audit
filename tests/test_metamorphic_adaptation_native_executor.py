import json
from pathlib import Path

from experiments.metamorphic_adaptation.native_executor import (
    EXECUTOR_REFUSED_TOKEN,
    EXECUTOR_VERSION,
    execute_native_plan,
)


def test_native_executor_refuses_without_execute_flag(tmp_path):
    receipt = execute_native_plan(output_dir=tmp_path / "native-exec", execute=False)

    assert receipt.executor_version == EXECUTOR_VERSION
    assert receipt.status == EXECUTOR_REFUSED_TOKEN
    assert receipt.execute_requested is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.command_results

    for result in receipt.command_results:
        assert result.executed is False
        assert result.exit_code is None
        assert result.refusal_reason


def test_native_executor_writes_plan_and_receipt_without_execution(tmp_path):
    output_dir = tmp_path / "native-exec"

    execute_native_plan(output_dir=output_dir, execute=False)

    plan_path = output_dir / "native_execution_plan.json"
    receipt_path = output_dir / "native_execution_receipt.json"

    assert plan_path.exists()
    assert receipt_path.exists()

    plan = json.loads(plan_path.read_text())
    receipt = json.loads(receipt_path.read_text())

    assert plan["status"] == "DIO_METAMORPHIC_ADAPTATION_NATIVE_EXECUTION_PLAN_READY"
    assert receipt["status"] == EXECUTOR_REFUSED_TOKEN
    assert receipt["adaptive_claim_authorized"] is False


def test_native_executor_refusal_boundary_separates_execution_from_claim(tmp_path):
    receipt = execute_native_plan(output_dir=tmp_path / "native-exec", execute=False)

    boundary = receipt.refusal_boundary.lower()

    assert "refused execution" in boundary
    assert "planning" in boundary
    assert "execution" in boundary
    assert "adaptive-composition claims" in boundary


def test_native_executor_plan_contains_all_commands_but_runs_none(tmp_path):
    receipt = execute_native_plan(output_dir=tmp_path / "native-exec", execute=False)

    assert len(receipt.command_results) == 12

    labels = {result.label for result in receipt.command_results}

    assert "media_incarnation_phase16_1" in labels
    assert "market_sensorium_cycle" in labels
    assert "professional_task_gauntlet" in labels

    assert all(result.executed is False for result in receipt.command_results)
