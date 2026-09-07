from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from experiments.metamorphic_adaptation.native_bindings import (
    NativeBindingError,
    NativeBindings,
    NativeCommand,
    load_native_bindings,
)


class NativeDryRunError(ValueError):
    """Raised when a native command cannot be safely dry-run validated."""


@dataclass(frozen=True)
class DryRunCommandCheck:
    label: str
    command_group: str
    script_path: str
    has_output_contract: bool
    resolved_argv: tuple[str, ...]


@dataclass(frozen=True)
class DryRunValidationReport:
    status: str
    command_checks: tuple[DryRunCommandCheck, ...]


def _has_output_contract(command: NativeCommand) -> bool:
    argv = command.argv

    # Transfer/adaptation commands must either declare an explicit --output target,
    # use {run_output}, or belong to known observational/import/manage commands
    # that are not permitted to claim artifact generation by themselves.
    if "--output" in argv and any("{run_output}" in part for part in argv):
        return True

    observational_or_native_default_output = (
        "market_sensorium_cycle",
        "hivenance_market_command_import",
        "market_command_manage",
        "dio_marketing_integration",
        "lingua_marketing_learning",
        "nichefoundry_media_pipeline",
    )

    return command.label in observational_or_native_default_output


def _validate_resolved_argv(command: NativeCommand, run_output: Path, python_executable: str) -> tuple[str, ...]:
    resolved = command.resolved_argv(run_output=run_output, python_executable=python_executable)

    if any("{run_output}" in part for part in resolved):
        raise NativeDryRunError(f"{command.label}: unresolved run_output placeholder")

    run_output_resolved = run_output.resolve()

    for part in resolved:
        if "\x00" in part:
            raise NativeDryRunError(f"{command.label}: resolved argv contains NUL byte")

        if part.startswith(("http://", "https://", "ssh://", "git@")):
            raise NativeDryRunError(f"{command.label}: resolved argv contains external resource: {part}")

        if part.startswith("/") and Path(part) != Path(python_executable):
            candidate = Path(part).resolve()
            if run_output_resolved not in [candidate, *candidate.parents]:
                raise NativeDryRunError(
                    f"{command.label}: absolute path escapes run output custody: {part}"
                )

    return resolved


def validate_native_dry_run(
    *,
    bindings: NativeBindings | None = None,
    run_output: Path = Path("/tmp/dio-metamorphic-adaptation-dry-run"),
    python_executable: str = "python",
) -> DryRunValidationReport:
    bindings = bindings or load_native_bindings()

    checks = []

    for command in bindings.adaptation_commands + bindings.transfer_commands:
        if not command.script_path.exists():
            raise NativeDryRunError(f"{command.label}: script no longer exists: {command.script_path}")

        has_output_contract = _has_output_contract(command)
        if not has_output_contract:
            raise NativeDryRunError(f"{command.label}: command lacks dry-run output contract")

        resolved_argv = _validate_resolved_argv(command, run_output, python_executable)

        checks.append(
            DryRunCommandCheck(
                label=command.label,
                command_group=command.command_group,
                script_path=str(command.script_path),
                has_output_contract=has_output_contract,
                resolved_argv=resolved_argv,
            )
        )

    return DryRunValidationReport(
        status="NATIVE_DRY_RUN_VALIDATED",
        command_checks=tuple(checks),
    )
