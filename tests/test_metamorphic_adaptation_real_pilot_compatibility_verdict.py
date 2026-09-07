import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_pilot_compatibility_verdict import (
    REAL_PILOT_COMPATIBILITY_READY_TOKEN,
    REAL_PILOT_COMPATIBILITY_REFUSED_TOKEN,
    REAL_PILOT_COMPATIBILITY_VERSION,
    evaluate_real_pilot_compatibility,
    write_real_pilot_compatibility_verdict,
)


def _write_execution_bundle(tmp_path, *, passed=5, failed=0, timed_out=0, executed=5):
    receipt = tmp_path / "real_pilot_execution_receipt.json"
    receipts = tmp_path / "real_pilot_execution_receipts.jsonl"

    receipt.write_text(json.dumps({
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_EXECUTION_READY",
        "executed": True,
        "real_native_mode": True,
        "pilot_encounters_loaded": 5,
        "pilot_encounters_executed": executed,
        "pilot_encounters_passed": passed,
        "pilot_encounters_failed": failed,
        "pilot_encounters_timed_out": timed_out,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))

    with receipts.open("w") as fh:
        for index in range(1, executed + 1):
            status = "REAL_PILOT_NATIVE_PASSED"
            exit_code = 0
            if failed and index == executed:
                status = "REAL_PILOT_NATIVE_FAILED"
                exit_code = 1
            if timed_out and index == executed:
                status = "REAL_PILOT_NATIVE_TIMED_OUT"
                exit_code = 124

            fh.write(json.dumps({
                "blind_id": f"REAL-PILOT-BLIND-{index:04d}",
                "arm": "A_STATELESS_RESET",
                "encounter_index": 1,
                "status": status,
                "executed": True,
                "real_native_mode": True,
                "exit_code": exit_code,
                "stdout_sha256": "a" * 64,
                "stderr_sha256": "b" * 64,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }, sort_keys=True) + "\n")

    return receipt, receipts


def test_real_pilot_compatibility_verdict_accepts_clean_five_of_five(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path)

    verdict = evaluate_real_pilot_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    assert verdict.verdict_version == REAL_PILOT_COMPATIBILITY_VERSION
    assert verdict.status == REAL_PILOT_COMPATIBILITY_READY_TOKEN
    assert verdict.real_pilot_native_compatibility_proven is True
    assert verdict.ready_for_real_blind_evaluation is True
    assert verdict.pilot_encounters_passed == 5
    assert verdict.pilot_encounters_failed == 0
    assert verdict.pilot_encounters_timed_out == 0
    assert verdict.adaptive_claim_authorized is False
    assert verdict.commercial_or_world_first_claim_authorized is False


def test_real_pilot_compatibility_verdict_refuses_failures(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path, passed=4, failed=1)

    verdict = evaluate_real_pilot_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    assert verdict.status == REAL_PILOT_COMPATIBILITY_REFUSED_TOKEN
    assert verdict.real_pilot_native_compatibility_proven is False
    assert verdict.ready_for_real_blind_evaluation is False


def test_real_pilot_compatibility_verdict_refuses_timeouts(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path, passed=4, timed_out=1)

    verdict = evaluate_real_pilot_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    assert verdict.status == REAL_PILOT_COMPATIBILITY_REFUSED_TOKEN
    assert verdict.real_pilot_native_compatibility_proven is False
    assert verdict.ready_for_real_blind_evaluation is False


def test_real_pilot_compatibility_verdict_writes_json_and_hashes_sources(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path)
    output = tmp_path / "real_pilot_compatibility_verdict.json"

    verdict = write_real_pilot_compatibility_verdict(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(verdict)))
    assert len(data["execution_receipt_sha256"]) == 64
    assert len(data["execution_receipts_sha256"]) == 64


def test_real_pilot_compatibility_verdict_boundary_blocks_overclaiming(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path)

    verdict = evaluate_real_pilot_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    boundary = verdict.boundary.lower()

    assert "limited real native pilot executed compatibly" in boundary
    assert "does not constitute adaptive performance evidence" in boundary
    assert "does not claim improvement" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_real_pilot_compatibility_cli_runner(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path)
    output = tmp_path / "real_pilot_compatibility_verdict.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_pilot_compatibility_verdict.py",
            "--execution-receipt",
            str(receipt_path),
            "--execution-receipts",
            str(receipts_path),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_PILOT_COMPATIBILITY_READY_TOKEN in completed.stdout
    assert output.exists()
