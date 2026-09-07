import json
from pathlib import Path

import pytest

from experiments.metamorphic_adaptation.native_bindings import (
    NativeBindingError,
    load_native_bindings,
    validate_native_bindings,
)


def test_native_loader_resolves_declared_commands():
    bindings = load_native_bindings()

    assert bindings.binding_version == "DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1"
    assert len(bindings.adaptation_commands) >= 3
    assert len(bindings.transfer_commands) >= 1

    labels = {command.label for command in bindings.adaptation_commands + bindings.transfer_commands}

    assert "media_incarnation_phase16_1" in labels
    assert "market_sensorium_cycle" in labels
    assert "professional_task_gauntlet" in labels

    for command in bindings.adaptation_commands + bindings.transfer_commands:
        assert command.argv[0] == "python"
        assert command.script_path.exists()


def test_native_loader_resolves_run_output_placeholder(tmp_path):
    bindings = load_native_bindings()
    command = next(c for c in bindings.adaptation_commands if c.label == "media_incarnation_phase16_1")

    argv = command.resolved_argv(tmp_path / "run-output", python_executable="/venv/bin/python")

    assert argv[0] == "/venv/bin/python"
    assert "{run_output}" not in " ".join(argv)
    assert str(tmp_path / "run-output" / "media_incarnation") in argv


def test_native_loader_rejects_missing_script(tmp_path):
    cfg = {
        "binding_version": "DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1",
        "adaptation_episodes": [
            {
                "episode_id": "bad",
                "factor_pressure": ["semantic"],
                "commands": [
                    {
                        "label": "missing",
                        "argv": ["python", "scripts/no_such_script.py"],
                    }
                ],
            }
        ],
        "transfer_executors": [],
        "state_roots": {"semantic": ["state/lingua"], "market": ["state/market"], "beast": ["state/beast"]},
        "authority_roots": ["authority", "governance"],
    }

    path = tmp_path / "bad.json"
    path.write_text(json.dumps(cfg))

    with pytest.raises(NativeBindingError, match="script does not exist"):
        load_native_bindings(config_path=path)


def test_native_loader_rejects_external_command(tmp_path):
    cfg = {
        "binding_version": "DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1",
        "adaptation_episodes": [
            {
                "episode_id": "bad",
                "factor_pressure": ["market"],
                "commands": [
                    {
                        "label": "external",
                        "argv": ["curl", "https://example.com/script.py"],
                    }
                ],
            }
        ],
        "transfer_executors": [],
        "state_roots": {"semantic": ["state/lingua"], "market": ["state/market"], "beast": ["state/beast"]},
        "authority_roots": ["authority", "governance"],
    }

    path = tmp_path / "bad.json"
    path.write_text(json.dumps(cfg))

    with pytest.raises(NativeBindingError, match="first argv element must be python"):
        load_native_bindings(config_path=path)


def test_native_loader_rejects_authority_state_overlap(tmp_path):
    cfg = {
        "binding_version": "DIO_METAMORPHIC_ADAPTATION_NATIVE_BINDINGS_V1",
        "adaptation_episodes": [],
        "transfer_executors": [],
        "state_roots": {"semantic": ["authority"], "market": ["state/market"], "beast": ["state/beast"]},
        "authority_roots": ["authority", "governance"],
    }

    path = tmp_path / "bad.json"
    path.write_text(json.dumps(cfg))

    with pytest.raises(NativeBindingError, match="authority roots overlap"):
        load_native_bindings(config_path=path)


def test_native_binding_validation_summary_is_stable():
    summary = validate_native_bindings()

    assert summary["status"] == "NATIVE_BINDINGS_VALID"
    assert summary["adaptation_commands"] >= 3
    assert summary["transfer_commands"] >= 1
