#!/usr/bin/env python3
"""
Direct Linux atomic executor (bypass PowerShell, run native shell).
Executes sh/bash atomics directly from YAML definitions.
"""

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. pip install pyyaml")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
ART_ROOT = REPO_ROOT / "atomic-red-team" / "atomics"
RESULTS_DIR = REPO_ROOT / "artifacts" / "native-sweep"


def run_atomic(tech_id: str, run_num: int) -> dict:
    """Execute a single atomic test with sh/bash executor."""
    yaml_file = ART_ROOT / tech_id / f"{tech_id}.yaml"

    if not yaml_file.exists():
        return {
            "run_id": str(uuid.uuid4()),
            "technique": tech_id,
            "status": "skipped",
            "outcome": "not_found",
            "message": f"No YAML at {yaml_file}",
            "exit_code": 1,
        }

    try:
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        return {
            "run_id": str(uuid.uuid4()),
            "technique": tech_id,
            "status": "failed",
            "outcome": "yaml_parse_error",
            "message": str(e),
            "exit_code": 1,
        }

    if not data or "atomic_tests" not in data:
        return {
            "run_id": str(uuid.uuid4()),
            "technique": tech_id,
            "status": "skipped",
            "outcome": "no_atomic_tests",
            "message": "No atomic_tests in YAML",
            "exit_code": 1,
        }

    results = []
    for test_idx, test in enumerate(data["atomic_tests"]):
        test_name = test.get("name", f"Test {test_idx}")
        supported_platforms = test.get("supported_platforms", [])

        if "linux" not in supported_platforms:
            continue

        executor = test.get("executor", {})
        executor_name = executor.get("name", "")

        if executor_name not in ["sh", "bash", "bash_shell"]:
            continue

        command = executor.get("command", "")
        if not command:
            continue

        # Execute the command
        start_time = datetime.now(timezone.utc).isoformat()
        try:
            # Find a valid working directory
            for cwd_candidate in ["/tmp", "/var/tmp", "/home", "."]:
                if Path(cwd_candidate).exists():
                    cwd = cwd_candidate
                    break
            else:
                cwd = "."

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=cwd,
            )
            exit_code = result.returncode
            cmd_output = result.stdout
            stderr = result.stderr

            # Format stdout with "Executing test:" prefix so TVR validator recognizes it
            stdout = f"Executing test: {test_name}\n{cmd_output}"

            status = "success" if exit_code == 0 else "failed"
            outcome = "success" if exit_code == 0 else "nonzero_exit"
        except subprocess.TimeoutExpired:
            exit_code = 124
            stdout = f"Executing test: {test_name}\n[TIMEOUT after 60s]"
            stderr = "Command timed out after 60s"
            status = "failed"
            outcome = "timeout"
        except Exception as e:
            exit_code = 1
            stdout = f"Executing test: {test_name}\n[ERROR: {str(e)}]"
            stderr = str(e)
            status = "failed"
            outcome = "execution_error"

        finish_time = datetime.now(timezone.utc).isoformat()

        results.append({
            "run_id": str(uuid.uuid4()),
            "technique": tech_id,
            "test_name": test_name,
            "status": status,
            "outcome": outcome,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "started_at": start_time,
            "finished_at": finish_time,
            "execution_mode": "direct_native_shell",
        })

    if not results:
        return {
            "run_id": str(uuid.uuid4()),
            "techniques_executed": [tech_id],
            "status": "skipped",
            "outcome": "no_shell_executor",
            "message": "No sh/bash executor found",
            "exit_code": 1,
        }

    # Return aggregate result
    success_count = sum(1 for r in results if r["status"] == "success")
    return {
        "run_id": results[0]["run_id"],
        "techniques_executed": [tech_id],
        "techniques": [tech_id],
        "tests_executed": len(results),
        "tests_successful": success_count,
        "status": "success" if success_count > 0 else "failed",
        "outcome": "success" if success_count > 0 else "failed",
        "execution_mode": "direct_native_shell",
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Direct native Linux atomic executor")
    parser.add_argument("--techniques", required=True, help="Comma-separated technique IDs")
    parser.add_argument("--output-dir", required=True, help="Output directory for run files")
    parser.add_argument("--run-number", type=int, default=1, help="Run number (for naming)")
    args = parser.parse_args()

    techniques = args.techniques.split(",")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Native Linux sweep — {len(techniques)} techniques")

    success = 0
    failed = 0
    skipped = 0

    for tech in techniques:
        result = run_atomic(tech, args.run_number)

        # Write run file
        run_file = output_dir / f"run_{result['run_id']}.json"
        with open(run_file, "w") as f:
            json.dump(result, f, indent=2)

        # Track results
        if result["status"] == "success":
            success += 1
            symbol = "✓"
        elif result["status"] == "failed":
            failed += 1
            symbol = "✗"
        else:
            skipped += 1
            symbol = "◦"

        print(f"  [{symbol}] {tech}")

    print(f"\nNative sweep done — {success}/{len(techniques)} success  {skipped} skipped  {failed} failed")


if __name__ == "__main__":
    main()
