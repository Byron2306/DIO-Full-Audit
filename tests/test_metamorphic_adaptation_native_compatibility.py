import json
from dataclasses import asdict

from experiments.metamorphic_adaptation.native_compatibility import (
    COMPATIBILITY_READY_TOKEN,
    COMPATIBILITY_VERSION,
    classify_native_compatibility,
    write_native_compatibility_summary,
)


def _receipt(path, results):
    path.write_text(json.dumps({
        "adaptive_claim_authorized": False,
        "command_results": results,
    }))


def test_native_compatibility_classifies_fast_and_long_running(tmp_path):
    receipt = tmp_path / "receipt.json"
    _receipt(receipt, [
        {"label": "a", "exit_code": 0, "refusal_reason": None},
        {"label": "b", "exit_code": 124, "refusal_reason": "Command timed out after 20 seconds."},
        {"label": "c", "exit_code": 0, "refusal_reason": None},
    ])

    summary = classify_native_compatibility(receipt)

    assert summary.compatibility_version == COMPATIBILITY_VERSION
    assert summary.status == COMPATIBILITY_READY_TOKEN
    assert summary.compatible_fast == 2
    assert summary.compatible_long_running == 1
    assert summary.failed_runtime == 0
    assert summary.adaptive_claim_authorized is False


def test_native_compatibility_keeps_other_nonzero_as_runtime_failure(tmp_path):
    receipt = tmp_path / "receipt.json"
    _receipt(receipt, [
        {"label": "bad", "exit_code": 1, "refusal_reason": None},
    ])

    summary = classify_native_compatibility(receipt)

    assert summary.failed_runtime == 1
    assert summary.failed_contract == 0
    assert summary.failed_dependency == 0


def test_native_compatibility_writes_json_summary(tmp_path):
    receipt = tmp_path / "receipt.json"
    output = tmp_path / "summary.json"

    _receipt(receipt, [
        {"label": "a", "exit_code": 0, "refusal_reason": None},
        {"label": "b", "exit_code": 124, "refusal_reason": "Command timed out after 20 seconds."},
    ])

    summary = write_native_compatibility_summary(receipt, output)

    assert output.exists()
    assert json.loads(output.read_text()) == json.loads(json.dumps(asdict(summary)))
    assert json.loads(output.read_text())["status"] == COMPATIBILITY_READY_TOKEN


def test_native_compatibility_boundary_blocks_adaptive_claim(tmp_path):
    receipt = tmp_path / "receipt.json"
    _receipt(receipt, [
        {"label": "a", "exit_code": 0, "refusal_reason": None},
    ])

    summary = classify_native_compatibility(receipt)

    boundary = summary.classification_boundary.lower()
    assert "command readiness only" in boundary
    assert "does not evaluate transfer performance" in boundary
    assert "does not authorize" in boundary
