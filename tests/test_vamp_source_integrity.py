import json
from pathlib import Path

from adapters.vamp.snapshot_pipeline import build_snapshot
from tests.test_vamp_snapshot_adapter import create_fixture_database, ROOT


def test_tampered_source_cannot_be_accepted(tmp_path: Path):
    database = tmp_path / "progress.db"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    create_fixture_database(database, evidence_dir)

    request = {
        "schema": "dio.vamp_snapshot_request.v1",
        "job_id": "VAMP-INTEGRITY-TEST",
        "profile_path": str(
            ROOT / "config/vamp_profiles/nwu_academic_v1.json"
        ),
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

    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))

    baseline = build_snapshot(
        request_path, tmp_path / "baseline", run_evidex=False
    )
    baseline_data = json.loads(
        (baseline / "VAMP_SNAPSHOT.json").read_text()
    )

    assert baseline_data["metrics"]["accepted_mappings"] == 1

    source = evidence_dir / "HISE312_internal_moderation_approved.txt"
    source.write_text("TAMPERED AFTER HASH REGISTRATION")

    attacked = build_snapshot(
        request_path, tmp_path / "tampered", run_evidex=False
    )
    attacked_data = json.loads(
        (attacked / "VAMP_SNAPSHOT.json").read_text()
    )

    e1 = next(
        row for row in attacked_data["evidence"]
        if row["evidence_id"] == "E1"
    )

    assert all(
        mapping["decision"] != "accepted"
        for mapping in e1["mappings"]
    )
    assert any(
        "SHA-1 mismatch" in reason
        for mapping in e1["mappings"]
        for reason in mapping["reasons"]
    )
    assert attacked_data["metrics"]["accepted_mappings"] == 0
    assert attacked_data["release"]["rating_generated"] is False
    assert attacked_data["release"]["employment_decision_generated"] is False
