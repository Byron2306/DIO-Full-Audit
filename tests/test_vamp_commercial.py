from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from scripts.manage_vamp_commercial import approve_job, create_job


ROOT = Path(__file__).resolve().parents[1]


def request_spec(database: Path) -> dict:
    return {
        "job_id": "VAMP-COMMERCIAL-TEST-001",
        "customer": {
            "name": "Controlled Reviewer",
            "email": "reviewer@example.com",
            "organization": "Example University",
        },
        "profile_path": str(ROOT / "config" / "vamp_profiles" / "university_generic_v1.json"),
        "source": {
            "kind": "vamp_sqlite",
            "database_path": str(database),
            "staff_id": "TEST",
            "year": 2026,
        },
        "review": {"months": ["2026-01"]},
        "privacy_mode": "redacted_demo",
        "consents": {
            "evidence_owner_authorized": True,
            "performance_data_processing_approved": True,
            "human_review_terms_accepted": True,
        },
    }


def test_controlled_intake_waives_payment_but_keeps_review_gate(tmp_path: Path) -> None:
    database = tmp_path / "progress.db"
    database.touch()
    spec_path = tmp_path / "request.json"
    spec_path.write_text(json.dumps(request_spec(database)), encoding="utf-8")

    job = create_job(
        spec_path,
        tmp_path / "jobs",
        tmp_path / "events.jsonl",
        ROOT / "config" / "vamp_service.json",
        controlled=True,
    )

    assert job["payment"]["state"] == "waived"
    assert job["snapshot"]["state"] == "not_started"
    assert job["approval"]["state"] == "pending"
    assert job["delivery"]["state"] == "held"
    with pytest.raises(ValueError, match="review-ready"):
        approve_job(tmp_path / "jobs", job["job_id"], "Test reviewer", tmp_path / "events.jsonl")


def test_intake_rejects_missing_processing_consent(tmp_path: Path) -> None:
    database = tmp_path / "progress.db"
    database.touch()
    spec = request_spec(database)
    spec["consents"]["performance_data_processing_approved"] = False
    spec_path = tmp_path / "request.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    with pytest.raises(jsonschema.ValidationError):
        create_job(
            spec_path,
            tmp_path / "jobs",
            tmp_path / "events.jsonl",
            ROOT / "config" / "vamp_service.json",
            controlled=True,
        )
