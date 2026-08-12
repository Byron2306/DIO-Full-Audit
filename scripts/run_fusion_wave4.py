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
    parser = argparse.ArgumentParser(description="Run DIO Fusion Wave 4 Authority & Execution Plane acceptance.")
    parser.add_argument("--workspace", default="/home/byron/DIO")
    parser.add_argument("--core", default="/home/byron/DIO-Core")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    py = python_for_core(core)

    wave3_path = workspace / "receipts" / "fusion-wave3-latest.json"
    if not wave3_path.is_file():
        print("REFUSE fusion4: Fusion Wave 3 receipt is missing. Run ./dio fusion3 first.")
        return 2
    try:
        wave3 = json.loads(wave3_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSE fusion4: invalid Fusion Wave 3 receipt: {exc}")
        return 2
    if wave3.get("state") != "FUSION_WAVE3_READY":
        print(f"REFUSE fusion4: Fusion Wave 3 state is {wave3.get('state')!r}, expected FUSION_WAVE3_READY.")
        return 2

    rc = run([py, "-m", "py_compile", "authority/canonical.py", "scripts/check_fusion_wave4.py", "scripts/run_fusion_wave4.py"], cwd=core)
    if rc:
        return rc
    rc = run([py, "-m", "pytest", "-q", "tests/test_authority_execution_plane.py"], cwd=core)
    if rc:
        print("\nFusion Wave 4 blocked by Authority & Execution Plane invariants.")
        return rc

    out = workspace / "receipts" / "fusion-wave4-latest.json"
    return run(
        [py, str(core / "scripts" / "check_fusion_wave4.py"), "--workspace", str(workspace), "--core", str(core), "--out", str(out)],
        cwd=core,
    )


if __name__ == "__main__":
    raise SystemExit(main())
