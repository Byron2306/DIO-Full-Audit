#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def python_for_core(core: Path) -> str:
    for candidate in (core / ".venv" / "bin" / "python", core / "venv" / "bin" / "python"):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable or "python3"


def run(command: list[str], *, cwd: Path) -> int:
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=str(cwd), check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DIO Fusion Wave 5 Vertical Capability Executor acceptance.")
    parser.add_argument("--workspace", default="/home/byron/DIO")
    parser.add_argument("--core", default="/home/byron/DIO-Core")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    py = python_for_core(core)

    wave4_path = workspace / "receipts" / "fusion-wave4-latest.json"
    if not wave4_path.is_file():
        print("REFUSE fusion5: Fusion Wave 4 receipt is missing. Run the Wave 4 acceptance first.")
        return 2
    try:
        wave4 = json.loads(wave4_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSE fusion5: invalid Fusion Wave 4 receipt: {exc}")
        return 2
    if wave4.get("state") != "FUSION_WAVE4_READY":
        print(f"REFUSE fusion5: Fusion Wave 4 state is {wave4.get('state')!r}, expected FUSION_WAVE4_READY.")
        return 2

    rc = run(
        [
            py,
            "-m",
            "py_compile",
            "executors/vertical.py",
            "scripts/check_fusion_wave5.py",
            "scripts/run_fusion_wave5.py",
        ],
        cwd=core,
    )
    if rc:
        return rc

    schema_check = (
        "import json; from pathlib import Path; from jsonschema import Draft202012Validator; "
        "s=json.loads(Path('schemas/dio_vertical_executors.schema.json').read_text()); "
        "p=json.loads(Path('config/dio_vertical_executors.json').read_text()); "
        "Draft202012Validator.check_schema(s); Draft202012Validator(s).validate(p); "
        "print('PASS vertical executor registry schema')"
    )
    rc = run([py, "-c", schema_check], cwd=core)
    if rc:
        return rc

    rc = run([py, "-m", "pytest", "-q", "tests/test_vertical_executors.py"], cwd=core)
    if rc:
        print("\nFusion Wave 5 blocked by Vertical Capability Executor invariants.")
        return rc

    out = workspace / "receipts" / "fusion-wave5-latest.json"
    return run(
        [
            py,
            str(core / "scripts" / "check_fusion_wave5.py"),
            "--workspace",
            str(workspace),
            "--core",
            str(core),
            "--out",
            str(out),
        ],
        cwd=core,
    )


if __name__ == "__main__":
    raise SystemExit(main())
