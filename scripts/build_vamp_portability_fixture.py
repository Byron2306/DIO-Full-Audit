#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "samples" / "vamp" / "generic_university"


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def build_fixture(out_dir: Path = DEFAULT_OUT) -> Path:
    out_dir = out_dir.expanduser().resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    evidence_dir = out_dir / "evidence"
    evidence_dir.mkdir(parents=True)
    files = {
        "GEN-E01": ("ABCD101_assessment_moderation_approved.txt", "Approved moderation report for ABCD101 assessment.", "TEACHING"),
        "GEN-E02": ("journal_manuscript_submission_accepted.txt", "Journal acknowledgement confirms manuscript submission.", "RESEARCH"),
        "GEN-E03": ("faculty_committee_minutes_signed.txt", "Signed faculty committee minutes and decision record.", "LEADERSHIP"),
        "GEN-E04": ("community_workshop_invitation.txt", "Invitation to a proposed community workshop.", "ENGAGEMENT"),
        "GEN-E05": ("unmapped_professional_note.txt", "General professional note with no objective mapping.", "DEVELOPMENT"),
    }
    paths: dict[str, Path] = {}
    for evidence_id, (name, body, _) in files.items():
        path = evidence_dir / name
        path.write_text(body + "\n", encoding="utf-8")
        paths[evidence_id] = path

    database = out_dir / "progress.db"
    connection = sqlite3.connect(database)
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
    connection.executemany(
        "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)",
        [
            ("GEN-TEACH-001", "TEACHING", "ABCD101 assessment moderation", "2026-01-01", "2026-01-31", "monthly", 1, 1, "lead", "{}"),
            ("GEN-RES-001", "RESEARCH", "Journal manuscript submission", "2026-01-01", "2026-01-31", "monthly", 1, 1, "lag", "{}"),
            ("GEN-LEAD-001", "LEADERSHIP", "Faculty committee participation", "2026-01-01", "2026-01-31", "monthly", 1, 1, "lead", "{}"),
            ("GEN-ENG-001", "ENGAGEMENT", "Community workshop delivery", "2026-02-01", "2026-02-28", "monthly", 1, 1, "lead", "{}"),
            ("GEN-DEV-001", "DEVELOPMENT", "Professional development completion", "2026-02-01", "2026-02-28", "monthly", 1, 1, "lead", "{}"),
            ("GEN-TEACH-002", "TEACHING", "Student consultation report", "2026-02-01", "2026-02-28", "monthly", 1, 1, "lead", "{}"),
        ],
    )
    metadata = {
        "GEN-E01": {"target_task_id": "GEN-TEACH-001", "brain": {"primary_kpa_code": "TEACHING"}},
        "GEN-E02": {"target_task_id": "GEN-RES-001", "brain": {"primary_kpa_code": "RESEARCH"}, "outlook": {"source": "outlook", "search_reason": "matched task with terms: journal, manuscript, submission"}},
        "GEN-E03": {"target_task_id": "GEN-LEAD-001", "brain": {"primary_kpa_code": "LEADERSHIP"}},
        "GEN-E04": {"target_task_id": "GEN-ENG-001", "brain": {"primary_kpa_code": "ENGAGEMENT"}, "outlook": {"source": "outlook", "search_reason": "matched task with terms: community, workshop, delivery"}},
        "GEN-E05": {},
    }
    connection.executemany(
        "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
        [
            (evidence_id, sha1(paths[evidence_id]), "PORTABLE-001", 2026, "2026-01" if evidence_id in {"GEN-E01", "GEN-E02", "GEN-E03"} else "2026-02", domain, "", "", str(paths[evidence_id]), json.dumps(metadata[evidence_id]))
            for evidence_id, (_, _, domain) in files.items()
        ],
    )
    connection.executemany(
        "INSERT INTO evidence_task VALUES(?,?,?,?,?)",
        [
            ("GEN-E01", "GEN-TEACH-001", "efundi_collect:direct_lms", 0.98, "2026-01-31"),
            ("GEN-E02", "GEN-RES-001", "outlook_collect:targeted", 0.92, "2026-01-31"),
            ("GEN-E03", "GEN-LEAD-001", "human_asserted", 1.0, "2026-01-31"),
            ("GEN-E04", "GEN-ENG-001", "outlook_collect:targeted", 0.9, "2026-02-28"),
        ],
    )
    connection.execute(
        "INSERT INTO task_no_evidence VALUES(?,?,?,?,?,?)",
        ("PORTABLE-001", 2026, "GEN-DEV-001", "2026-02", "No development activity completed in this window", "2026-03-01"),
    )
    connection.commit()
    connection.close()
    receipt = {
        "schema": "dio.vamp_portability_fixture.v1",
        "institution": "Example Metropolitan University",
        "profile_id": "university_generic_v1",
        "staff_id": "PORTABLE-001",
        "database_path": str(database),
        "evidence_files": len(files),
        "objectives": 6,
        "contains_real_personal_data": False,
    }
    (out_dir / "FIXTURE_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return database


if __name__ == "__main__":
    print(build_fixture())
