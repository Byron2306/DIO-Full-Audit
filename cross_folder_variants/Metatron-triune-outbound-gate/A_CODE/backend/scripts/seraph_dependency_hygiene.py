#!/usr/bin/env python3
"""Dependency hygiene check for Seraph/Arda validation runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    py = str(repo_root / ".venv" / "bin" / "python")

    snippet = r'''
import json, warnings
result = {"warnings": [], "versions": {}}
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    try:
        import oqs
        result["versions"]["oqs_module"] = getattr(oqs, "__name__", "oqs")
    except Exception as exc:
        result["warnings"].append(f"oqs import failed: {exc}")
    for item in w:
        result["warnings"].append(str(item.message))
print(json.dumps(result))
'''

    proc = subprocess.run([py, "-c", snippet], cwd=str(repo_root), capture_output=True, text=True)

    record: Dict[str, Any] = {
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "oqs_mismatch_detected": False,
        "status": "unknown",
    }

    if proc.returncode == 0 and proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception:
            payload = {"warnings": []}

        warnings_list = payload.get("warnings") or []
        mismatch = any(
            "liboqs version" in str(msg) and "differs from liboqs-python" in str(msg)
            for msg in warnings_list
        )
        record["parsed"] = payload
        record["oqs_mismatch_detected"] = mismatch
        record["status"] = "fail" if mismatch else "pass"
    else:
        record["status"] = "fail"

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(json.dumps({"status": record["status"], "output": str(out_path), "oqs_mismatch_detected": record["oqs_mismatch_detected"]}, indent=2))
    return 1 if record["status"] == "fail" else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seraph dependency hygiene check")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument(
        "--output",
        default="backend/scripts/telemetry_logs/seraph_dependency_hygiene_latest.json",
        help="Output path",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
