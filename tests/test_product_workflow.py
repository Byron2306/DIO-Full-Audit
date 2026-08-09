from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.vamp.snapshot_pipeline import build_snapshot
from scripts.build_vamp_portability_fixture import build_fixture
from scripts.manage_product_workflow import (
    approve_intake,
    bootstrap_job,
    next_action,
    prepare_notification,
)


ROOT = Path(__file__).resolve().parents[1]


def source_job(path: Path, product: str = "homs") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "job_id": f"{product}-workflow-test-001",
        "created_at": "2026-08-08T00:00:00+00:00",
        "status": "needs_review",
        "risk": "moderate",
        "route": {"product": product, "confidence": 0.95, "reason": "Controlled test"},
        "inputs": [{"sender": "Reviewer <reviewer@example.com>", "subject": "Controlled request"}],
        "evidence": [{"text_extract": "Controlled evidence"}],
        "approval": {"required": True, "state": "pending"},
    }), encoding="utf-8")


def test_homs_workflow_exposes_one_next_action_and_governed_notification(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    source = runs / "client-001" / "homs" / "homs-workflow-test-001.json"
    source_job(source)
    state_root = tmp_path / "state"
    events = tmp_path / "events.jsonl"
    workflow = bootstrap_job(source, state_root, runs)
    assert next_action(workflow, tmp_path / "mail") == "approve-intake"

    workflow = approve_intake(state_root, workflow["job_id"], "Test operator", events)
    assert next_action(workflow, tmp_path / "mail") == "process"

    workflow["processing"].update({"state": "request_ready", "output_dir": str(tmp_path / "pack")})
    workflow_path = state_root / workflow["job_id"] / "JOB.json"
    workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
    workflow = prepare_notification(state_root, workflow["job_id"], events, tmp_path / "mail")
    assert workflow["notification"]["state"] == "draft_ready"
    assert next_action(workflow, tmp_path / "mail") == "outlook-draft"
    source_payload = json.loads(source.read_text())
    assert source_payload["approval"]["state"] == "approved"


def test_generic_university_fixture_proves_profile_portability(tmp_path: Path) -> None:
    database = build_fixture(tmp_path / "fixture")
    request = {
        "schema": "dio.vamp_snapshot_request.v1",
        "job_id": "VAMP-PORTABILITY-TEST-001",
        "profile_path": str(ROOT / "config" / "vamp_profiles" / "university_generic_v1.json"),
        "source": {"kind": "vamp_sqlite", "database_path": str(database), "staff_id": "PORTABLE-001", "year": 2026},
        "review": {"months": ["2026-01", "2026-02"]},
        "privacy_mode": "redacted_demo",
        "consents": {
            "evidence_owner_authorized": True,
            "performance_data_processing_approved": True,
            "human_review_terms_accepted": True,
        },
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    output = build_snapshot(request_path, tmp_path / "output", run_evidex=False)
    snapshot = json.loads((output / "VAMP_SNAPSHOT.json").read_text())
    assert snapshot["profile"]["profile_id"] == "university_generic_v1"
    assert snapshot["metrics"]["accepted_mappings"] == 3
    assert snapshot["metrics"]["candidate_mappings"] == 1
    assert snapshot["metrics"]["objectives_declared_no_evidence"] == 1
    assert snapshot["metrics"]["objectives_gap"] == 2


def test_source_job_outside_allowed_runs_root_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "outside.json"
    source_job(source)
    with pytest.raises(ValueError, match="runs directory"):
        bootstrap_job(source, tmp_path / "state", tmp_path / "runs")
