from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from experiments.metamorphic_adaptation.native_execution_plan import build_native_execution_plan


EXECUTOR_VERSION = "DIO_METAMORPHIC_ADAPTATION_NATIVE_EXECUTOR_V1"
EXECUTOR_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_NATIVE_EXECUTION_REFUSED"
EXECUTOR_COMPLETED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_NATIVE_EXECUTION_COMPLETED"


@dataclass(frozen=True)
class NativeCommandResult:
    label: str
    command_group: str
    started_at_utc: str | None
    ended_at_utc: str | None
    exit_code: int | None
    stdout_sha256: str | None
    stderr_sha256: str | None
    executed: bool
    refusal_reason: str | None


@dataclass(frozen=True)
class NativeExecutionReceipt:
    executor_version: str
    status: str
    plan_path: str
    execute_requested: bool
    command_results: tuple[NativeCommandResult, ...]
    adaptive_claim_authorized: bool
    refusal_boundary: str


def _write_text(path: Path, value: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    return hashlib.sha256(value.encode()).hexdigest()


def execute_native_plan(
    *,
    output_dir: Path,
    execute: bool = False,
    python_executable: str = "python",
    timeout_seconds: int = 120,
) -> NativeExecutionReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    plan = build_native_execution_plan(
        output_dir=output_dir,
        python_executable=python_executable,
    )

    plan_path = output_dir / "native_execution_plan.json"
    plan_path.write_text(json.dumps(asdict(plan), indent=2, sort_keys=True) + "\n")

    results: list[NativeCommandResult] = []

    if not execute:
        for command in plan.planned_commands:
            results.append(
                NativeCommandResult(
                    label=command.label,
                    command_group=command.command_group,
                    started_at_utc=None,
                    ended_at_utc=None,
                    exit_code=None,
                    stdout_sha256=None,
                    stderr_sha256=None,
                    executed=False,
                    refusal_reason="Execution was not requested. Pass --execute to run native commands.",
                )
            )

        receipt = NativeExecutionReceipt(
            executor_version=EXECUTOR_VERSION,
            status=EXECUTOR_REFUSED_TOKEN,
            plan_path=str(plan_path),
            execute_requested=False,
            command_results=tuple(results),
            adaptive_claim_authorized=False,
            refusal_boundary=(
                "The native executor prepared a plan but refused execution because --execute "
                "was not supplied. Refusal is not failure; it preserves the boundary between "
                "planning, execution and adaptive-composition claims."
            ),
        )
        (output_dir / "native_execution_receipt.json").write_text(
            json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n"
        )
        return receipt

    stdout_dir = output_dir / "command_logs"
    repo_root = str(Path(".").resolve())

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = repo_root if not existing_pythonpath else f"{repo_root}:{existing_pythonpath}"

    for index, command in enumerate(plan.planned_commands, start=1):
        started = datetime.now(timezone.utc).isoformat()

        try:
            completed = subprocess.run(
                list(command.resolved_argv),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
                env=env,
                cwd=repo_root,
            )
            ended = datetime.now(timezone.utc).isoformat()
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
            refusal_reason = None

        except subprocess.TimeoutExpired as exc:
            ended = datetime.now(timezone.utc).isoformat()
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")

            stderr = stderr + f"\nNATIVE_COMMAND_TIMEOUT: command exceeded {timeout_seconds} seconds\n"
            exit_code = 124
            refusal_reason = f"Command timed out after {timeout_seconds} seconds."

        stdout_sha = _write_text(
            stdout_dir / f"{index:02d}_{command.label}.stdout.txt",
            stdout,
        )
        stderr_sha = _write_text(
            stdout_dir / f"{index:02d}_{command.label}.stderr.txt",
            stderr,
        )

        results.append(
            NativeCommandResult(
                label=command.label,
                command_group=command.command_group,
                started_at_utc=started,
                ended_at_utc=ended,
                exit_code=exit_code,
                stdout_sha256=stdout_sha,
                stderr_sha256=stderr_sha,
                executed=True,
                refusal_reason=refusal_reason,
            )
        )

    receipt = NativeExecutionReceipt(
        executor_version=EXECUTOR_VERSION,
        status=EXECUTOR_COMPLETED_TOKEN,
        plan_path=str(plan_path),
        execute_requested=True,
        command_results=tuple(results),
        adaptive_claim_authorized=False,
        refusal_boundary=(
            "Native commands were executed and their outputs were hashed, but execution "
            "alone does not authorize an adaptive-composition claim. Claim authorization "
            "requires transfer evaluation, lineage review, blind scoring and factorial analysis."
        ),
    )

    (output_dir / "native_execution_receipt.json").write_text(
        json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n"
    )
    return receipt
