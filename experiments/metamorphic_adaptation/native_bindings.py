from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CONFIG_PATH = Path("experiments/metamorphic_adaptation/config/native_bindings.v1.json")


class NativeBindingError(ValueError):
    """Raised when native DIO bindings are unsafe, missing, or malformed."""


@dataclass(frozen=True)
class NativeCommand:
    label: str
    argv: tuple[str, ...]
    script_path: Path
    command_group: str
    factor_pressure: tuple[str, ...] = ()

    def resolved_argv(self, run_output: Path, python_executable: str = "python") -> tuple[str, ...]:
        output = str(run_output)
        resolved = []
        for part in self.argv:
            if part == "python":
                resolved.append(python_executable)
            else:
                resolved.append(part.replace("{run_output}", output))
        return tuple(resolved)


@dataclass(frozen=True)
class NativeBindings:
    binding_version: str
    adaptation_commands: tuple[NativeCommand, ...]
    transfer_commands: tuple[NativeCommand, ...]
    state_roots: dict[str, tuple[Path, ...]]
    authority_roots: tuple[Path, ...]


def _repo_relative_path(value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        raise NativeBindingError(f"absolute paths are not allowed: {value}")

    if ".." in path.parts:
        raise NativeBindingError(f"path traversal is not allowed: {value}")

    return path


def _script_from_argv(argv: Iterable[str]) -> Path:
    scripts = [
        _repo_relative_path(part)
        for part in argv
        if part.startswith("scripts/") and part.endswith(".py")
    ]

    if len(scripts) != 1:
        raise NativeBindingError(f"expected exactly one repository script in argv, got {len(scripts)}")

    return scripts[0]


def _validate_argv(label: str, argv: list[str]) -> tuple[str, ...]:
    if not argv:
        raise NativeBindingError(f"{label}: argv may not be empty")

    if argv[0] not in {"python", "{python}"}:
        raise NativeBindingError(f"{label}: first argv element must be python")

    for part in argv:
        if "\x00" in part:
            raise NativeBindingError(f"{label}: argv contains NUL byte")

        if part.startswith(("http://", "https://", "ssh://", "git@")):
            raise NativeBindingError(f"{label}: external command/resource is not allowed: {part}")

        if part.startswith("/") and part != "{run_output}":
            raise NativeBindingError(f"{label}: absolute argv path is not allowed: {part}")

        if ".." in Path(part.replace("{run_output}", "run_output")).parts:
            raise NativeBindingError(f"{label}: argv path traversal is not allowed: {part}")

    return tuple("python" if part == "{python}" else part for part in argv)


def _validate_command(
    *,
    label: str,
    argv: list[str],
    command_group: str,
    factor_pressure: Iterable[str] = (),
    repo_root: Path,
) -> NativeCommand:
    safe_argv = _validate_argv(label, argv)
    script_path = _script_from_argv(safe_argv)

    if not (repo_root / script_path).exists():
        raise NativeBindingError(f"{label}: script does not exist: {script_path}")

    return NativeCommand(
        label=label,
        argv=safe_argv,
        script_path=script_path,
        command_group=command_group,
        factor_pressure=tuple(factor_pressure),
    )


def load_native_bindings(
    config_path: Path = CONFIG_PATH,
    repo_root: Path = Path("."),
) -> NativeBindings:
    repo_root = repo_root.resolve()
    config_path = config_path if config_path.is_absolute() else repo_root / config_path

    if not config_path.exists():
        raise NativeBindingError(f"native binding config missing: {config_path}")

    cfg = json.loads(config_path.read_text())

    state_roots = {
        factor: tuple(_repo_relative_path(root) for root in roots)
        for factor, roots in cfg["state_roots"].items()
    }

    if set(state_roots) != {"semantic", "market", "beast"}:
        raise NativeBindingError("state_roots must declare semantic, market and beast")

    authority_roots = tuple(_repo_relative_path(root) for root in cfg["authority_roots"])

    overlap = set(authority_roots) & {root for roots in state_roots.values() for root in roots}
    if overlap:
        raise NativeBindingError(f"authority roots overlap adaptive state roots: {sorted(map(str, overlap))}")

    adaptation_commands = []
    for episode in cfg["adaptation_episodes"]:
        for command in episode["commands"]:
            adaptation_commands.append(
                _validate_command(
                    label=command["label"],
                    argv=command["argv"],
                    command_group=episode["episode_id"],
                    factor_pressure=episode["factor_pressure"],
                    repo_root=repo_root,
                )
            )

    transfer_commands = []
    for command in cfg["transfer_executors"]:
        transfer_commands.append(
            _validate_command(
                label=command["label"],
                argv=command["argv"],
                command_group="transfer",
                repo_root=repo_root,
            )
        )

    return NativeBindings(
        binding_version=cfg["binding_version"],
        adaptation_commands=tuple(adaptation_commands),
        transfer_commands=tuple(transfer_commands),
        state_roots=state_roots,
        authority_roots=authority_roots,
    )


def validate_native_bindings(
    config_path: Path = CONFIG_PATH,
    repo_root: Path = Path("."),
) -> dict:
    bindings = load_native_bindings(config_path=config_path, repo_root=repo_root)

    return {
        "binding_version": bindings.binding_version,
        "adaptation_commands": len(bindings.adaptation_commands),
        "transfer_commands": len(bindings.transfer_commands),
        "state_roots": {k: [str(v) for v in roots] for k, roots in bindings.state_roots.items()},
        "authority_roots": [str(root) for root in bindings.authority_roots],
        "status": "NATIVE_BINDINGS_VALID",
    }
