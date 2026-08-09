from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from adapters.vamp.snapshot_pipeline import build_snapshot


ROOT = Path(__file__).resolve().parents[1]


def create_fixture_database(path: Path, evidence_dir: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE tasks(
            task_id TEXT PRIMARY KEY, kpa_code TEXT NOT NULL, title TEXT NOT NULL,
            window_start TEXT NOT NULL, window_end TEXT NOT NULL, cadence TEXT NOT NULL,
            min_required INTEGER NOT NULL, stretch_target INTEGER NOT NULL,
            lead_lag TEXT NOT NULL, hints_json TEXT NOT NULL
        );
        CREATE TABLE evidence(
            evidence_id TEXT PRIMARY KEY, sha1 TEXT, staff_id TEXT NOT NULL,
            year INTEGER NOT NULL, month_bucket TEXT NOT NULL, kpa_code TEXT,
            rating TEXT, tier TEXT, file_path TEXT NOT NULL, meta_json TEXT NOT NULL
        );
        CREATE TABLE evidence_task(
            evidence_id TEXT NOT NULL, task_id TEXT NOT NULL, mapped_by TEXT NOT NULL,
            confidence REAL NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(evidence_id, task_id)
        );
        CREATE TABLE task_no_evidence(
            staff_id TEXT NOT NULL, year INTEGER NOT NULL, task_id TEXT NOT NULL,
            month TEXT NOT NULL, reason TEXT, declared_at TEXT NOT NULL,
            PRIMARY KEY(staff_id, year, task_id, month)
        );
        """
    )
    tasks = [
        ("T1", "KPA1", "HISE312 internal moderation", "2026-01-01", "2026-01-31", "monthly", 1, 1, "lead", "{}"),
        ("T2", "KPA4", "Committee: School Management Committee", "2026-01-01", "2026-01-31", "monthly", 1, 1, "lead", "{}"),
        ("T3", "KPA3", "Publication submission", "2026-01-01", "2026-01-31", "monthly", 1, 1, "lag", "{}"),
    ]
    connection.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)", tasks)
    files = {
        "E1": evidence_dir / "HISE312_internal_moderation_approved.txt",
        "E2": evidence_dir / "School_meeting_invitation.txt",
        "E3": evidence_dir / "HISE312_internal_moderation_duplicate.txt",
        "E4": evidence_dir / "Unmapped_note.txt",
    }
    for path_item in files.values():
        path_item.write_text("Controlled evidence fixture.", encoding="utf-8")
    meta1 = {"target_task_id": "T1", "brain": {"primary_kpa_code": "KPA1"}, "outlook": {"source": "outlook_playwright", "search_reason": "matched task with terms: hise312, moderation"}}
    meta2 = {"target_task_id": "T2", "brain": {"primary_kpa_code": "KPA4"}, "outlook": {"source": "outlook_playwright", "search_reason": "matched task with terms: and, school"}}
    evidence_rows = [
        ("E1", "hash-1", "TEST", 2026, "2026-01", "KPA1", "", "", str(files["E1"]), json.dumps(meta1)),
        ("E2", "hash-2", "TEST", 2026, "2026-01", "KPA4", "", "", str(files["E2"]), json.dumps(meta2)),
        ("E3", "hash-1", "TEST", 2026, "2026-01", "KPA1", "", "", str(files["E3"]), json.dumps(meta1)),
        ("E4", "hash-4", "TEST", 2026, "2026-01", "KPA3", "", "", str(files["E4"]), "{}"),
    ]
    connection.executemany("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)", evidence_rows)
    connection.executemany(
        "INSERT INTO evidence_task VALUES(?,?,?,?,?)",
        [("E1", "T1", "outlook_collect:targeted", 0.9, "2026-01-10"),
         ("E2", "T2", "outlook_collect:targeted", 0.9, "2026-01-10"),
         ("E3", "T1", "outlook_collect:targeted", 0.9, "2026-01-10")],
    )
    connection.execute(
        "INSERT INTO task_no_evidence VALUES(?,?,?,?,?,?)",
        ("TEST", 2026, "T3", "2026-01", "No submission this month", "2026-02-01"),
    )
    connection.commit()
    connection.close()


def test_snapshot_separates_accepted_candidates_duplicates_and_declarations(tmp_path: Path) -> None:
    database = tmp_path / "progress.db"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    create_fixture_database(database, evidence_dir)
    request = {
        "schema": "dio.vamp_snapshot_request.v1",
        "job_id": "VAMP-TEST-001",
        "profile_path": str(ROOT / "config" / "vamp_profiles" / "nwu_academic_v1.json"),
        "source": {"kind": "vamp_sqlite", "database_path": str(database), "staff_id": "TEST", "year": 2026},
        "review": {"months": ["2026-01"]},
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
    snapshot = json.loads((output / "VAMP_SNAPSHOT.json").read_text(encoding="utf-8"))

    assert snapshot["metrics"]["accepted_mappings"] == 1
    assert snapshot["metrics"]["candidate_mappings"] == 1
    assert snapshot["metrics"]["duplicates_suppressed"] == 1
    assert snapshot["metrics"]["unmapped_evidence"] == 1
    assert snapshot["metrics"]["objectives_evidence_backed"] == 1
    assert snapshot["metrics"]["objectives_declared_no_evidence"] == 1
    assert all(item["source"]["display_name"].startswith("Evidence ") for item in snapshot["evidence"])
    assert snapshot["release"]["rating_generated"] is False
    assert (output / "VAMP-TEST-001_VAMP_EVIDENCE_SNAPSHOT.zip").is_file()
