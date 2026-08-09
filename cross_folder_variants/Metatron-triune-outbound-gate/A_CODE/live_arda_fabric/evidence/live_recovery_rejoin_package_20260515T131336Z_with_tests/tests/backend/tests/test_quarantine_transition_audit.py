"""Durability tests for quarantine transition audit metadata."""

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
QUARANTINE_PATH = BACKEND_DIR / "quarantine.py"


def _load_quarantine_module(tmp_path: Path):
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    quarantine_dir = tmp_path / "quarantine-store"
    os.environ["QUARANTINE_DIR"] = str(quarantine_dir)

    module_name = f"backend.quarantine_transition_{tmp_path.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, QUARANTINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.quarantine")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _create_sample_file(base_dir: Path, name: str = "sample.bin") -> Path:
    source_path = base_dir / "incoming" / name
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"malicious-test-content")
    return source_path


def test_quarantine_file_initializes_transition_audit_fields(tmp_path):
    quarantine = _load_quarantine_module(tmp_path)
    source = _create_sample_file(tmp_path)

    entry = quarantine.quarantine_file(
        filepath=str(source),
        threat_name="UnitTestThreat",
        threat_type="malware",
        detection_source="unit-test",
        auto_scan=False,
        auto_sandbox=False,
    )

    assert entry is not None
    assert entry.state_version == 1
    transition_log = entry.state_transition_log or []
    assert len(transition_log) == 1
    assert transition_log[0].get("from_status") is None
    assert transition_log[0].get("to_status") == "quarantined"


def test_restore_appends_transition_audit_and_increments_version(tmp_path):
    quarantine = _load_quarantine_module(tmp_path)
    source = _create_sample_file(tmp_path, name="restore.bin")

    entry = quarantine.quarantine_file(
        filepath=str(source),
        threat_name="RestoreThreat",
        detection_source="unit-test",
        auto_scan=False,
        auto_sandbox=False,
    )

    assert entry is not None
    assert quarantine.restore_file(entry.id) is True

    updated = quarantine.get_quarantine_entry(entry.id)
    assert updated is not None
    assert updated.status == "restored"
    assert updated.state_version == 2

    last_transition = (updated.state_transition_log or [])[-1]
    assert last_transition.get("from_status") == "quarantined"
    assert last_transition.get("to_status") == "restored"


def test_advance_pipeline_stage_appends_transition_audit(tmp_path):
    quarantine = _load_quarantine_module(tmp_path)
    source = _create_sample_file(tmp_path, name="pipeline.bin")

    entry = quarantine.quarantine_file(
        filepath=str(source),
        threat_name="PipelineThreat",
        detection_source="unit-test",
        auto_scan=False,
        auto_sandbox=False,
    )

    assert entry is not None

    updated = quarantine.advance_pipeline_stage(
        entry.id,
        "scanning",
        reason="Unit test stage advancement",
    )

    assert updated is not None
    assert updated.status == "scanning"
    assert updated.pipeline_stage == "scanning"
    assert updated.state_version == 2

    last_transition = (updated.state_transition_log or [])[-1]
    assert last_transition.get("from_status") == "quarantined"
    assert last_transition.get("to_status") == "scanning"


def test_add_sandbox_result_records_analyzed_transition(tmp_path):
    quarantine = _load_quarantine_module(tmp_path)
    source = _create_sample_file(tmp_path, name="sandbox.bin")

    entry = quarantine.quarantine_file(
        filepath=str(source),
        threat_name="SandboxThreat",
        detection_source="unit-test",
        auto_scan=False,
        auto_sandbox=False,
    )

    assert entry is not None

    updated = quarantine.add_sandbox_result(
        entry_id=entry.id,
        sandbox_id="sbx-unit-001",
        sandbox_type="light",
        execution_time_s=15,
        verdict="malicious",
        behaviors=["process_injection"],
        network_iocs=["198.51.100.10"],
    )

    assert updated is not None
    assert updated.status == "analyzed"
    assert updated.pipeline_stage == "analyzed"
    assert updated.state_version == 2

    last_transition = (updated.state_transition_log or [])[-1]
    assert last_transition.get("from_status") == "quarantined"
    assert last_transition.get("to_status") == "analyzed"
    assert last_transition.get("metadata", {}).get("sandbox_id") == "sbx-unit-001"
