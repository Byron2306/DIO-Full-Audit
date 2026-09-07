from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from experiments.metamorphic_adaptation.preflight import write_native_preflight_bundle
from experiments.metamorphic_adaptation.native_bindings import load_native_bindings


PLAN_VERSION = "DIO_METAMORPHIC_ADAPTATION_NATIVE_EXECUTION_PLAN_V1"
PLAN_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_NATIVE_EXECUTION_PLAN_READY"


@dataclass(frozen=True)
class PlannedNativeCommand:
    label: str
    command_group: str
    script_path: str
    factor_pressure: tuple[str, ...]
    resolved_argv: tuple[str, ...]


@dataclass(frozen=True)
class NativeExecutionPlan:
    plan_version: str
    status: str
    preflight_receipt_path: str
    run_output: str
    planned_commands: tuple[PlannedNativeCommand, ...]
    execute_by_default: bool
    refusal_boundary: str


def build_native_execution_plan(
    *,
    output_dir: Path,
    python_executable: str = "python",
) -> NativeExecutionPlan:
    output_dir.mkdir(parents=True, exist_ok=True)

    preflight_dir = output_dir / "preflight"
    run_output = output_dir / "run_output"

    write_native_preflight_bundle(preflight_dir)

    bindings = load_native_bindings()

    planned = []
    for command in bindings.adaptation_commands + bindings.transfer_commands:
        planned.append(
            PlannedNativeCommand(
                label=command.label,
                command_group=command.command_group,
                script_path=str(command.script_path),
                factor_pressure=command.factor_pressure,
                resolved_argv=command.resolved_argv(
                    run_output=run_output,
                    python_executable=python_executable,
                ),
            )
        )

    return NativeExecutionPlan(
        plan_version=PLAN_VERSION,
        status=PLAN_READY_TOKEN,
        preflight_receipt_path=str(preflight_dir / "native_preflight_receipt.json"),
        run_output=str(run_output),
        planned_commands=tuple(planned),
        execute_by_default=False,
        refusal_boundary=(
            "This plan expands native DIO commands but does not execute them. "
            "Execution requires an explicit operator action and remains separate "
            "from any adaptive-composition claim."
        ),
    )


def write_native_execution_plan(
    output_dir: Path,
    *,
    python_executable: str = "python",
) -> NativeExecutionPlan:
    plan = build_native_execution_plan(
        output_dir=output_dir,
        python_executable=python_executable,
    )

    plan_path = output_dir / "native_execution_plan.json"
    plan_path.write_text(json.dumps(asdict(plan), indent=2, sort_keys=True) + "\n")
    return plan
