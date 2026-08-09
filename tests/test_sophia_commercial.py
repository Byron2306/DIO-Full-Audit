from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from scripts.manage_sophia_commercial import approve_job, create_job


ROOT = Path(__file__).resolve().parents[1]


def request_spec(base: Path, consents: dict[str, bool] | None = None) -> Path:
    manuscript = base / "section.md"
    manuscript.write_text("# Draft\n\nA controlled manuscript section.\n", encoding="utf-8")
    spec = {
        "job_id": "SOPHIA-TEST-001",
        "customer": {"name": "Test Author", "email": "author@example.org"},
        "title": "Controlled section",
        "document_path": str(manuscript),
        "research_question": "How should this controlled section be reviewed?",
        "citation_style": "APA 7",
        "consents": consents or {
            "manuscript_owner_authorized": True,
            "gemini_remote_processing_approved": True,
            "service_terms_accepted": True,
        },
    }
    path = base / "request.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_controlled_job_waives_payment_but_keeps_human_approval(tmp_path: Path) -> None:
    job = create_job(
        request_spec(tmp_path),
        tmp_path / "jobs",
        tmp_path / "events.jsonl",
        ROOT / "config" / "sophia_service.json",
        controlled=True,
    )
    assert job["payment"]["state"] == "waived"
    assert job["approval"]["state"] == "pending"
    assert job["delivery"]["state"] == "held"
    with pytest.raises(ValueError, match="grounded"):
        approve_job(tmp_path / "jobs", job["job_id"], "Test Reviewer", tmp_path / "events.jsonl")


def test_intake_rejects_missing_consent_before_provider_call(tmp_path: Path) -> None:
    consents = {
        "manuscript_owner_authorized": True,
        "gemini_remote_processing_approved": False,
        "service_terms_accepted": True,
    }
    with pytest.raises(jsonschema.ValidationError):
        create_job(
            request_spec(tmp_path, consents),
            tmp_path / "jobs",
            tmp_path / "events.jsonl",
            ROOT / "config" / "sophia_service.json",
            controlled=True,
        )
