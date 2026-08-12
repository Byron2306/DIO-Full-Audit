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
    parser = argparse.ArgumentParser(description="Run DIO Fusion Wave 7 Evidence & Authority Twin acceptance.")
    parser.add_argument("--workspace", default="/home/byron/DIO")
    parser.add_argument("--core", default="/home/byron/DIO-Core")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    py = python_for_core(core)

    wave6_path = workspace / "receipts" / "fusion-wave6-latest.json"
    if not wave6_path.is_file():
        print("REFUSE fusion7: Fusion Wave 6 receipt is missing. Run Fusion Wave 6 first.")
        return 2
    try:
        wave6 = json.loads(wave6_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSE fusion7: invalid Fusion Wave 6 receipt: {exc}")
        return 2
    if wave6.get("state") != "FUSION_WAVE6_READY":
        print(f"REFUSE fusion7: Fusion Wave 6 state is {wave6.get('state')!r}, expected FUSION_WAVE6_READY.")
        return 2

    rc = run(
        [
            py,
            "-m",
            "py_compile",
            "twin/canonical.py",
            "twin/loki_mirror.py",
            "scripts/check_fusion_wave7.py",
            "scripts/run_fusion_wave7.py",
        ],
        cwd=core,
    )
    if rc:
        return rc

    validation = (
        "import json; from pathlib import Path; from jsonschema import Draft202012Validator; "
        "s=json.loads(Path('schemas/dio_evidence_authority_twin.schema.json').read_text()); "
        "p=json.loads(Path('config/dio_evidence_authority_twin.json').read_text()); "
        "Draft202012Validator.check_schema(s); Draft202012Validator(s).validate(p); "
        "print('PASS Evidence & Authority Twin config schema')"
    )
    rc = run([py, "-c", validation], cwd=core)
    if rc:
        return rc

    rc = run([py, "-m", "pytest", "-q", "tests/test_evidence_authority_twin.py"], cwd=core)
    if rc:
        print("\nFusion Wave 7 blocked by Evidence & Authority Twin invariants.")
        return rc

    out = workspace / "receipts" / "fusion-wave7-latest.json"
    return run(
        [py, str(core / "scripts" / "check_fusion_wave7.py"), "--workspace", str(workspace), "--core", str(core), "--out", str(out)],
        cwd=core,
    )


if __name__ == "__main__":
    raise SystemExit(main())
