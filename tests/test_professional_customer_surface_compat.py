from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from adapters.format_core.renderer import render_semantic_asset, validate_semantic_content
from adapters.sophia.review_pipeline import _allowed_citation_keys, audit_references
from products.professional_evidence_customer_surface_compat import (
    _build_vamp_database_v2,
    _campaign_material_for_role,
    _evidex_contextual_intake,
    _merge_reference_text,
    _semantic_from_markdown,
    _vamp_domain,
)


class _CitationCheck:
    def to_dict(self) -> dict:
        return {"fail_count": 0, "errors": []}


def _citation_check(_: str) -> _CitationCheck:
    return _CitationCheck()


def test_sophia_supplied_reference_file_expands_closed_world_allow_set() -> None:
    manuscript = "The draft draws on Knowles (1975) and Garrison (1997)."
    separate = (
        "Knowles, M. (1975). Self-Directed Learning.\n"
        "Garrison, D. R. (1997). Self-directed learning: Toward a comprehensive model. Adult Education Quarterly, 48(1), 18-33.\n"
    )
    audit = audit_references(manuscript, _merge_reference_text("", separate), _citation_check)
    allowed = _allowed_citation_keys(audit, [])
    assert "knowles:1975" in allowed
    assert "garrison:1997" in allowed
    assert len(audit["reference_entries"]) == 2


def _packet(tmp_path: Path) -> dict:
    packet_dir = tmp_path / "CUSTOMER_PACKET"
    sources = packet_dir / "SOURCES"
    sources.mkdir(parents=True)
    register = sources / "02_evidence_register.csv"
    rows = [
        ("R-01", "Review period: January-June 2026."),
        ("R-02", "Objective KPA1 requires evidence of two research outputs; one accepted article and one submitted manuscript are present."),
        ("R-03", "KPA3 requires module coordination evidence; the appointment letter and timetable are present."),
        ("R-04", "KPA5 requires community engagement evidence; only an undated planning email is present."),
    ]
    with register.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record_id", "customer_supplied_record"])
        writer.writerows(rows)
    return {"packet_dir": packet_dir, "packet_fingerprint": "sha256:test"}


def test_vamp_projection_uses_profile_domains_and_populates_rows(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    db = _build_vamp_database_v2(packet, tmp_path / "projection" / "progress.db")
    with sqlite3.connect(db) as con:
        task_domains = {row[0] for row in con.execute("SELECT DISTINCT kpa_code FROM tasks")}
        evidence_domains = {row[0] for row in con.execute("SELECT DISTINCT kpa_code FROM evidence")}
        task_count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        evidence_count = con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        mapping_count = con.execute("SELECT COUNT(*) FROM evidence_task").fetchone()[0]
    allowed = {"RESEARCH", "TEACHING", "ENGAGEMENT", "LEADERSHIP", "DEVELOPMENT"}
    assert task_domains <= allowed
    assert evidence_domains <= allowed
    assert "PROFESSIONAL" not in task_domains
    assert "RESEARCH" in task_domains
    assert "ENGAGEMENT" in task_domains
    assert task_count == evidence_count == mapping_count == 4
    assert (db.parent / "VAMP_DOMAIN_PROJECTION.json").is_file()


def test_vamp_domain_classifier_is_deterministic_for_alpha_records() -> None:
    assert _vamp_domain("Accepted research article and submitted manuscript") == "RESEARCH"
    assert _vamp_domain("Community engagement evidence and outreach record") == "ENGAGEMENT"
    assert _vamp_domain("Module teaching timetable and assessment coordination") == "TEACHING"


def test_homs_exam_markdown_composes_through_format_core(tmp_path: Path) -> None:
    source = tmp_path / "HOMS_EXAM_PAPER.md"
    source.write_text(
        "# Grade 11 History Mid-Year Examination\n\n"
        "**Time:** 2 hours  \n**Total:** 150 marks\n\n"
        "## Section A\n\n"
        "### Question 1\n\nExplain the usefulness of the supplied source for a historian. (8)\n\n"
        "- Refer to origin.\n- Refer to content.\n- Refer to limitation.\n",
        encoding="utf-8",
    )
    semantic = _semantic_from_markdown(source, object_id="homs-exam-paper", title="Grade 11 History Mid-Year Examination", artifact_type="exam_paper")
    assert validate_semantic_content(semantic)["passed"] is True
    receipt = render_semantic_asset(
        semantic,
        tmp_path / "rendered",
        style_profile="dio_professional",
        delivery_profile="editable_review",
        language="en",
        channels=["docx", "html"],
        release_mode=False,
    )
    channels = {row["channel"] for row in receipt["outputs"]}
    assert channels == {"docx", "html"}
    assert receipt["status"] == "rendered_review_candidate"
    assert receipt["qa"]["passed"] is True


def test_evidex_customer_context_replaces_template_identity_without_inventing_dates() -> None:
    def base(_: dict) -> dict:
        return {
            "client": {"organization": "Client organization to confirm", "contact_name": "Client", "contact_email": ""},
            "pack": {"reporting_period": {"start": "To be confirmed", "end": "To be confirmed"}},
            "constraints": {"known_gaps": ["Client organization, reporting period, donor template, and KPI list may need confirmation."]},
        }

    build = _evidex_contextual_intake(base)
    intake = build({"customer_context": {"organisation": "Green Basin Initiative", "reporting_period": {}}})
    assert intake["client"]["organization"] == "Green Basin Initiative"
    assert intake["pack"]["reporting_period"] == {
        "start": "Not supplied by customer",
        "end": "Not supplied by customer",
    }
    assert any("not supplied by the customer" in row.casefold() for row in intake["constraints"]["known_gaps"])


def test_campaign_material_selection_prefers_semantic_fit_and_nonreuse() -> None:
    candidates = [
        {"material_id": "research-photo", "material_kind": "curated_photo", "semantic_visual_kinds": ["research_workbench"]},
        {"material_id": "proof-artifact", "material_kind": "artifact_render", "semantic_visual_kinds": ["provenance_stack"]},
        {"material_id": "method-photo", "material_kind": "curated_photo", "semantic_visual_kinds": ["method_map"]},
    ]
    used: set[str] = set()
    first = _campaign_material_for_role("question", candidates, used)
    assert first and first["material_id"] == "research-photo"
    used.add(first["material_id"])
    second = _campaign_material_for_role("proof", candidates, used)
    assert second and second["material_id"] == "proof-artifact"
    used.add(second["material_id"])
    third = _campaign_material_for_role("workflow_demo", candidates, used)
    assert third and third["material_id"] == "method-photo"
    assert len({first["material_id"], second["material_id"], third["material_id"]}) == 3
