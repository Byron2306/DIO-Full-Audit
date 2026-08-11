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
    parser = argparse.ArgumentParser(description="Run DIO Fusion Wave 6 Cross-Organ Composition acceptance.")
    parser.add_argument("--workspace", default="/home/byron/DIO")
    parser.add_argument("--core", default="/home/byron/DIO-Core")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    py = python_for_core(core)

    wave5_path = workspace / "receipts" / "fusion-wave5-latest.json"
    if not wave5_path.is_file():
        print("REFUSE fusion6: Fusion Wave 5 receipt is missing. Run Fusion Wave 5 first.")
        return 2
    try:
        wave5 = json.loads(wave5_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSE fusion6: invalid Fusion Wave 5 receipt: {exc}")
        return 2
    if wave5.get("state") != "FUSION_WAVE5_READY":
        print(f"REFUSE fusion6: Fusion Wave 5 state is {wave5.get('state')!r}, expected FUSION_WAVE5_READY.")
        return 2

    rc = run(
        [
            py,
            "-m",
            "py_compile",
            "composition/orchestrator.py",
            "composition/case_bridge.py",
            "scripts/check_fusion_wave6.py",
            "scripts/run_fusion_wave6.py",
        ],
        cwd=core,
    )
    if rc:
        return rc

    validation = (
        "import json; from pathlib import Path; from jsonschema import Draft202012Validator; "
        "s=json.loads(Path('schemas/dio_composition_profiles.schema.json').read_text()); "
        "p=json.loads(Path('config/dio_composition_profiles.json').read_text()); "
        "Draft202012Validator.check_schema(s); Draft202012Validator(s).validate(p); "
        "print('PASS cross-organ composition profile schema')"
    )
    rc = run([py, "-c", validation], cwd=core)
    if rc:
        return rc

    rc = run([py, "-m", "pytest", "-q", "tests/test_cross_organ_composition.py"], cwd=core)
    if rc:
        print("\nFusion Wave 6 blocked by Cross-Organ Composition invariants.")
        return rc

    out = workspace / "receipts" / "fusion-wave6-latest.json"
    return run(
        [py, str(core / "scripts" / "check_fusion_wave6.py"), "--workspace", str(workspace), "--core", str(core), "--out", str(out)],
        cwd=core,
    )


if __name__ == "__main__":
    raise SystemExit(main())
