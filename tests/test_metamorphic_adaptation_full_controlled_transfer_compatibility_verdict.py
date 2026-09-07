import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.full_controlled_transfer_compatibility_verdict import (
    FULL_TRANSFER_COMPATIBILITY_READY_TOKEN,
    FULL_TRANSFER_COMPATIBILITY_REFUSED_TOKEN,
    FULL_TRANSFER_COMPATIBILITY_VERSION,
    evaluate_full_transfer_compatibility,
    write_full_transfer_compatibility_verdict,
)


def _write_execution_bundle(tmp_path, *, passed=25, failed=0, timed_out=0, executed=25):
    receipt = tmp_path / "full_controlled_transfer_execution_receipt.json"
    receipts = tmp_path / "full_controlled_transfer_execution_receipts.jsonl"

    receipt.write_text(json.dumps({
        "status": "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_EXECUTION_READY",
        "executed": True,
        "real_native_mode": True,
        "full_run_encounters_loaded": 25,
        "full_run_encounters_executed": executed,
        "full_run_encounters_passed": passed,
        "full_run_encounters_failed": failed,
        "full_run_encounters_timed_out": timed_out,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))

    with receipts.open("w") as fh:
        for index in range(1, executed + 1):
            status = "FULL_CONTROLLED_TRANSFER_NATIVE_PASSED"
            exit_code = 0
            if failed and index == executed:
                status = "FULL_CONTROLLED_TRANSFER_NATIVE_FAILED"
                exit_code = 1
            if timed_out and index == executed:
                status = "FULL_CONTROLLED_TRANSFER_NATIVE_TIMED_OUT"
                exit_code = 124

            fh.write(json.dumps({
                "blind_id": f"FULL-TRANSFER-BLIND-{index:04d}",
                "arm": "A_STATELESS_RESET",
                "encounter_index": index,
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


def test_full_transfer_compatibility_accepts_clean_25_of_25(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path)

    verdict = evaluate_full_transfer_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    assert verdict.verdict_version == FULL_TRANSFER_COMPATIBILITY_VERSION
    assert verdict.status == FULL_TRANSFER_COMPATIBILITY_READY_TOKEN
    assert verdict.full_run_native_compatibility_proven is True
    assert verdict.ready_for_full_blind_evaluation is True
    assert verdict.full_run_encounters_loaded == 25
    assert verdict.full_run_encounters_executed == 25
    assert verdict.full_run_encounters_passed == 25
    assert verdict.full_run_encounters_failed == 0
    assert verdict.full_run_encounters_timed_out == 0
    assert verdict.adaptive_claim_authorized is False
    assert verdict.commercial_or_world_first_claim_authorized is False


def test_full_transfer_compatibility_refuses_failures(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path, passed=24, failed=1)

    verdict = evaluate_full_transfer_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    assert verdict.status == FULL_TRANSFER_COMPATIBILITY_REFUSED_TOKEN
    assert verdict.full_run_native_compatibility_proven is False
    assert verdict.ready_for_full_blind_evaluation is False


def test_full_transfer_compatibility_refuses_timeouts(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path, passed=24, timed_out=1)

    verdict = evaluate_full_transfer_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    assert verdict.status == FULL_TRANSFER_COMPATIBILITY_REFUSED_TOKEN
    assert verdict.full_run_native_compatibility_proven is False
    assert verdict.ready_for_full_blind_evaluation is False


def test_full_transfer_compatibility_refuses_wrong_count(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path, passed=24, executed=24)

    verdict = evaluate_full_transfer_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    assert verdict.status == FULL_TRANSFER_COMPATIBILITY_REFUSED_TOKEN
    assert verdict.full_run_native_compatibility_proven is False


def test_full_transfer_compatibility_writes_json_and_hashes_sources(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path)
    output = tmp_path / "full_controlled_transfer_compatibility_verdict.json"

    verdict = write_full_transfer_compatibility_verdict(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(verdict)))
    assert len(data["execution_receipt_sha256"]) == 64
    assert len(data["execution_receipts_sha256"]) == 64


def test_full_transfer_compatibility_boundary_blocks_overclaiming(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path)

    verdict = evaluate_full_transfer_compatibility(
        execution_receipt_path=receipt_path,
        execution_receipts_path=receipts_path,
    )

    boundary = verdict.boundary.lower()

    assert "full 25-encounter real native" in boundary
    assert "executed compatibly" in boundary
    assert "does not constitute adaptive" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_full_transfer_compatibility_cli_runner(tmp_path):
    receipt_path, receipts_path = _write_execution_bundle(tmp_path)
    output = tmp_path / "full_controlled_transfer_compatibility_verdict.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_full_controlled_transfer_compatibility_verdict.py",
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
    assert FULL_TRANSFER_COMPATIBILITY_READY_TOKEN in completed.stdout
    assert output.exists()
