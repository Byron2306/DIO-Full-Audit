from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from products.professional_evidence_native_rich_routes import (
    _build_vamp_rich_database,
    _evidex_source_files,
)


def _write_sources(packet_dir: Path, names: list[str]) -> None:
    sources = packet_dir / "SOURCES"
    sources.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(names, 1):
        path = sources / name
        if path.suffix == ".csv":
            # Keep each synthetic source byte-distinct. The Evidex contract is
            # deliberately testing a genuinely multi-artifact customer folder,
            # not several filenames that contain identical placeholder bytes.
            path.write_text(
                f"source_id,source_name,value\nS-{index:02d},{name},customer-source-{index:02d}\n",
                encoding="utf-8",
            )
        else:
            path.write_text(f"customer source {index}: {name}\n", encoding="utf-8")


def test_vamp_rich_database_preserves_multiple_objectives_and_evidence(tmp_path: Path) -> None:
    packet_dir = tmp_path / "CUSTOMER_PACKET"
    names = [
        "research_article_acceptance.txt",
        "submitted_manuscript_record.txt",
        "module_coordination_appointment.txt",
        "module_timetable.csv",
        "community_engagement_planning_email.txt",
        "congratulatory_context_email.txt",
    ]
    _write_sources(packet_dir, names)
    packet = {"packet_dir": packet_dir, "packet_fingerprint": "sha256:test-packet"}
    database = tmp_path / "projection" / "vamp.db"

    projection = _build_vamp_rich_database(packet, database)

    assert projection["profile_id"] == "university_generic_v1"
    assert len(projection["tasks"]) == 3
    assert len(projection["evidence"]) == 6
    assert projection["rating_authority_created"] is False
    assert projection["employment_decision_created"] is False

    con = sqlite3.connect(database)
    assert con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 3
    assert con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 6
    assert con.execute("SELECT COUNT(*) FROM evidence_task").fetchone()[0] == 5
    assert con.execute("SELECT COUNT(*) FROM evidence WHERE kpa_code='RESEARCH'").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM evidence WHERE kpa_code='TEACHING'").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM evidence WHERE kpa_code='ENGAGEMENT'").fetchone()[0] == 1
    con.close()

    persisted = json.loads((database.parent / "VAMP_NATIVE_RICH_PROJECTION.json").read_text(encoding="utf-8"))
    assert persisted["packet_fingerprint"] == "sha256:test-packet"
    assert "planning email" in persisted["expected_semantics"]["KPA5"]


def test_evidex_rich_projection_requires_ten_separate_customer_sources(tmp_path: Path) -> None:
    packet_dir = tmp_path / "CUSTOMER_PACKET"
    names = [
        "claims_register.csv",
        "monitoring_workshops.csv",
        "narrative_draft.md",
        "workstream_email_summary.txt",
        "invoice_INV-118.txt",
        "photo_metadata.csv",
        "reporting_folder_readme.md",
        "02_evidence_register.csv",
        "03_exception_note.md",
        "01_customer_context.md",
    ]
    _write_sources(packet_dir, names)
    packet = {"packet_dir": packet_dir, "packet_fingerprint": "sha256:test-packet"}

    rows = _evidex_source_files(packet)

    assert len(rows) == 10
    assert [row["name"] for row in rows] == names
    assert len({row["sha256"] for row in rows}) == 10
    assert all(row["source_role"] == "customer_evidence" for row in rows)
