#!/usr/bin/env python3
"""Execute or dry-run the ARDA artifact-emission workspace commands."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_SUMMARY = DISTRIBUTION_DIR / "build" / "artifact-workspace" / "plans" / "artifact-workspace-summary.json"
DEFAULT_OUTPUT = DISTRIBUTION_DIR / "build" / "artifact-workspace" / "plans" / "artifact-workspace-run-report.json"
RUN_ORDER = [
    "pack_rootfs",
    "make_live_rootfs",
    "make_esp_image",
    "emit_raw_disk",
    "emit_live_iso",
    "emit_installer_iso",
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _persist_payload(payload: dict, output_path: Path, fallback_root: Path) -> dict:
    report = dict(payload)
    attempts = [output_path]
    fallback_path = fallback_root / "plans" / "artifact-workspace-run-report.autosave.json"
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


def _expected_output_path(step: str, command: list[str]) -> Path | None:
    if step == "make_live_rootfs" and len(command) >= 3:
        return Path(command[2])
    if step == "emit_raw_disk" and len(command) >= 5:
        return Path(command[4])
    if step in {"emit_live_iso", "emit_installer_iso"}:
        if "-o" in command:
            index = command.index("-o")
            if index + 1 < len(command):
                return Path(command[index + 1])
        if len(command) >= 4:
            return Path(command[-1])
    return None


def execute_artifact_workspace(
    *,
    summary_path: Path,
    output_path: Path,
    execute: bool,
    start_at: str | None,
    stop_after: str | None,
) -> dict:
    summary = _read_json(summary_path)
    artifact_workspace_root = Path(summary["artifact_workspace_root"])
    commands = dict(summary.get("build_commands") or {})
    blockers = list(summary.get("blockers") or [])

    if execute and blockers:
        payload = {
            "schema_version": "arda.distribution.artifact_workspace_run.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifact_workspace_root": str(artifact_workspace_root),
            "summary_path": str(summary_path),
            "execute": execute,
            "selected_order": [],
            "ok": False,
            "blockers": blockers,
            "steps": [],
        }
        return _persist_payload(payload, output_path, artifact_workspace_root)

    selected_order = list(RUN_ORDER)
    if start_at:
        selected_order = selected_order[selected_order.index(start_at):]
    if stop_after:
        selected_order = selected_order[: selected_order.index(stop_after) + 1]

    results = []
    overall_ok = True
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
            results.append(step_payload)
            if execute:
                break
            continue

        if execute:
            completed = subprocess.run(
                command,
                cwd=artifact_workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )
            step_payload["executed"] = True
            step_payload["returncode"] = completed.returncode
            step_payload["stdout"] = completed.stdout
            step_payload["stderr"] = completed.stderr
            step_payload["ok"] = completed.returncode == 0
            expected_output = _expected_output_path(step, command)
            if step_payload["ok"] and expected_output is not None and not expected_output.exists():
                step_payload["ok"] = False
                step_payload["stderr"] = (
                    (step_payload["stderr"] + "\n") if step_payload["stderr"] else ""
                ) + f"expected_output_missing: {expected_output}"
            if completed.returncode != 0:
                overall_ok = False
                results.append(step_payload)
                break
            if not step_payload["ok"]:
                overall_ok = False
                results.append(step_payload)
                break
        results.append(step_payload)

    payload = {
        "schema_version": "arda.distribution.artifact_workspace_run.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_workspace_root": str(artifact_workspace_root),
        "summary_path": str(summary_path),
        "execute": execute,
        "selected_order": selected_order,
        "ok": overall_ok,
        "blockers": blockers,
        "steps": results,
    }
    return _persist_payload(payload, output_path, artifact_workspace_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or dry-run the ARDA artifact-emission workspace")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--start-at", choices=RUN_ORDER)
    parser.add_argument("--stop-after", choices=RUN_ORDER)
    args = parser.parse_args()

    payload = execute_artifact_workspace(
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
