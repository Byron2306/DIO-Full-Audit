#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
CORE_ROOT = HERE.parents[1]
PHASE1_TESTS = [
    "tests/test_product_portfolio.py",
    "tests/test_governed_case_v2.py",
    "tests/test_case_migration.py",
    "tests/test_system_snapshot.py",
    "tests/test_unified_workspace.py",
]


def load_manifest(workspace: Path) -> dict[str, Any]:
    path = workspace / "WORKSPACE.json"
    if not path.is_file():
        raise RuntimeError(f"Unified DIO workspace manifest not found: {path}. Run scripts/build_unified_dio_workspace.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def python_for_core(core: Path) -> str:
    candidates = [core / ".venv" / "bin" / "python", core / "venv" / "bin" / "python"]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable or "python3"


def run(command: list[str], *, cwd: Path) -> int:
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=str(cwd), check=False).returncode


def status(workspace: Path, manifest: dict[str, Any]) -> int:
    print(f"DIO workspace: {workspace}")
    print(f"Workspace state: {manifest.get('state')}")
    print()
    width = max(len(str(item.get("alias", ""))) for item in manifest.get("mounts") or [])
    for item in manifest.get("mounts") or []:
        alias = str(item.get("alias", "")).ljust(width)
        state = item.get("state")
        target = item.get("target") or "UNRESOLVED"
        suffix = " [required]" if item.get("required_for_phase0") else ""
        print(f"{alias}  {state:10}  {target}{suffix}")
    if manifest.get("required_missing"):
        print("\nPhase 0 blockers: " + ", ".join(manifest["required_missing"]))
        return 2
    return 0


def phase0(workspace: Path, core: Path, manifest: dict[str, Any]) -> int:
    if manifest.get("required_missing"):
        status(workspace, manifest)
        print("\nREFUSE phase0: required workspace sources are unresolved.")
        return 2
    py = python_for_core(core)
    out = workspace / "state" / "system_snapshots" / "latest.json"
    command = [
        py,
        str(core / "scripts" / "capture_system_snapshot.py"),
        "--workspace",
        str(workspace),
        "--out",
        str(out),
        "--require-ready",
    ]
    return run(command, cwd=core)


def phase1(core: Path) -> int:
    py = python_for_core(core)
    compile_targets = [
        "products/registry.py",
        "products/governed_case.py",
        "products/case_migration.py",
        "scripts/capture_system_snapshot.py",
        "scripts/build_unified_dio_workspace.py",
        "scripts/dio_workspace.py",
    ]
    rc = run([py, "-m", "py_compile", *compile_targets], cwd=core)
    if rc:
        return rc
    probe = subprocess.run([py, "-c", "import pytest"], cwd=str(core), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode:
        print("REFUSE phase1: pytest is not installed for this Python. Install it in the DIO core environment first.")
        return 3
    return run([py, "-m", "pytest", "-q", *PHASE1_TESTS], cwd=core)


def doctor(workspace: Path, core: Path, manifest: dict[str, Any]) -> int:
    rc = status(workspace, manifest)
    py = python_for_core(core)
    print(f"\nCore: {core}")
    print(f"Python: {py}")
    print(f"Phase 0 snapshot: {workspace / 'state' / 'system_snapshots' / 'latest.json'}")
    pytest_ok = subprocess.run([py, "-c", "import pytest"], cwd=str(core), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    print(f"pytest: {'available' if pytest_ok else 'missing'}")
    return rc if rc else (0 if pytest_ok else 3)


def main() -> int:
    parser = argparse.ArgumentParser(description="One command surface for the unified DIO workspace.")
    parser.add_argument("--workspace-root", default=os.environ.get("DIO_WORKSPACE_ROOT", "/home/byron/DIO"))
    parser.add_argument("command", choices=["status", "doctor", "phase0", "phase1", "phase01"])
    args = parser.parse_args()

    workspace = Path(args.workspace_root).expanduser().resolve()
    manifest = load_manifest(workspace)
    core = (workspace / "core").resolve()
    if core != CORE_ROOT.resolve():
        print(f"NOTICE: launcher core resolves to {core}; script source is {CORE_ROOT.resolve()}.")

    if args.command == "status":
        return status(workspace, manifest)
    if args.command == "doctor":
        return doctor(workspace, core, manifest)
    if args.command == "phase0":
        return phase0(workspace, core, manifest)
    if args.command == "phase1":
        return phase1(core)
    if args.command == "phase01":
        rc = phase0(workspace, core, manifest)
        if rc:
            print("\nPhase 1 not started because Phase 0 did not earn READY.")
            return rc
        return phase1(core)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
