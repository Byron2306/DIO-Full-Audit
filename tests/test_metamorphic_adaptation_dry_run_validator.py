from pathlib import Path

import pytest

from experiments.metamorphic_adaptation.dry_run_validator import (
    NativeDryRunError,
    validate_native_dry_run,
)
from experiments.metamorphic_adaptation.native_bindings import NativeBindings, NativeCommand


def test_dry_run_validator_accepts_bound_native_commands(tmp_path):
    report = validate_native_dry_run(run_output=tmp_path / "run-output", python_executable="python")

    assert report.status == "NATIVE_DRY_RUN_VALIDATED"
    assert report.command_checks

    labels = {check.label for check in report.command_checks}
    assert "media_incarnation_phase16_1" in labels
    assert "professional_task_gauntlet" in labels

    for check in report.command_checks:
        assert check.has_output_contract is True
        assert "{run_output}" not in " ".join(check.resolved_argv)


def test_dry_run_validator_rejects_missing_output_contract(tmp_path):
    script = Path("scripts/run_media_incarnation_phase16_1.py")
    assert script.exists(), "fixture assumes real media script exists"

    bindings = NativeBindings(
        binding_version="DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1",
        adaptation_commands=(
            NativeCommand(
                label="unsafe_no_output",
                argv=("python", str(script)),
                script_path=script,
                command_group="unsafe",
                factor_pressure=("semantic",),
            ),
        ),
        transfer_commands=(),
        state_roots={"semantic": (Path("state/lingua"),), "market": (Path("state/market"),), "beast": (Path("state/beast"),)},
        authority_roots=(Path("authority"), Path("governance")),
    )

    with pytest.raises(NativeDryRunError, match="lacks dry-run output contract"):
        validate_native_dry_run(bindings=bindings, run_output=tmp_path / "run-output")


def test_dry_run_validator_rejects_absolute_escape_path(tmp_path):
    script = Path("scripts/run_media_incarnation_phase16_1.py")
    assert script.exists(), "fixture assumes real media script exists"

    bindings = NativeBindings(
        binding_version="DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1",
        adaptation_commands=(
            NativeCommand(
                label="absolute_escape",
                argv=("python", str(script), "--output", "{run_output}/safe", "--cache", "/tmp/outside-custody"),
                script_path=script,
                command_group="unsafe",
                factor_pressure=("semantic",),
            ),
        ),
        transfer_commands=(),
        state_roots={"semantic": (Path("state/lingua"),), "market": (Path("state/market"),), "beast": (Path("state/beast"),)},
        authority_roots=(Path("authority"), Path("governance")),
    )

    with pytest.raises(NativeDryRunError, match="absolute path escapes"):
        validate_native_dry_run(bindings=bindings, run_output=tmp_path / "run-output")


def test_dry_run_validator_allows_observational_commands_without_artifact_claim(tmp_path):
    script = Path("scripts/run_market_sensorium_cycle.py")
    assert script.exists(), "fixture assumes real market sensorium script exists"

    bindings = NativeBindings(
        binding_version="DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1",
        adaptation_commands=(
            NativeCommand(
                label="market_sensorium_cycle",
                argv=("python", str(script)),
                script_path=script,
                command_group="market_sensorium_hivenance",
                factor_pressure=("market",),
            ),
        ),
        transfer_commands=(),
        state_roots={"semantic": (Path("state/lingua"),), "market": (Path("state/market"),), "beast": (Path("state/beast"),)},
        authority_roots=(Path("authority"), Path("governance")),
    )

    report = validate_native_dry_run(bindings=bindings, run_output=tmp_path / "run-output")
    assert report.status == "NATIVE_DRY_RUN_VALIDATED"
