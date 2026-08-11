#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
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
    "tests/test_document_conversion.py",
    "tests/test_legalis.py",
]
INCARNATION_TESTS = [
    "tests/test_presence_authority.py",
    "tests/test_presence_vesper.py",
    "tests/test_seraph_challenge.py",
    "tests/test_fusion_registry.py",
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
    command = [py, str(core / "scripts" / "capture_system_snapshot.py"), "--workspace", str(workspace), "--out", str(out), "--require-ready"]
    return run(command, cwd=core)


def phase1(core: Path) -> int:
    py = python_for_core(core)
    compile_targets = [
        "products/registry.py",
        "products/governed_case.py",
        "products/case_migration.py",
        "adapters/document_studio/conversion.py",
        "adapters/legalis/service.py",
        "adapters/legalis/valinor_bridge.py",
        "adapters/seraph/challenge.py",
        "presence_core/authority.py",
        "scripts/convert_document.py",
        "scripts/manage_legalis.py",
        "scripts/capture_system_snapshot.py",
        "scripts/build_unified_dio_workspace.py",
        "scripts/check_incarnation.py",
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


def incarnation(workspace: Path, core: Path) -> int:
    """Run Phase 1, then the Presence/Challenge/Fusion inventory gate."""
    py = python_for_core(core)
    rc = phase1(core)
    if rc:
        print("\nIncarnation not started because Phase 1 did not pass.")
        return rc
    rc = run([py, "-m", "pytest", "-q", *INCARNATION_TESTS], cwd=core)
    if rc:
        print("\nIncarnation blocked by Presence, Seraph or fusion-inventory tests.")
        return rc
    out = workspace / "receipts" / "incarnation-latest.json"
    return run(
        [py, str(core / "scripts" / "check_incarnation.py"), "--workspace", str(workspace), "--core", str(core), "--out", str(out)],
        cwd=core,
    )


def _binary_state(name: str) -> str:
    return shutil.which(name) or "missing"


def doctor(workspace: Path, core: Path, manifest: dict[str, Any]) -> int:
    rc = status(workspace, manifest)
    py = python_for_core(core)
    print(f"\nCore: {core}")
    print(f"Python: {py}")
    print(f"Phase 0 snapshot: {workspace / 'state' / 'system_snapshots' / 'latest.json'}")
    print(f"Incarnation receipt: {workspace / 'receipts' / 'incarnation-latest.json'}")
    pytest_ok = subprocess.run([py, "-c", "import pytest"], cwd=str(core), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    print(f"pytest: {'available' if pytest_ok else 'missing'}")
    valinor_hooks = workspace / "organs" / "sophia" / "arda_os" / "backend" / "valinor" / "runtime_hooks.py"
    legalis_service = workspace / "organs" / "legalis" / "service.py"
    seraph_contract = core / "adapters" / "seraph" / "challenge.py"
    vesper_authority = core / "presence_core" / "authority.py"
    print("\nGovernance runtime:")
    print(f"  Valinor kernel runtime: {'available' if valinor_hooks.is_file() else 'missing/unmounted'}")
    print(f"  DIO Legalis organ: {'available' if legalis_service.is_file() else 'missing/unmounted'}")
    print(f"  Seraph challenge contract: {'available' if seraph_contract.is_file() else 'missing'}")
    print(f"  Vesper Presence authority: {'available' if vesper_authority.is_file() else 'missing'}")
    print("\nTransformation tools (optional, route-specific):")
    for binary in ("node", "ffmpeg", "ffprobe", "libreoffice", "soffice", "pandoc", "pdftotext"):
        print(f"  {binary}: {_binary_state(binary)}")
    media_script = workspace / "organs" / "nichefoundry" / "scripts" / "media_transform.js"
    print(f"  nichefoundry media transform: {'available' if media_script.is_file() else 'missing/unmounted'}")
    return rc if rc else (0 if pytest_ok else 3)


def convert_document(core: Path, operands: list[str], *, dry_run: bool, force: bool) -> int:
    if len(operands) != 2:
        print("REFUSE convert-doc: expected SOURCE OUTPUT.")
        return 2
    py = python_for_core(core)
    command = [py, str(core / "scripts" / "convert_document.py"), operands[0], operands[1]]
    if dry_run:
        command.append("--dry-run")
    if force:
        command.append("--force")
    return run(command, cwd=core)


def legalis(workspace: Path, core: Path, operands: list[str], *, dry_run: bool, authorize_valinor: bool) -> int:
    if len(operands) != 1:
        print("REFUSE legalis: expected REQUEST.json.")
        return 2
    py = python_for_core(core)
    command = [py, str(core / "scripts" / "manage_legalis.py"), operands[0], "--workspace-root", str(workspace)]
    if dry_run:
        command.append("--dry-run")
    if authorize_valinor:
        command.append("--authorize-valinor")
    return run(command, cwd=core)


def media_transform(workspace: Path, kind: str, operands: list[str], *, media_root: str | None, dry_run: bool) -> int:
    if len(operands) != 1:
        print(f"REFUSE {'convert-image' if kind == 'image' else 'edit-video'}: expected REQUEST.json.")
        return 2
    request_path = Path(operands[0]).expanduser().resolve()
    if not request_path.is_file():
        print(f"REFUSE media transform: request file not found: {request_path}")
        return 2
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSE media transform: invalid request JSON: {exc}")
        return 2
    if str(request.get("kind") or "").casefold() != kind:
        print(f"REFUSE media transform: request kind must be {kind!r} for this command.")
        return 2
    media_org = workspace / "organs" / "nichefoundry"
    script = media_org / "scripts" / "media_transform.js"
    if not script.is_file():
        print("REFUSE media transform: NicheFoundry media organ is not mounted with the transformation engine.")
        print("Expected: " + str(script))
        return 3
    node = shutil.which("node")
    if not node:
        print("REFUSE media transform: Node.js is not installed or not on PATH.")
        return 3
    root = Path(media_root).expanduser().resolve() if media_root else Path.cwd().resolve()
    command = [node, str(script), "--workspace", str(root), "--request", str(request_path)]
    if dry_run:
        command.append("--dry-run")
    return run(command, cwd=media_org)


def main() -> int:
    parser = argparse.ArgumentParser(description="One command surface for the unified DIO workspace.")
    parser.add_argument("--workspace-root", default=os.environ.get("DIO_WORKSPACE_ROOT", "/home/byron/DIO"))
    parser.add_argument("command", choices=["status", "doctor", "phase0", "phase1", "phase01", "incarnation", "legalis", "convert-doc", "convert-image", "edit-video"])
    parser.add_argument("operands", nargs="*")
    parser.add_argument("--dry-run", action="store_true", help="Plan/evaluate without writing a transform or Legalis receipt.")
    parser.add_argument("--force", action="store_true", help="Allow Document Studio to replace an existing conversion output.")
    parser.add_argument("--authorize-valinor", action="store_true", help="For Legalis, request bounded Valinor runtime authorization after ALLOW.")
    parser.add_argument("--media-root", help="Root containing media input/output paths referenced by a media request; defaults to the current directory.")
    args = parser.parse_args()

    workspace = Path(args.workspace_root).expanduser().resolve()
    manifest = load_manifest(workspace)
    core = (workspace / "core").resolve()
    if core != CORE_ROOT.resolve():
        print(f"NOTICE: launcher core resolves to {core}; script source is {CORE_ROOT.resolve()}.")

    if args.command == "status": return status(workspace, manifest)
    if args.command == "doctor": return doctor(workspace, core, manifest)
    if args.command == "phase0": return phase0(workspace, core, manifest)
    if args.command == "phase1": return phase1(core)
    if args.command == "phase01":
        rc = phase0(workspace, core, manifest)
        if rc:
            print("\nPhase 1 not started because Phase 0 did not earn READY.")
            return rc
        return phase1(core)
    if args.command == "incarnation": return incarnation(workspace, core)
    if args.command == "legalis": return legalis(workspace, core, args.operands, dry_run=args.dry_run, authorize_valinor=args.authorize_valinor)
    if args.command == "convert-doc": return convert_document(core, args.operands, dry_run=args.dry_run, force=args.force)
    if args.command == "convert-image": return media_transform(workspace, "image", args.operands, media_root=args.media_root, dry_run=args.dry_run)
    if args.command == "edit-video": return media_transform(workspace, "video", args.operands, media_root=args.media_root, dry_run=args.dry_run)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
