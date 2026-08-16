from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts import manage_document_studio_commercial as document_manager


ROOT = Path(__file__).resolve().parents[1]


def request_spec(base: Path, consents: dict[str, bool] | None = None) -> Path:
    source = base / "policy.md"
    source.write_text("# Water Safety\n\nRecord pH after 2 minutes before releasing the report.\n", encoding="utf-8")
    spec = {
        "job_id": "DOC-STUDIO-TEST-001",
        "customer": {"name": "Test Client", "email": "client@example.org"},
        "service": "technical_edit",
        "title": "Water Safety Policy",
        "document_path": str(source),
        "source_language": "English",
        "document_domain": "water operations",
        "audience": "municipal operator",
        "consents": consents or {
            "document_owner_authorized": True,
            "remote_processing_approved": True,
            "human_review_required": True,
            "certified_translation_not_requested": True,
        },
    }
    path = base / "document_request.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_controlled_document_studio_job_runs_through_approval_and_delivery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_document_studio(request: dict, request_path: Path, output_root: Path) -> Path:
        job_dir = output_root / request["job_id"]
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "DOCUMENT_STUDIO_RECEIPT.json").write_text(json.dumps({
            "status": "human_review_required",
            "release": {"release_readiness": "blocked_pending_human_approval"},
            "processing": {"semantic_object_id": None},
        }), encoding="utf-8")
        (job_dir / "DOCUMENT_STUDIO_QA.json").write_text(json.dumps({
            "passed": True,
            "automated_integrity_passed": True,
            "release_readiness": "blocked_pending_human_approval",
        }), encoding="utf-8")
        with zipfile.ZipFile(job_dir / f"{request['job_id']}_DOCUMENT_STUDIO_REVIEW_PACK.zip", "w") as archive:
            archive.writestr("DOCUMENT_STUDIO_QA.json", "{}")
        return job_dir

    monkeypatch.setattr(document_manager, "run_document_studio", fake_run_document_studio)
    job_root = tmp_path / "jobs"
    event_log = tmp_path / "events.jsonl"
    output_root = tmp_path / "deliverables"
    job = document_manager.create_job(
        request_spec(tmp_path),
        job_root,
        event_log,
        ROOT / "config" / "document_studio_service.json",
        controlled=True,
    )
    assert job["payment"]["state"] == "waived"
    assert job["studio"]["state"] == "not_started"

    job = document_manager.run_job(job_root, job["job_id"], output_root, event_log)
    assert job["studio"]["state"] == "ready_for_human_review"
    assert job["approval"]["state"] == "pending"

    job = document_manager.approve_job(job_root, job["job_id"], "Test reviewer", event_log)
    assert job["approval"]["state"] == "approved"

    job = document_manager.prepare_delivery(job_root, job["job_id"], event_log)
    assert job["delivery"]["state"] == "draft_ready"
    assert job["delivery"]["mail_intent_id"]


def test_document_studio_rejects_missing_remote_processing_consent(tmp_path: Path) -> None:
    consents = {
        "document_owner_authorized": True,
        "remote_processing_approved": False,
        "human_review_required": True,
        "certified_translation_not_requested": True,
    }
    with pytest.raises(Exception):
        document_manager.create_job(
            request_spec(tmp_path, consents),
            tmp_path / "jobs",
            tmp_path / "events.jsonl",
            ROOT / "config" / "document_studio_service.json",
            controlled=True,
        )
