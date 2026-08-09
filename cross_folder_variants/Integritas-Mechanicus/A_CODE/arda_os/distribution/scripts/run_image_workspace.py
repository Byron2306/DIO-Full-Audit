#!/usr/bin/env python3
"""Execute or dry-run the ARDA image workspace build commands."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
from subprocess import TimeoutExpired
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_WORKSPACE = DISTRIBUTION_DIR / "build" / "workspace"
DEFAULT_SUMMARY = DEFAULT_WORKSPACE / "plans" / "workspace-summary.json"
DEFAULT_OUTPUT = DEFAULT_WORKSPACE / "plans" / "workspace-run-report.json"

RUN_ORDER = [
    "debootstrap",
    "apply_overlay",
    "install_packages",
    "install_kernel",
    "generate_initramfs",
    "enable_units",
]

STEP_TIMEOUTS_SECONDS = {
    "debootstrap": 45 * 60,
    "apply_overlay": 10 * 60,
    "install_packages": 75 * 60,
    "install_kernel": 25 * 60,
    "generate_initramfs": 25 * 60,
    "enable_units": 10 * 60,
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _persist_payload(payload: dict, output_path: Path, fallback_root: Path) -> dict:
    report = dict(payload)
    attempts = [output_path]
    fallback_path = fallback_root / "plans" / "workspace-run-report.autosave.json"
    if fallback_path != output_path:
        attempts.append(fallback_path)

    errors: list[str] = []
    for candidate in attempts:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report["report_path"] = str(candidate)
            if errors:
                report["report_write_warnings"] = errors
            return report
        except OSError as exc:
            errors.append(f"{candidate}: {exc}")

    report["report_path"] = None
    report["report_write_warnings"] = errors
    return report


def _command_display(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _command_available(command: list[str]) -> bool:
    if not command:
        return False
    program = command[0]
    if "/" in program:
        return Path(program).exists()
    return shutil.which(program) is not None


def _ensure_workspace_artifact_copy(workspace_root: Path, rootfs_dir: Path) -> Path:
    target = rootfs_dir / "workspace-artifacts"
    source = workspace_root / "artifacts"
    if target.is_symlink():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, symlinks=True)
    return target


def execute_workspace(
    *,
    summary_path: Path,
    output_path: Path,
    execute: bool,
    start_at: str | None,
    stop_after: str | None,
) -> dict:
    summary = _read_json(summary_path)
    workspace_root = Path(summary["workspace_root"])
    rootfs_dir = Path(summary["rootfs_dir"])
    commands = dict(summary.get("build_commands") or {})
    prerequisites = dict(summary.get("host_prerequisites") or {})

    selected_order = list(RUN_ORDER)
    if start_at:
        selected_order = selected_order[selected_order.index(start_at):]
    if stop_after:
        selected_order = selected_order[: selected_order.index(stop_after) + 1]

    if execute:
        rootfs_dir.mkdir(parents=True, exist_ok=True)
        _ensure_workspace_artifact_copy(workspace_root, rootfs_dir)

    results = []
    overall_ok = True
    missing_commands: list[str] = []
    for step in selected_order:
        command = list(commands.get(step) or [])
        available = _command_available(command)
        step_payload = {
            "step": step,
            "command": command,
            "display": _command_display(command),
            "command_available": available,
            "executed": False,
            "ok": available,
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }
        if not available:
            overall_ok = False
            if command:
                missing_commands.append(command[0])
            results.append(step_payload)
            if execute:
                break
            continue

        if execute:
            try:
                completed = subprocess.run(
                    command,
                    cwd=workspace_root,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=STEP_TIMEOUTS_SECONDS.get(step),
                )
            except TimeoutExpired as exc:
                step_payload["executed"] = True
                step_payload["returncode"] = 124
                step_payload["stdout"] = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
                step_payload["stderr"] = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
                step_payload["ok"] = False
                step_payload["timed_out"] = True
                step_payload["timeout_seconds"] = STEP_TIMEOUTS_SECONDS.get(step)
                overall_ok = False
                results.append(step_payload)
                break
            step_payload["executed"] = True
            step_payload["returncode"] = completed.returncode
            step_payload["stdout"] = completed.stdout
            step_payload["stderr"] = completed.stderr
            step_payload["ok"] = completed.returncode == 0
            if completed.returncode != 0:
                overall_ok = False
                results.append(step_payload)
                break
        results.append(step_payload)

    payload = {
        "schema_version": "arda.distribution.workspace_run.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(workspace_root),
        "rootfs_dir": str(rootfs_dir),
        "summary_path": str(summary_path),
        "execute": execute,
        "selected_order": selected_order,
        "ok": overall_ok,
        "host_prerequisites": prerequisites,
        "missing_commands": sorted(dict.fromkeys(missing_commands)),
        "next_actions": [
            "install missing host tools before rerunning --execute"
            if missing_commands
            else "workspace prerequisites satisfied for the selected steps"
        ],
        "steps": results,
    }
    return _persist_payload(payload, output_path, workspace_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or dry-run the ARDA image workspace")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--start-at", choices=RUN_ORDER)
    parser.add_argument("--stop-after", choices=RUN_ORDER)
    args = parser.parse_args()

    payload = execute_workspace(
        summary_path=Path(args.summary),
        output_path=Path(args.output),
        execute=args.execute,
        start_at=args.start_at,
        stop_after=args.stop_after,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not args.execute:
        return 0
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
