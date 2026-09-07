import json
import subprocess
import sys
from pathlib import Path


def test_native_compatibility_runner_writes_summary(tmp_path):
    receipt = tmp_path / "native_execution_receipt.json"
    output = tmp_path / "native_compatibility_summary.json"

    receipt.write_text(json.dumps({
        "adaptive_claim_authorized": False,
        "command_results": [
            {"label": "fast", "exit_code": 0, "refusal_reason": None},
            {"label": "long", "exit_code": 124, "refusal_reason": "Command timed out after 20 seconds."},
        ],
    }))

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_native_compatibility.py",
            "--receipt",
            str(receipt),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "DIO_METAMORPHIC_ADAPTATION_NATIVE_COMPATIBILITY_CLASSIFIED" in completed.stdout
    assert output.exists()

    data = json.loads(output.read_text())
    assert data["compatible_fast"] == 1
    assert data["compatible_long_running"] == 1
    assert data["failed_runtime"] == 0
    assert data["adaptive_claim_authorized"] is False
